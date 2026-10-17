"""Occupancy estimation from person detections and configured zone polygons.

Estimates are derived from sampled frames of an analysed clip:
  * persons whose bounding-box centre falls inside the configured zone polygon
    count toward occupancy (or all persons when the zone has no polygon yet).
  * the reported occupied value for a clip is the *peak* count observed, since a
    lower later count may reflect people leaving the frame rather than leaving.
Confidence is tracked separately from the count: a count with weak detections is
not presented as an exact number.

This module is deliberately free of OpenCV/model imports so it can be unit
tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


Point = tuple[float, float]
Polygon = list[Point]


def point_in_polygon(x: float, y: float, polygon: Polygon) -> bool:
    """Ray-casting point-in-polygon test (vertices on the edge count as inside)."""
    if len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        # Collinear/on-segment check.
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if abs(cross) < 1e-9 and min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9 and min(y1, y2) - 1e-9 <= y <= max(y1, y2) + 1e-9:
            return True
        if (y1 > y) != (y2 > y):
            x_at_y = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_at_y:
                inside = not inside
    return inside


def polygon_to_pixels(polygon_norm: Polygon, width: int, height: int) -> Polygon:
    """Convert normalised 0..1 polygon coordinates to pixel coordinates."""
    return [(nx * width, ny * height) for nx, ny in polygon_norm]


def normalize_polygon(value: object) -> Polygon | None:
    """Validate a JSONB polygon ([[x,y],...] in 0..1 space) or return None."""
    if not isinstance(value, list) or len(value) < 3:
        return None
    points: Polygon = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            return None
        try:
            x, y = float(item[0]), float(item[1])
        except (TypeError, ValueError):
            return None
        if not (-0.5 <= x <= 1.5 and -0.5 <= y <= 1.5):
            return None
        points.append((x, y))
    return points


def availability_status(occupied: int, capacity: int | None) -> str:
    """Human-readable availability label used by the API and dashboard."""
    if capacity is None or capacity <= 0:
        return "Unknown"
    remaining = max(capacity - occupied, 0)
    if remaining == 0:
        return "Full"
    if occupied / capacity >= 0.75:
        return "Busy"
    if occupied == 0:
        return "Available"
    return "Available" if occupied / capacity < 0.5 else "Filling up"


@dataclass
class OccupancyTracker:
    """Accumulates per-frame zone counts into a clip-level occupancy estimate."""

    zone_counts: list[int] = field(default_factory=list)
    all_counts: list[int] = field(default_factory=list)
    confidences: list[float] = field(default_factory=list)

    def add_sample(self, occupied_in_zone: int, total_persons: int, scores: list[float]) -> None:
        self.zone_counts.append(occupied_in_zone)
        self.all_counts.append(total_persons)
        self.confidences.extend(scores)

    @property
    def peak_occupied(self) -> int:
        return max(self.zone_counts) if self.zone_counts else 0

    @property
    def peak_total(self) -> int:
        return max(self.all_counts) if self.all_counts else 0

    @property
    def mean_occupied(self) -> float:
        if not self.zone_counts:
            return 0.0
        return round(sum(self.zone_counts) / len(self.zone_counts), 2)

    @property
    def mean_confidence(self) -> float | None:
        if not self.confidences:
            return None
        return round(sum(self.confidences) / len(self.confidences), 4)

    def status_for(self, capacity: int | None, available_threshold: int = 3) -> str:
        """Human-readable availability label for API/dashboard consumers."""
        return availability_status(self.peak_occupied, capacity)


def estimate_zone_occupancy(
    person_centers: list[Point],
    polygon_px: Polygon | None,
) -> int:
    """Count persons whose centre falls inside the zone polygon (all if none)."""
    if polygon_px is None or len(polygon_px) < 3:
        return len(person_centers)
    return sum(1 for x, y in person_centers if point_in_polygon(x, y, polygon_px))