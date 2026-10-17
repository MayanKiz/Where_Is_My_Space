"""WIMS AI inference worker.

Runs as a separate process from the API. Two loops share one detector:

  jobs   — claim durable processing_jobs rows, download the private temporary
           video, run YOLO person detection on sampled frames, estimate zone
           occupancy, store an annotated preview, persist an occupancy
           snapshot, and mark the job completed (only with verified results).
  stream — continuously read registered RTSP/RTSPS sources (decrypted
           server-side), run the same detection, and publish zone snapshots at
           a configured interval.

Usage:
  python -m app.worker --mode jobs
  python -m app.worker --mode stream
  python -m app.worker --mode all

Environment variables reuse the API's (.env) plus WIMS_WORKER_* tuning knobs.
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import tempfile
import threading
import time
import traceback
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
from cryptography.fernet import Fernet, InvalidToken
from pydantic_settings import BaseSettings, SettingsConfigDict
from supabase import Client, create_client

from app.detector import Detection, ModelUnavailableError, YoloDetector, draw_detections
from app.occupancy import OccupancyTracker, estimate_zone_occupancy, normalize_polygon, polygon_to_pixels

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("wims.worker")

DETECTOR_VERSION = "yolov5s-onnx-opencv-dnn"

JOB_COLUMNS = "id,source_id,location_id,zone_id,source_type,storage_path,status,progress_percent,expires_at"
SOURCE_COLUMNS = "id,name,location_id,zone_id,status,stream_url_ciphertext,metadata,last_seen_at"


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Shared with the API service.
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_video_bucket: str = "wims-temporary-videos"
    source_encryption_key: str | None = None

    # Worker-specific.
    supabase_preview_bucket: str = "wims-job-previews"
    worker_id: str = f"{socket.gethostname()}-{os.getpid()}"
    poll_seconds: int = 5
    stale_claim_minutes: int = 30
    max_attempts: int = 3
    yolo_model_path: str = "models/yolov5s.onnx"
    yolo_model_url: str = "https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx"
    yolo_model_sha256: str = "8bc25a47abdbe2fd23e30eb948746bf856b031ea3cc815166687f52db9f8c659"
    detection_confidence: float = 0.35
    detection_iou: float = 0.45
    frame_stride: int = 5
    max_sampled_frames: int = 60
    keep_raw_video: bool = False
    preview_width: int = 960
    stream_interval_seconds: int = 10
    stream_snapshot_max_per_hour: int = 600


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_client(settings: WorkerSettings) -> Client | None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        logger.error(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not configured; the worker cannot run."
        )
        return None
    try:
        return create_client(settings.supabase_url, settings.supabase_service_role_key)
    except Exception:
        logger.exception("Could not initialise the Supabase client.")
        return None


def build_detector(settings: WorkerSettings) -> YoloDetector:
    return YoloDetector(
        settings.yolo_model_path,
        url=settings.yolo_model_url,
        sha256=settings.yolo_model_sha256 or None,
        conf_threshold=settings.detection_confidence,
        iou_threshold=settings.detection_iou,
    )


# --------------------------------------------------------------------------- #
# Job queue (durable, backed by processing_jobs rows)
# --------------------------------------------------------------------------- #


@dataclass
class AnalysisResult:
    frames_total: int = 0
    frames_sampled: int = 0
    tracker: OccupancyTracker | None = None
    annotated_jpeg: bytes | None = None

    def as_dict(self) -> dict[str, Any]:
        tracker = self.tracker or OccupancyTracker()
        return {
            "frames_total": self.frames_total,
            "frames_sampled": self.frames_sampled,
            "persons_peak": tracker.peak_occupied,
            "persons_peak_total": tracker.peak_total,
            "persons_mean": tracker.mean_occupied,
            "detection_confidence": tracker.mean_confidence,
        }


def analyse_video(
    path: Path,
    detector: YoloDetector,
    *,
    zone_polygon_px: list[tuple[float, float]] | None,
    frame_stride: int,
    max_sampled_frames: int,
    preview_width: int,
) -> AnalysisResult:
    """Sample frames from a clip, detect persons, and build an annotated preview."""
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError("VIDEO_UNREADABLE")

    result = AnalysisResult(tracker=OccupancyTracker())
    best_frame: tuple[Any, list[Detection]] | None = None
    index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            result.frames_total += 1
            if index % max(1, frame_stride) == 0 and result.frames_sampled < max_sampled_frames:
                detections = detector.detect_persons(frame)
                centers = [d.center for d in detections]
                in_zone = estimate_zone_occupancy(centers, zone_polygon_px)
                result.tracker.add_sample(in_zone, len(detections), [d.score for d in detections])
                result.frames_sampled += 1
                if best_frame is None or len(detections) > len(best_frame[1]):
                    best_frame = (frame, detections)
            index += 1
    finally:
        capture.release()

    if result.frames_total == 0:
        raise RuntimeError("VIDEO_NO_FRAMES")

    if best_frame and best_frame[1]:
        annotated = draw_detections(best_frame[0], best_frame[1], color=(0, 60, 220))
        scale = preview_width / max(1, annotated.shape[1])
        if scale < 1:
            annotated = cv2.resize(annotated, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        ok, buffer = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if ok:
            result.annotated_jpeg = buffer.tobytes()
    return result


def claim_job(client: Client, settings: WorkerSettings) -> dict[str, Any] | None:
    """Atomically claim one eligible job (received/queued, attempts left)."""
    now = datetime.now(timezone.utc)
    stale_before = now.timestamp() - settings.stale_claim_minutes * 60

    # Requeue stale claims from crashed workers first.
    try:
        stale = (
            client.table("processing_jobs")
            .update({"status": "queued", "claimed_by": None, "claimed_at": None})
            .eq("status", "processing")
            .lt("claimed_at", datetime.fromtimestamp(stale_before, tz=timezone.utc).isoformat())
            .execute()
        )
        if getattr(stale, "data", None):
            logger.warning("Requeued %d stale processing job(s).", len(stale.data))
    except Exception:
        logger.exception("Stale-claim sweep failed.")

    candidates = (
        client.table("processing_jobs")
        .select(JOB_COLUMNS + ",attempt_count,claimed_at")
        .in_("status", ["received", "queued"])
        .order("created_at")
        .limit(10)
        .execute()
    ).data or []

    for job in candidates:
        if int(job.get("attempt_count") or 0) >= settings.max_attempts:
            _finish_failed(client, job["id"], "MAX_ATTEMPTS", "Worker failed this job too many times.")
            continue
        claim = (
            client.table("processing_jobs")
            .update(
                {
                    "status": "processing",
                    "claimed_by": settings.worker_id,
                    "claimed_at": now.isoformat(),
                    "started_at": job.get("started_at") or now.isoformat(),
                    "progress_percent": 10,
                    "attempt_count": int(job.get("attempt_count") or 0) + 1,
                }
            )
            .eq("id", job["id"])
            .in_("status", ["received", "queued"])
            .select("id")
            .execute()
        )
        if getattr(claim, "data", None):
            logger.info("Claimed job %s", job["id"])
            return {**job, "attempt_count": int(job.get("attempt_count") or 0) + 1}
    return None


def _finish_failed(client: Client, job_id: str, code: str, message: str) -> None:
    try:
        client.table("processing_jobs").update(
            {
                "status": "failed",
                "finished_at": utcnow(),
                "error_code": code,
                "result_summary": {"stage": "failed", "error_code": code, "message": message},
                "claimed_by": None,
                "claimed_at": None,
            }
        ).eq("id", job_id).execute()
        logger.error("Job %s failed: %s — %s", job_id, code, message)
    except Exception:
        logger.exception("Could not mark job %s as failed.", job_id)


def get_zone(client: Client, zone_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("zones")
        .select("id,name,capacity,polygon,location_id")
        .eq("id", zone_id)
        .limit(1)
        .execute()
    ).data
    return rows[0] if rows else None


def insert_snapshot(
    client: Client,
    *,
    zone_id: str,
    occupied: int,
    capacity: int,
    confidence: float | None,
    job_id: str | None = None,
) -> None:
    client.table("occupancy_snapshots").insert(
        {
            "zone_id": zone_id,
            "job_id": job_id,
            "occupied_count": max(0, int(occupied)),
            "capacity_count": max(0, int(capacity)),
            "confidence": confidence,
            "detector_version": DETECTOR_VERSION,
            "observed_at": utcnow(),
        }
    ).execute()


def process_job(client: Client, settings: WorkerSettings, detector: YoloDetector, job: dict[str, Any]) -> None:
    job_id = job["id"]
    storage_path = job.get("storage_path")
    if not storage_path:
        _finish_failed(client, job_id, "NO_VIDEO", "This job has no stored video object to process.")
        return

    zone: dict[str, Any] | None = None
    zone_polygon_norm: list[tuple[float, float]] | None = None
    if job.get("zone_id"):
        zone = get_zone(client, job["zone_id"])
        if zone is None:
            _finish_failed(client, job_id, "ZONE_NOT_FOUND", "The configured zone no longer exists.")
            return
        # Normalised polygon -> pixels is resolution-dependent, so it is converted
        # to pixel coordinates per sampled frame inside the analysis pass.
        zone_polygon_norm = normalize_polygon(zone.get("polygon")) or None
    raw_bytes = client.storage.from_(settings.supabase_video_bucket).download(storage_path)
    if not raw_bytes:
        _finish_failed(client, job_id, "VIDEO_MISSING", "The stored video could not be downloaded.")
        return

    suffix = Path(job_id).suffix if Path(job_id).suffix else (".webm" if str(storage_path).endswith(".webm") else ".mp4")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw_bytes)
            tmp_path = Path(tmp.name)
    except OSError:
        logger.exception("Could not stage the video for job %s", job_id)
        _finish_failed(client, job_id, "STAGING_FAILED", "Local staging of the video failed.")
        return

    try:
        _update_job_progress(client, job_id, 35)
        analysis = _analyse_with_normalised_polygon(
            tmp_path,
            detector,
            zone_polygon_norm=zone_polygon_norm,
            frame_stride=settings.frame_stride,
            max_sampled_frames=settings.max_sampled_frames,
            preview_width=settings.preview_width,
        )
        _update_job_progress(client, job_id, 85)

        preview_path: str | None = None
        if analysis.annotated_jpeg:
            preview_path = f"{job_id}/preview.jpg"
            try:
                client.storage.from_(settings.supabase_preview_bucket).upload(
                    path=preview_path,
                    file=analysis.annotated_jpeg,
                    file_options={"content-type": "image/jpeg", "upsert": "true"},
                )
            except Exception:
                logger.exception("Could not store the preview for job %s", job_id)
                preview_path = None

        summary = analysis.as_dict()
        summary.update(
            {
                "stage": "ai_processed",
                "detector": detector.version,
                "detector_version": DETECTOR_VERSION,
                "preview_path": preview_path,
                "zone_id": job.get("zone_id"),
                "zone_name": zone.get("name") if zone else None,
            }
        )

        if zone:
            capacity = int(zone.get("capacity") or 0)
            occupied = summary["persons_peak"]
            confidence = summary.get("detection_confidence")
            summary["occupancy"] = {
                "estimate": "peak persons observed inside the zone polygon during the clip",
                "occupied": occupied,
                "capacity": capacity,
                "available": max(capacity - occupied, 0),
                "polygon_based": bool(zone_polygon_norm),
            }
            insert_snapshot(
                client,
                zone_id=job["zone_id"],
                occupied=occupied,
                capacity=capacity,
                confidence=confidence,
                job_id=job_id,
            )

        client.table("processing_jobs").update(
            {
                "status": "completed",
                "progress_percent": 100,
                "finished_at": utcnow(),
                "error_code": None,
                "result_summary": summary,
                "claimed_by": None,
                "claimed_at": None,
            }
        ).eq("id", job_id).execute()

        # Raw video is deleted immediately after verified processing; the job row
        # keeps only metadata and derived results.
        if not settings.keep_raw_video:
            try:
                client.storage.from_(settings.supabase_video_bucket).remove([storage_path])
                client.table("processing_jobs").update(
                    {"storage_path": None, "video_deleted_at": utcnow()}
                ).eq("id", job_id).execute()
            except Exception:
                logger.exception("Processed job %s but the raw video cleanup failed.", job_id)

        logger.info(
            "Job %s completed: %s frames sampled(s), peak persons %s",
            job_id,
            summary["frames_sampled"],
            summary["persons_peak"],
        )
    except ModelUnavailableError as exc:
        _finish_failed(client, job_id, "MODEL_UNAVAILABLE", str(exc))
    except RuntimeError as exc:
        _finish_failed(client, job_id, str(exc), "The stored video could not be decoded.")
    except Exception as exc:
        logger.exception("Job %s crashed.", job_id)
        _finish_failed(client, job_id, "WORKER_ERROR", f"{type(exc).__name__}: {exc}")
        logger.debug("%s", traceback.format_exc())
    finally:
        with suppress(OSError):
            tmp_path.unlink(missing_ok=True)


class _NormalisedZoneAdapter:
    """Converts a 0..1 polygon to pixels using each frame's size."""

    def __init__(self, polygon_norm: list[tuple[float, float]] | None) -> None:
        self.polygon_norm = polygon_norm

    def for_frame(self, width: int, height: int) -> list[tuple[float, float]] | None:
        if self.polygon_norm is None:
            return None
        return polygon_to_pixels(self.polygon_norm, width, height)


def _analyse_with_normalised_polygon(
    path: Path,
    detector: YoloDetector,
    *,
    zone_polygon_norm: list[tuple[float, float]] | None,
    frame_stride: int,
    max_sampled_frames: int,
    preview_width: int,
) -> AnalysisResult:
    if zone_polygon_norm is None:
        return analyse_video(
            path,
            detector,
            zone_polygon_px=None,
            frame_stride=frame_stride,
            max_sampled_frames=max_sampled_frames,
            preview_width=preview_width,
        )

    adapter = _NormalisedZoneAdapter(zone_polygon_norm)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError("VIDEO_UNREADABLE")

    result = AnalysisResult(tracker=OccupancyTracker())
    best_frame = None
    index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            result.frames_total += 1
            if index % max(1, frame_stride) == 0 and result.frames_sampled < max_sampled_frames:
                height, width = frame.shape[:2]
                polygon_px = adapter.for_frame(width, height)
                detections = detector.detect_persons(frame)
                centers = [d.center for d in detections]
                in_zone = estimate_zone_occupancy(centers, polygon_px)
                result.tracker.add_sample(in_zone, len(detections), [d.score for d in detections])
                result.frames_sampled += 1
                if best_frame is None or len(detections) > len(best_frame[1]):
                    best_frame = (frame, detections)
            index += 1
    finally:
        capture.release()

    if result.frames_total == 0:
        raise RuntimeError("VIDEO_NO_FRAMES")
    if best_frame and best_frame[1]:
        annotated = draw_detections(best_frame[0], best_frame[1], color=(0, 60, 220))
        scale = preview_width / max(1, annotated.shape[1])
        if scale < 1:
            annotated = cv2.resize(annotated, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        ok, buffer = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if ok:
            result.annotated_jpeg = buffer.tobytes()
    return result


def _update_job_progress(client: Client, job_id: str, percent: int) -> None:
    client.table("processing_jobs").update(
        {"progress_percent": percent}
    ).eq("id", job_id).execute()


def jobs_loop(settings: WorkerSettings, stop: threading.Event) -> None:
    client = build_client(settings)
    if client is None:
        return
    detector = build_detector(settings)
    try:
        detector.load()
    except ModelUnavailableError as exc:
        logger.error("Detector unavailable; jobs will be marked failed when claimed: %s", exc)

    logger.info("Job worker started (id=%s).", settings.worker_id)
    while not stop.is_set():
        try:
            job = claim_job(client, settings)
            if job is None:
                stop.wait(settings.poll_seconds)
                continue
            process_job(client, settings, detector, job)
        except Exception:
            logger.exception("jobs_loop iteration failed.")
            stop.wait(settings.poll_seconds)
    logger.info("Job worker stopped.")


# --------------------------------------------------------------------------- #
# Continuous RTSP/RTSPS ingestion
# --------------------------------------------------------------------------- #


def decrypt_stream_url(settings: WorkerSettings, ciphertext: str) -> str:
    if not settings.source_encryption_key:
        raise RuntimeError("SOURCE_ENCRYPTION_NOT_CONFIGURED")
    fer = Fernet(settings.source_encryption_key.encode("utf-8"))
    try:
        return fer.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("STREAM_DECRYPT_FAILED") from exc


@dataclass
class _StreamState:
    capture: Any = None
    last_analyzed: float = 0.0
    snapshots_this_hour: float = 0.0
    hour_marker: float = 0.0


def stream_loop(settings: WorkerSettings, stop: threading.Event) -> None:
    client = build_client(settings)
    if client is None:
        return
    detector = build_detector(settings)
    try:
        detector.load()
    except ModelUnavailableError as exc:
        logger.error("Detector unavailable for streaming: %s", exc)
        stop.wait(settings.poll_seconds)
        return

    states: dict[str, _StreamState] = {}
    logger.info("Stream worker started (interval=%ss).", settings.stream_interval_seconds)

    while not stop.is_set():
        try:
            sources = (
                client.table("video_sources")
                .select(SOURCE_COLUMNS)
                .eq("source_type", "rtsp_camera")
                .not_.is_("zone_id", "null")
                .not_.is_("stream_url_ciphertext", "null")
                .in_("status", ["registered", "ready", "connected", "recording", "streaming"])
                .limit(50)
                .execute()
            ).data or []

            known_ids = {source["id"] for source in sources}
            for stale_id in list(states):
                if stale_id not in known_ids:
                    state = states.pop(stale_id)
                    if state.capture is not None:
                        state.capture.release()

            for source in sources:
                if stop.is_set():
                    break
                _analyse_source_once(client, settings, detector, source, states)

        except Exception:
            logger.exception("stream_loop iteration failed.")
        stop.wait(settings.poll_seconds)
    for state in states.values():
        if state.capture is not None:
            state.capture.release()
    logger.info("Stream worker stopped.")


def _analyse_source_once(
    client: Client,
    settings: WorkerSettings,
    detector: YoloDetector,
    source: dict[str, Any],
    states: dict[str, _StreamState],
) -> None:
    source_id = source["id"]
    zone = get_zone(client, source["zone_id"])
    if zone is None:
        return
    capacity = int(zone.get("capacity") or 0)
    polygon = normalize_polygon(zone.get("polygon"))

    state = states.setdefault(source_id, _StreamState())
    now = time.time()
    interval = max(1, settings.stream_interval_seconds)

    if state.hour_marker == 0:
        state.hour_marker = now
    if now - state.hour_marker >= 3600:
        state.hour_marker = now
        state.snapshots_this_hour = 0
    if state.snapshots_this_hour >= settings.stream_snapshot_max_per_hour:
        return
    if state.last_analyzed and now - state.last_analyzed < interval:
        return

    if state.capture is None:
        try:
            url = decrypt_stream_url(settings, source["stream_url_ciphertext"])
        except RuntimeError:
            logger.error("Source %s: stream URL cannot be decrypted; marking error.", source_id)
            client.table("video_sources").update({"status": "error"}).eq("id", source_id).execute()
            return
        capture = cv2.VideoCapture(url)
        if not capture.isOpened():
            capture.release()
            logger.warning("Source %s: could not open RTSP stream.", source_id)
            client.table("video_sources").update({"status": "error"}).eq("id", source_id).execute()
            return
        state.capture = capture

    ok, frame = state.capture.read()
    if not ok:
        state.capture.release()
        state.capture = None
        client.table("video_sources").update({"status": "error"}).eq("id", source_id).execute()
        return

    height, width = frame.shape[:2]
    polygon_px = polygon_to_pixels(polygon, width, height) if polygon and len(polygon) >= 3 else None
    detections = detector.detect_persons(frame)
    occupied = estimate_zone_occupancy([d.center for d in detections], polygon_px)
    confidence = round(sum(d.score for d in detections) / len(detections), 4) if detections else 0.0

    insert_snapshot(
        client,
        zone_id=source["zone_id"],
        occupied=occupied,
        capacity=capacity,
        confidence=confidence,
    )
    state.last_analyzed = now
    state.snapshots_this_hour += 1

    client.table("video_sources").update(
        {"status": "streaming", "last_seen_at": utcnow(), "updated_at": utcnow()}
    ).eq("id", source_id).execute()
    logger.info("Source %s (%s): zone '%s' snapshot persons=%s.", source_id, source.get("name"), zone.get("name"), occupied)


# --------------------------------------------------------------------------- #


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WIMS AI inference worker")
    parser.add_argument("--mode", choices=["jobs", "stream", "all"], default="all")
    parser.add_argument("--once", action="store_true", help="Process available jobs once and exit (jobs mode only).")
    args = parser.parse_args(argv)

    settings = WorkerSettings()
    stop = threading.Event()
    with suppress(KeyboardInterrupt):
        if args.once:
            client = build_client(settings)
            if client is None:
                return 2
            detector = build_detector(settings)
            processed = 0
            while True:
                job = claim_job(client, settings)
                if job is None:
                    break
                process_job(client, settings, detector, job)
                processed += 1
            logger.info("--once mode processed %d job(s).", processed)
            return 0

        threads: list[threading.Thread] = []
        if args.mode in ("jobs", "all"):
            threads.append(threading.Thread(target=jobs_loop, args=(settings, stop), daemon=True, name="jobs"))
        if args.mode in ("stream", "all"):
            threads.append(threading.Thread(target=stream_loop, args=(settings, stop), daemon=True, name="stream"))

        for thread in threads:
            thread.start()
        try:
            while any(thread.is_alive() for thread in threads):
                time.sleep(0.5)
        finally:
            stop.set()
            for thread in threads:
                thread.join(timeout=30)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())