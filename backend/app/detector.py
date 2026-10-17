"""YOLO person detection on top of OpenCV's DNN module with ONNX weights.

The detector supports both common export layouts:
  * YOLOv5 exports: output (1, N, 85) with an objectness column.
  * YOLOv8 exports: output (1, 84, N) without an objectness column.

Model weights are downloaded once to a local path and optionally pinned with
SHA-256 so a worker restart does not silently change the detector behind the
same version label.
"""

from __future__ import annotations

import hashlib
import logging
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("wims.detector")

PERSON_CLASS_ID = 0
INPUT_SIZE = 640
DEFAULT_MODEL_URL = (
    "https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx"
)


class ModelUnavailableError(RuntimeError):
    """Raised when the ONNX model cannot be downloaded or loaded."""


@dataclass(frozen=True)
class Detection:
    x1: int
    y1: int
    x2: int
    y2: int
    score: float
    class_id: int

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_model(path: Path, url: str = DEFAULT_MODEL_URL, sha256: str | None = None) -> Path:
    """Download the ONNX model once, verifying a pinned SHA-256 when provided."""
    if path.exists() and path.stat().st_size > 1_000_000:
        if sha256:
            actual = sha256_of(path)
            if actual.lower() != sha256.lower():
                raise ModelUnavailableError(
                    f"Model at {path} has SHA-256 {actual}, expected {sha256}. "
                    "Delete the file to re-download it."
                )
        return path

    if not url:
        raise ModelUnavailableError(f"No model found at {path} and no download URL configured.")

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".part")
    logger.info("Downloading YOLO model from %s to %s", url, path)
    try:
        with urllib.request.urlopen(url, timeout=60) as response, temp_path.open("wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise ModelUnavailableError(f"Could not download the YOLO model: {exc}") from exc

    if temp_path.stat().st_size < 1_000_000:
        temp_path.unlink(missing_ok=True)
        raise ModelUnavailableError("Downloaded model file is implausibly small.")

    if sha256:
        actual = sha256_of(temp_path)
        if actual.lower() != sha256.lower():
            temp_path.unlink(missing_ok=True)
            raise ModelUnavailableError(
                f"Downloaded model has SHA-256 {actual}, expected {sha256}."
            )

    temp_path.replace(path)
    return path


def letterbox(frame: np.ndarray, size: int = INPUT_SIZE) -> tuple[np.ndarray, float, int, int]:
    """Resize with aspect ratio preserved and pad to a square canvas."""
    height, width = frame.shape[:2]
    scale = min(size / width, size / height)
    new_w, new_h = max(1, round(width * scale)), max(1, round(height * scale))
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    pad_x = (size - new_w) // 2
    pad_y = (size - new_h) // 2
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
    return canvas, scale, pad_x, pad_y


def rows_from_output(output: np.ndarray) -> tuple[np.ndarray, str]:
    """Normalise raw network output to an (N, C) row-major array with its channel count."""
    array = np.asarray(output)
    array = np.squeeze(array)
    if array.ndim == 1 and array.size in (84, 85):
        return array.reshape(1, -1), str(array.size)
    if array.ndim != 2:
        raise ValueError(f"Unexpected YOLO output shape {array.shape}")
    rows, cols = array.shape
    if rows in (84, 85) and cols not in (84, 85):
        transposed = array.T
        return transposed, str(transposed.shape[1])
    if cols in (84, 85):
        return array, str(cols)
    # Already top-k detections in (N, 5+) form; treat conservatively as 85-layout.
    return array, str(cols)


def parse_detections(
    output: np.ndarray,
    scale: float,
    pad_x: int,
    pad_y: int,
    conf_threshold: float = 0.35,
    iou_threshold: float = 0.45,
) -> list[Detection]:
    """Decode raw YOLO output into image-space detections with NMS applied."""
    rows, cols_hint = rows_from_output(output)
    if rows.size == 0:
        return []

    scores_list: list[float] = []
    class_ids: list[int] = []
    boxes: list[list[int]] = []

    for row in rows:
        if row.size < 6:
            continue
        box = row[:4]
        if cols_hint == "85":
            objectness = float(row[4])
            class_scores = row[5:]
            if class_scores.size == 0:
                continue
            class_id = int(np.argmax(class_scores))
            score = objectness * float(class_scores[class_id])
        else:
            class_scores = row[4:]
            class_id = int(np.argmax(class_scores))
            score = float(class_scores[class_id])
        if score < conf_threshold:
            continue
        cx, cy, w, h = (float(v) for v in box)
        x1 = (cx - w / 2 - pad_x) / scale
        y1 = (cy - h / 2 - pad_y) / scale
        x2 = (cx + w / 2 - pad_x) / scale
        y2 = (cy + h / 2 - pad_y) / scale
        boxes.append([int(round(x1)), int(round(y1)), int(round(x2 - x1)), int(round(y2 - y1))])
        scores_list.append(round(score, 4))
        class_ids.append(class_id)

    if not boxes:
        return []

    keep = cv2.dnn.NMSBoxes(
        np.array(boxes, dtype=np.float32),
        np.array(scores_list, dtype=np.float32),
        conf_threshold,
        iou_threshold,
    )
    detections: list[Detection] = []
    indices = [] if keep is None else (keep.flatten() if hasattr(keep, "flatten") else list(keep))
    for index in indices:
        x, y, w, h = boxes[int(index)]
        if w <= 0 or h <= 0:
            continue
        detections.append(
            Detection(
                x1=max(0, x),
                y1=max(0, y),
                x2=max(0, x + w),
                y2=max(0, y + h),
                score=scores_list[int(index)],
                class_id=class_ids[int(index)],
            )
        )
    return detections


class YoloDetector:
    """OpenCV DNN wrapper around an ONNX YOLO model."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        url: str = DEFAULT_MODEL_URL,
        sha256: str | None = None,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        input_size: int = INPUT_SIZE,
    ) -> None:
        self.model_path = Path(model_path)
        self.url = url
        self.sha256 = sha256 or None
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.input_size = input_size
        self._net: cv2.dnn_Net | None = None

    @property
    def version(self) -> str:
        return self.model_path.name

    def load(self) -> None:
        if self._net is not None:
            return
        ensure_model(self.model_path, url=self.url, sha256=self.sha256)
        try:
            net = cv2.dnn.readNet(str(self.model_path))
        except cv2.error as exc:
            raise ModelUnavailableError(f"Could not load ONNX model {self.model_path}: {exc}") from exc
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self._net = net
        logger.info("Loaded YOLO model %s (input %d)", self.version, self.input_size)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        self.load()
        assert self._net is not None
        canvas, scale, pad_x, pad_y = letterbox(frame, self.input_size)
        blob = cv2.dnn.blobFromImage(canvas, 1 / 255.0, (self.input_size, self.input_size), swapRB=True)
        self._net.setInput(blob)
        output = self._net.forward()
        return parse_detections(
            output,
            scale,
            pad_x,
            pad_y,
            conf_threshold=self.conf_threshold,
            iou_threshold=self.iou_threshold,
        )

    def detect_persons(self, frame: np.ndarray) -> list[Detection]:
        return [d for d in self.detect(frame) if d.class_id == PERSON_CLASS_ID]


def draw_detections(frame: np.ndarray, detections: list[Detection], color: tuple[int, int, int]) -> np.ndarray:
    """Return a copy of the frame with bounding boxes and score labels drawn."""
    annotated = frame.copy()
    for det in detections:
        cv2.rectangle(annotated, (det.x1, det.y1), (det.x2, det.y2), color, 2)
        label = f"{det.score:.2f}"
        cv2.putText(
            annotated,
            label,
            (det.x1, max(12, det.y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
    return annotated