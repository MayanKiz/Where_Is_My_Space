"""Unit tests for the WIMS backend: occupancy maths, rate limiting, YOLO decoding,
and the worker's video analysis pass (with a stub detector and a synthetic clip)."""

from __future__ import annotations

import numpy as np
import pytest

from app.detector import Detection, letterbox, parse_detections, rows_from_output
from app.occupancy import (
    OccupancyTracker,
    availability_status,
    estimate_zone_occupancy,
    normalize_polygon,
    point_in_polygon,
    polygon_to_pixels,
)
from app.ratelimit import SlidingWindowLimiter

# --------------------------------------------------------------------------- #
# Occupancy geometry
# --------------------------------------------------------------------------- #

SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
LEFT_HALF = [(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)]
CONCAVE = [(0.0, 0.0), (0.5, 0.3), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def test_point_in_polygon_square():
    assert point_in_polygon(0.5, 0.5, SQUARE)
    assert not point_in_polygon(1.5, 0.5, SQUARE)
    assert not point_in_polygon(-0.1, 0.5, SQUARE)


def test_point_in_polygon_concave_notch():
    # The notch apex at (0.5, 0.3): a point just below it is outside the shape.
    assert not point_in_polygon(0.5, 0.2, CONCAVE)
    assert point_in_polygon(0.5, 0.6, CONCAVE)


def test_point_in_polygon_edge_counts_inside():
    assert point_in_polygon(0.0, 0.5, SQUARE)  # on the left edge


def test_point_in_polygon_too_small_polygon():
    assert not point_in_polygon(0.5, 0.5, [(0.0, 0.0), (1.0, 1.0)])


def test_polygon_to_pixels_and_normalize_roundtrip():
    px = polygon_to_pixels(SQUARE, 640, 480)
    assert px[1] == (640.0, 0.0)
    assert normalize_polygon([list(p) for p in SQUARE]) is not None
    assert normalize_polygon([[0, 0], [1, 1]]) is None  # fewer than 3 points
    assert normalize_polygon(["a", "b", "c"]) is None
    assert normalize_polygon([0, 1, 2]) is None
    assert normalize_polygon([[5.0, 5.0], [0.1, 0.1], [0.2, 0.2]]) is None  # out of range
    assert normalize_polygon([[-0.01, 0.1], [0.5, 0.1], [0.5, 0.5]]) is None
    assert normalize_polygon([[0.1, 0.1], [1.01, 0.1], [0.5, 0.5]]) is None


def test_estimate_zone_occupancy_with_and_without_polygon():
    centers = [(0.2, 0.5), (0.8, 0.5), (0.4, 0.9)]
    assert estimate_zone_occupancy(centers, None) == 3  # no polygon: all persons
    px = polygon_to_pixels(LEFT_HALF, 100, 100)
    assert estimate_zone_occupancy([(20, 50), (80, 50), (40, 90)], px) == 2


def test_tracker_peak_and_confidence():
    tracker = OccupancyTracker()
    tracker.add_sample(2, 3, [0.9, 0.8])
    tracker.add_sample(5, 5, [0.7])
    tracker.add_sample(1, 2, [0.6])
    assert tracker.peak_occupied == 5  # peak, not last sample
    assert tracker.peak_total == 5
    assert tracker.mean_occupied == pytest.approx(2.67, abs=0.01)
    assert tracker.mean_confidence == pytest.approx(0.75, abs=0.01)
    empty = OccupancyTracker()
    assert empty.peak_occupied == 0
    assert empty.mean_confidence is None


def test_availability_status_labels():
    assert availability_status(0, 10) == "Available"
    assert availability_status(3, 10) == "Available"
    assert availability_status(5, 10) == "Filling up"
    assert availability_status(8, 10) == "Busy"
    assert availability_status(10, 10) == "Full"
    assert availability_status(3, None) == "Unknown"
    assert availability_status(3, 0) == "Unknown"


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #


def test_rate_limiter_allows_then_blocks():
    now = [0.0]
    limiter = SlidingWindowLimiter(window_seconds=60, max_events=3, clock=lambda: now[0])
    assert all(limiter.allow("ip-1") for _ in range(3))
    assert not limiter.allow("ip-1")
    assert limiter.allow("ip-2")  # independent key
    assert limiter.remaining("ip-1") == 0


def test_rate_limiter_window_slides():
    now = [0.0]
    limiter = SlidingWindowLimiter(window_seconds=60, max_events=2, clock=lambda: now[0])
    assert limiter.allow("k") and limiter.allow("k")
    assert not limiter.allow("k")
    now[0] += 61
    assert limiter.allow("k")  # old events fall out of the window


# --------------------------------------------------------------------------- #
# YOLO output decoding
# --------------------------------------------------------------------------- #


def _v5_row(cx, cy, w, h, obj, class_id, num_classes=80):
    row = np.zeros(5 + num_classes, dtype=np.float32)
    row[:4] = cx, cy, w, h
    row[4] = obj
    row[5 + class_id] = 1.0
    return row


def test_rows_from_output_layouts():
    v5 = np.zeros((1, 100, 85), dtype=np.float32)
    rows, cols = rows_from_output(v5)
    assert rows.shape == (100, 85) and cols == "85"

    v8 = np.zeros((1, 84, 200), dtype=np.float32)
    rows, cols = rows_from_output(v8)
    assert rows.shape == (200, 84) and cols == "84"

    single = np.zeros((1, 1, 85), dtype=np.float32)
    rows, cols = rows_from_output(single)
    assert rows.shape == (1, 85) and cols == "85"


def test_parse_v5_detection_and_background_filter():
    # Identity transform: scale=1, pad=0 → image coords == network coords.
    row = _v5_row(cx=100, cy=100, w=40, h=40, obj=0.9, class_id=0)  # person
    background = _v5_row(cx=300, cy=300, w=40, h=40, obj=0.9, class_id=7)
    low_conf = _v5_row(cx=100, cy=100, w=40, h=40, obj=0.1, class_id=0)
    output = np.stack([row, background, low_conf])[None, ...]

    detections = parse_detections(output, scale=1.0, pad_x=0, pad_y=0, conf_threshold=0.35)
    assert len(detections) == 2  # low-confidence row dropped
    person = next(d for d in detections if d.class_id == 0)
    assert (person.x1, person.y1) == (80, 80)
    assert (person.x2, person.y2) == (120, 120)
    assert person.score == pytest.approx(0.9, abs=0.01)


def test_parse_v8_layout_no_objectness():
    # (1, 84, N) layout: 4 box values + 80 class scores, no objectness column.
    rows = np.zeros((2, 84), dtype=np.float32)
    rows[0, :4] = 50, 50, 20, 20
    rows[0, 4 + 0] = 0.8
    rows[1, :4] = 400, 400, 30, 30
    rows[1, 4 + 3] = 0.5
    output = rows.T[None, ...]
    detections = parse_detections(output, scale=1.0, pad_x=0, pad_y=0, conf_threshold=0.35)
    assert sorted(d.class_id for d in detections) == [0, 3]


def test_letterbox_preserves_aspect_ratio():
    frame = np.zeros((100, 400, 3), dtype=np.uint8)
    canvas, scale, pad_x, pad_y = letterbox(frame, 640)
    assert canvas.shape == (640, 640, 3)
    assert scale == pytest.approx(640 / 400)
    assert pad_x == 0 and pad_y > 0  # wide frame: vertical padding


# --------------------------------------------------------------------------- #
# Worker video analysis (stub detector + synthetic clip)
# --------------------------------------------------------------------------- #


class StubDetector:
    """Returns two fixed person detections regardless of frame content."""

    version = "stub-detector"

    def detect_persons(self, frame):
        return [
            Detection(10, 10, 50, 80, 0.9, 0),
            Detection(200, 10, 260, 90, 0.7, 0),
        ]


@pytest.fixture()
def synthetic_video(tmp_path):
    cv2 = pytest.importorskip("cv2")
    path = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    if not writer.isOpened():
        pytest.skip("mp4v encoder unavailable in this OpenCV build")
    for i in range(25):
        frame = np.full((240, 320, 3), 40, dtype=np.uint8)
        cv2.rectangle(frame, (10 + i, 10), (50 + i, 80), (230, 230, 230), -1)
        writer.write(frame)
    writer.release()
    return path


def test_analyse_video_with_stub_detector(synthetic_video):
    from app.worker import analyse_video

    result = analyse_video(
        synthetic_video,
        StubDetector(),
        zone_polygon_px=None,
        frame_stride=5,
        max_sampled_frames=10,
        preview_width=320,
    )
    assert result.frames_total == 25
    assert result.frames_sampled == 5  # frames 0,5,10,15,20
    assert result.tracker.peak_occupied == 2
    assert result.tracker.mean_confidence == pytest.approx(0.8, abs=0.01)
    assert result.annotated_jpeg is not None and result.annotated_jpeg[:2] == b"\xff\xd8"  # JPEG SOI
    payload = result.as_dict()
    assert payload["persons_peak"] == 2
    assert payload["detection_confidence"] == pytest.approx(0.8, abs=0.01)


def test_analyse_video_with_normalised_zone_adapter(synthetic_video):
    from app.worker import _analyse_with_normalised_polygon

    left_half = [(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)]
    result = _analyse_with_normalised_polygon(
        synthetic_video,
        StubDetector(),
        zone_polygon_norm=left_half,
        frame_stride=5,
        max_sampled_frames=10,
        preview_width=320,
    )
    assert result.frames_sampled == 5
    assert result.tracker.peak_occupied == 1  # only the left-side detection counts
    assert result.tracker.peak_total == 2


def test_analyse_video_rejects_missing_file(tmp_path):
    from app.worker import analyse_video

    with pytest.raises(RuntimeError, match="VIDEO_UNREADABLE"):
        analyse_video(
            tmp_path / "absent.mp4",
            StubDetector(),
            zone_polygon_px=None,
            frame_stride=5,
            max_sampled_frames=10,
            preview_width=320,
        )


def test_worker_settings_defaults():
    from app.worker import WorkerSettings

    settings = WorkerSettings(_env_file=None)
    assert settings.supabase_video_bucket == "wims-temporary-videos"
    assert settings.supabase_preview_bucket == "wims-job-previews"
    assert settings.stale_claim_minutes >= 1
    assert settings.detection_confidence > 0
