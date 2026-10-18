"""Local WIMS laptop-webcam demo: live people detection and seat-zone estimate.

Run from the backend directory:
    python live_webcam.py

Controls:
    P       start/stop drawing a seating-zone polygon
    Left click adds a corner while polygon editing is active
    Right click removes the last corner while editing
    C       clear the seating zone
    Q / Esc quit

A person inside the drawn zone is an occupancy estimate, not proof that a
specific physical chair is occupied. Set --capacity to the seating capacity.
"""

from __future__ import annotations

import argparse
import logging
import time

import cv2
import numpy as np

from app.detector import ModelUnavailableError, YoloDetector, draw_detections

MODEL_URL = "https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx"
MODEL_SHA256 = "8bc25a47abdbe2fd23e30eb948746bf856b031ea3cc815166687f52db9f8c659"
WINDOW_NAME = "Where Is My Space - Live Occupancy"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live webcam people counting and seating-zone estimate.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0).")
    parser.add_argument("--model-path", default="models/yolov5s.onnx", help="YOLO ONNX model path.")
    parser.add_argument("--confidence", type=float, default=0.35, help="Detection confidence threshold.")
    parser.add_argument("--width", type=int, default=960, help="Requested camera frame width.")
    parser.add_argument("--capacity", type=int, default=20, help="Number of seats in the selected zone.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.capacity < 1:
        raise SystemExit("--capacity must be at least 1.")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    detector = YoloDetector(
        args.model_path,
        url=MODEL_URL,
        sha256=MODEL_SHA256,
        conf_threshold=args.confidence,
    )
    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        camera.release()
        raise SystemExit(
            f"Could not open camera index {args.camera}. Close other camera apps or try --camera 1."
        )

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    state: dict[str, object] = {"points": [], "editing": False}

    def on_mouse(event: int, x: int, y: int, _flags: int, _userdata: object) -> None:
        points = state["points"]
        if not isinstance(points, list) or not state["editing"]:
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))
        elif event == cv2.EVENT_RBUTTONDOWN and points:
            points.pop()

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)
    previous_time = time.perf_counter()
    fps = 0.0

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                logging.warning("No frame received from the camera; retrying.")
                if cv2.waitKey(100) & 0xFF in (ord("q"), 27):
                    break
                continue

            try:
                detections = detector.detect_persons(frame)
            except ModelUnavailableError as exc:
                raise SystemExit(f"YOLO model is unavailable: {exc}") from exc

            points = state["points"]
            assert isinstance(points, list)
            zone = np.array(points, dtype=np.int32) if len(points) >= 3 else None
            zone_detections = detections
            if zone is not None:
                zone_detections = [
                    detection
                    for detection in detections
                    if cv2.pointPolygonTest(
                        zone.astype(np.float32),
                        (float((detection.x1 + detection.x2) / 2), float(detection.y2)),
                        False,
                    ) >= 0
                ]

            now = time.perf_counter()
            elapsed = now - previous_time
            previous_time = now
            if elapsed > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / elapsed) if fps else 1.0 / elapsed

            preview = draw_detections(frame, detections, color=(0, 220, 80))
            if len(points) >= 1:
                for point in points:
                    cv2.circle(preview, point, 5, (255, 180, 0), -1)
                if len(points) >= 2:
                    cv2.polylines(
                        preview,
                        [np.array(points, dtype=np.int32)],
                        bool(zone is not None and not state["editing"]),
                        (255, 180, 0),
                        2,
                    )

            cv2.rectangle(preview, (10, 10), (560, 125), (20, 20, 20), -1)
            cv2.putText(preview, f"People detected: {len(detections)}", (22, 39),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2, cv2.LINE_AA)
            if zone is not None:
                occupied = len(zone_detections)
                remaining = max(0, args.capacity - occupied)
                cv2.putText(preview, f"People in seat zone: {occupied}", (22, 67),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 220, 150), 2, cv2.LINE_AA)
                cv2.putText(preview, f"Capacity: {args.capacity} | Estimated seats remaining: {remaining}",
                            (22, 94), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (210, 255, 210), 1, cv2.LINE_AA)
            else:
                cv2.putText(preview, "Seat zone: press P, then click 3+ corners",
                            (22, 69), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 220, 150), 1, cv2.LINE_AA)
            hint = "DRAWING ZONE" if state["editing"] else "P: edit zone | C: clear | Q: quit"
            cv2.putText(preview, f"{hint} | {fps:.1f} FPS", (22, 115),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)

            cv2.imshow(WINDOW_NAME, preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("p"):
                state["editing"] = not state["editing"]
            elif key == ord("c"):
                state["points"] = []
                state["editing"] = False
    finally:
        camera.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
