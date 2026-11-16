"""Counting engine: connects to each camera locally, counts people with YOLO,
and POSTs ONLY the number to the cloud backend.

Key privacy property: a frame is read into memory, counted, and immediately
discarded. No frame is ever written to disk, shown, or transmitted.
"""

import os
import time
import random
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

# Put the detection library (ultralytics) in offline mode BEFORE it is imported:
# otherwise it does DNS "am I online?" lookups at import and sends anonymous usage
# analytics on every prediction. With this set, the only connection this program
# makes is to our dashboard (plus a one-time model download if the file is missing).
os.environ["YOLO_OFFLINE"] = "1"

import httpx

import config as _cfg
from config import get_settings

settings = get_settings()

# Official YOLOv8 weights, used only if the model file isn't already in this folder.
_MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/{name}"

# Rolling record of exactly what this machine sends out — used by the portal's
# "Outbound log" so IT can see with their own eyes that only numbers leave.
_outbound = deque(maxlen=100)
_outbound_lock = threading.Lock()


def record_outbound(entry: dict) -> None:
    with _outbound_lock:
        _outbound.appendleft(entry)


def get_outbound(limit: int = 50) -> list[dict]:
    with _outbound_lock:
        return list(_outbound)[:limit]

# YOLO is loaded lazily (and only once) the first time a real camera needs it,
# so the portal and "test" cameras work without torch installed.
_model = None
_model_lock = threading.Lock()
_infer_lock = threading.Lock()  # YOLO inference is not thread-safe; serialize it.

# COCO classes: 0 = person, 63 = laptop (used to detect reserved-but-empty seats)
_PERSON, _LAPTOP = 0, 63


def _model_path() -> Path:
    """Model file location — a bare name resolves against this folder, so it
    works whatever the working directory is (e.g. when started as a service)."""
    p = Path(settings.MODEL_NAME)
    return p if p.is_absolute() else Path(_cfg.BASE_DIR) / p


def _ensure_model_file(path: Path) -> None:
    """Download the official weights once if they aren't here yet."""
    if path.exists() and path.stat().st_size > 1_000_000:
        return
    url = _MODEL_URL.format(name=path.name)
    print(f"[counter] model file not found - downloading {path.name} once from {url}")
    tmp = path.with_suffix(path.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=180.0) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    tmp.replace(path)


def load_model():
    global _model
    with _model_lock:
        if _model is None:
            path = _model_path()
            _ensure_model_file(path)
            from ultralytics import YOLO
            _model = YOLO(str(path))
    return _model


# ── Reserved-seat geometry (ported from the original cv_camera.py) ───────────
def _edge_distance(obj_box, person_box):
    ox = (obj_box[0] + obj_box[2]) / 2
    oy = (obj_box[1] + obj_box[3]) / 2
    dx = max(person_box[0] - ox, 0, ox - person_box[2])
    dy = max(person_box[1] - oy, 0, oy - person_box[3])
    return (dx ** 2 + dy ** 2) ** 0.5


def _within_threshold(obj_box, person_box):
    oy = (obj_box[1] + obj_box[3]) / 2
    pw = person_box[2] - person_box[0]
    ph = person_box[3] - person_box[1]
    dist = _edge_distance(obj_box, person_box)
    if settings.CEILING_CAM:
        return dist < pw * 0.7
    if oy < person_box[1] - ph * 0.2:   # laptop well above the person → not at desk
        return False
    return dist < pw * 0.5


def count_reserved_seats(person_boxes: list, object_boxes: list) -> int:
    """Pure logic: laptops NOT claimed by any nearby person = reserved seats.

    One-to-one matching — each person claims only their single closest laptop, so
    one person sitting between two laptops can't absorb a neighbour's reserved seat.
    Separated from YOLO so it can be unit-tested without a model or a frame.
    """
    assigned: set[int] = set()
    for pb in person_boxes:
        best_idx, best_dist = None, float("inf")
        for i, lb in enumerate(object_boxes):
            if i in assigned or not _within_threshold(lb, pb):
                continue
            d = _edge_distance(lb, pb)
            if d < best_dist:
                best_dist, best_idx = d, i
        if best_idx is not None:
            assigned.add(best_idx)
    return len(object_boxes) - len(assigned)


def detect(frame, detect_reserved: bool = True) -> tuple[list, list]:
    """Run YOLO on one frame. Returns (person_boxes, laptop_boxes) as [x1,y1,x2,y2].

    Only box coordinates come out of here — the frame itself is not kept.
    """
    model = load_model()
    classes = [_PERSON, _LAPTOP] if detect_reserved else [_PERSON]
    with _infer_lock:
        results = model(
            frame, verbose=False, classes=classes, conf=settings.DETECT_CONFIDENCE
        )
    person_boxes, object_boxes = [], []
    for box in results[0].boxes:
        coords = [round(v, 1) for v in box.xyxy[0].tolist()]
        (person_boxes if int(box.cls[0]) == _PERSON else object_boxes).append(coords)
    return person_boxes, object_boxes


def count_people_and_reserved(frame, detect_reserved: bool = True) -> tuple[int, int]:
    """Return (people_count, reserved_seats). The frame is used only here."""
    person_boxes, object_boxes = detect(frame, detect_reserved)
    reserved = count_reserved_seats(person_boxes, object_boxes) if detect_reserved else 0
    return len(person_boxes), reserved


def send_count(client: httpx.Client, camera_id: str, count: int, reserved: int) -> tuple[bool, str, dict]:
    """POST one count to the cloud. Returns (ok, detail, body_sent).

    `body` is the ENTIRE payload that leaves the machine — only numbers and the
    camera id. Every send is recorded for the "What leaves this machine" view.
    """
    headers = {"X-API-Key": settings.DEVICE_API_KEY} if settings.DEVICE_API_KEY else {}
    body = {
        "camera_id": camera_id,
        "count": int(count),
        "reserved": int(reserved),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    sent_at = datetime.now().strftime("%H:%M:%S")
    try:
        r = client.post(
            f"{settings.BACKEND_URL.rstrip('/')}/count/update",
            json=body, headers=headers, timeout=10.0,
        )
        ok = r.status_code == 200
        detail = "200 OK" if ok else f"HTTP {r.status_code}"
    except Exception as exc:
        ok, detail = False, f"send failed: {exc}"
    record_outbound({"at": sent_at, "body": body, "ok": ok, "detail": detail})
    return ok, detail, body


def build_source(cam: dict):
    """Turn a stored camera record into something cv2.VideoCapture understands."""
    stype = cam.get("source_type")
    if stype == "webcam":
        return int(cam.get("webcam_index", 0))
    if stype == "test":
        return "test"
    host_path = cam.get("host_path", "").strip()
    user = cam.get("username", "")
    pwd = cam.get("password", "")
    scheme = "rtsp://"
    if host_path.startswith(("rtsp://", "http://", "https://")):
        scheme, host_path = host_path.split("://", 1)
        scheme += "://"
    if user:
        return f"{scheme}{user}:{pwd}@{host_path}"
    return f"{scheme}{host_path}"


class CameraWorker(threading.Thread):
    def __init__(self, cam: dict):
        super().__init__(daemon=True)
        self.cam = cam
        self.camera_id = cam["camera_id"]
        self._stop = threading.Event()
        self.status = {
            "camera_id": self.camera_id,
            "zone_name": cam.get("zone_name", self.camera_id),
            "online": False,
            "last_count": None,
            "last_reserved": None,
            "last_post_ok": None,
            "last_update": None,
            "error": None,
            "mode": cam.get("source_type"),
        }

    def stop(self):
        self._stop.set()

    # ── networking: only the number leaves the machine ──────────────────────
    def _post(self, client: httpx.Client, count: int, reserved: int) -> bool:
        ok, detail, _ = send_count(client, self.camera_id, count, reserved)
        self.status["last_post_ok"] = ok
        self.status["error"] = None if ok else detail
        return ok

    def _record(self, count, reserved):
        self.status["last_count"] = count
        self.status["last_reserved"] = reserved
        self.status["last_update"] = datetime.now().strftime("%H:%M:%S")

    def run(self):
        if self.cam.get("source_type") == "test":
            self._run_sim()
        else:
            self._run_camera()
        self.status["online"] = False

    def _run_camera(self):
        import cv2  # imported here so the portal runs even without OpenCV

        source = build_source(self.cam)
        detect_reserved = self.cam.get("detect_reserved", True)
        with httpx.Client() as client:
            while not self._stop.is_set():
                cap = cv2.VideoCapture(source)
                if not cap.isOpened():
                    self.status["online"] = False
                    self.status["error"] = "cannot open camera stream"
                    if self._stop.wait(5):
                        break
                    continue
                self.status["online"] = True
                self.status["error"] = None
                try:
                    while not self._stop.is_set():
                        ok, frame = cap.read()
                        if not ok:
                            self.status["online"] = False
                            self.status["error"] = "frame read failed — reconnecting"
                            break
                        try:
                            count, reserved = count_people_and_reserved(frame, detect_reserved)
                        except Exception as exc:
                            # Model missing/failed or inference error — stay alive, report it.
                            self.status["error"] = f"count failed: {exc}"
                            if self._stop.wait(settings.INFERENCE_INTERVAL):
                                break
                            continue
                        finally:
                            frame = None  # drop the frame immediately
                        self.status["error"] = None
                        self._post(client, count, reserved)
                        self._record(count, reserved)
                        if self._stop.wait(settings.INFERENCE_INTERVAL):
                            break
                finally:
                    cap.release()
                if not self._stop.is_set():
                    self._stop.wait(3)  # brief pause before reconnect

    def _run_sim(self):
        """No real camera — generates plausible numbers for demos / portal testing."""
        lo, hi, drift = 5, 60, 4
        count = random.randint(lo, hi)
        detect_reserved = self.cam.get("detect_reserved", True)
        with httpx.Client() as client:
            while not self._stop.is_set():
                count = max(lo, min(hi, count + random.randint(-drift, drift)))
                reserved = random.randint(0, 3) if detect_reserved else 0
                self.status["online"] = True
                self._post(client, count, reserved)
                self._record(count, reserved)
                if self._stop.wait(settings.INFERENCE_INTERVAL):
                    break


class Manager:
    """Owns the running workers. Start/stop cameras and report live status."""

    def __init__(self):
        self._workers: dict[str, CameraWorker] = {}
        self._lock = threading.RLock()

    def start_camera(self, cam: dict):
        with self._lock:
            self.stop_camera(cam["camera_id"])
            worker = CameraWorker(cam)
            self._workers[cam["camera_id"]] = worker
            worker.start()

    def stop_camera(self, camera_id: str):
        with self._lock:
            worker = self._workers.pop(camera_id, None)
        if worker:
            worker.stop()

    def start_all(self, cameras: list[dict]):
        for cam in cameras:
            if cam.get("enabled", True):
                self.start_camera(cam)

    def stop_all(self):
        with self._lock:
            ids = list(self._workers)
        for camera_id in ids:
            self.stop_camera(camera_id)

    def is_running(self, camera_id: str) -> bool:
        with self._lock:
            worker = self._workers.get(camera_id)
            return bool(worker and worker.is_alive())

    def status(self) -> dict[str, dict]:
        with self._lock:
            return {cid: dict(w.status) for cid, w in self._workers.items()}


manager = Manager()
