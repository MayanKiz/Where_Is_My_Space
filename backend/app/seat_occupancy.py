"""CPU-friendly seat occupancy state machine with lightweight ByteTrack-style IDs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.detector import Detection


def overlap_ratio(detection: Detection, seat: dict[str, float]) -> float:
    """Return bbox/seat overlap as a fraction of the seat rectangle."""
    left = max(detection.x1, seat["x1"])
    top = max(detection.y1, seat["y1"])
    right = min(detection.x2, seat["x2"])
    bottom = min(detection.y2, seat["y2"])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    seat_area = max(1.0, (seat["x2"] - seat["x1"]) * (seat["y2"] - seat["y1"]))
    return intersection / seat_area


def iou(first: Detection, second: Detection) -> float:
    left = max(first.x1, second.x1)
    top = max(first.y1, second.y1)
    right = min(first.x2, second.x2)
    bottom = min(first.y2, second.y2)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0, first.x2 - first.x1) * max(0, first.y2 - first.y1)
    second_area = max(0, second.x2 - second.x1) * max(0, second.y2 - second.y1)
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


@dataclass
class Track:
    track_id: int
    detection: Detection
    last_seen: float


class ByteTrackLite:
    """Greedy IoU tracker suitable for a single CPU camera stream."""

    def __init__(self, iou_threshold: float = 0.25, max_age: float = 1.5) -> None:
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self._next_id = 1
        self._tracks: dict[int, Track] = {}

    def update(self, detections: Iterable[Detection], timestamp: float) -> list[tuple[int, Detection]]:
        remaining = list(detections)
        results: list[tuple[int, Detection]] = []
        used: set[int] = set()
        for track_id, track in list(self._tracks.items()):
            if timestamp - track.last_seen > self.max_age:
                del self._tracks[track_id]
                continue
            best_index = -1
            best_score = self.iou_threshold
            for index, detection in enumerate(remaining):
                if index in used:
                    continue
                score = iou(track.detection, detection)
                if score >= best_score:
                    best_index, best_score = index, score
            if best_index >= 0:
                detection = remaining[best_index]
                used.add(best_index)
                track.detection = detection
                track.last_seen = timestamp
                results.append((track_id, detection))
        for index, detection in enumerate(remaining):
            if index in used:
                continue
            track_id = self._next_id
            self._next_id += 1
            self._tracks[track_id] = Track(track_id, detection, timestamp)
            results.append((track_id, detection))
        return results


class SeatOccupancyEngine:
    def __init__(self, *, occupied_after: float = 3.0, empty_after: float = 5.0) -> None:
        self.occupied_after = occupied_after
        self.empty_after = empty_after
        self.tracker = ByteTrackLite()
        self._presence_since: dict[int, float] = {}
        self._absence_since: dict[int, float] = {}
        self._status: dict[int, str] = {}

    def update(
        self,
        seats: Iterable[dict[str, float]],
        detections: Iterable[Detection],
        timestamp: float,
    ) -> dict[int, str]:
        tracked = self.tracker.update(detections, timestamp)
        result: dict[int, str] = {}
        for seat in seats:
            seat_id = int(seat["id"])
            status = self._status.get(seat_id, str(seat.get("status", "EMPTY")))
            overlapping = [
                (track_id, detection)
                for track_id, detection in tracked
                if overlap_ratio(detection, seat) > 0.40
            ]
            if overlapping:
                self._absence_since.pop(seat_id, None)
                self._presence_since.setdefault(seat_id, timestamp)
                if status != "RESERVED" and timestamp - self._presence_since[seat_id] >= self.occupied_after:
                    status = "OCCUPIED"
            else:
                self._presence_since.pop(seat_id, None)
                self._absence_since.setdefault(seat_id, timestamp)
                if status == "OCCUPIED" and timestamp - self._absence_since[seat_id] >= self.empty_after:
                    status = "EMPTY"
            self._status[seat_id] = status
            result[seat_id] = status
        return result
