"""Local WIMS laptop-webcam demo: live YOLO person detection.

Run from the backend directory:
    python live_webcam.py

Press Q or Esc in the preview window to stop.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import cv2

from app.detector import ModelUnavailableError, YoloDetector, draw_detections

MODEL_URL = "https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx"
MODEL_SHA256 = "8bc25a47abdbe2fd23e30eb948746bf856b031ea3cc815166687f52db9f8c659"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Count people from a live laptop webcam.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0).")
    parser.add_argument(
        "--model-path",
        default="models/yolov5s.onnx",
        help="Path to the YOLOv5 ONNX model, downloaded on first run if missing.",
    )
    parser.add_argument("--confidence", type=float, default=0.35, help="Detection confidence threshold.")
    parser.add_argument("--width", type=int, default=960, help="Maximum preview width.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
    cv2.namedWindow("Where Is My Space - Live People Count", cv2.WINDOW_NORMAL)
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

            now = time.perf_counter()
            elapsed = now - previous_time
            previous_time = now
            if elapsed > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / elapsed) if fps else 1.0 / elapsed

            preview = draw_detections(frame, detections, color=(0, 220, 80))
            cv2.rectangle(preview, (10, 10), (360, 82), (20, 20, 20), -1)
            cv2.putText(
                preview,
                f"People detected: {len(detections)}",
                (22, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                preview,
                f"Live demo | {fps:.1f} FPS | press Q to quit",
                (22, 68),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (210, 230, 210),
                1,
                cv2.LINE_AA,
            )
            cv2.imshow("Where Is My Space - Live People Count", preview)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
