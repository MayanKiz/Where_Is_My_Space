from app.detector import Detection
from app.seat_occupancy import SeatOccupancyEngine, overlap_ratio
from app.seat_store import SeatStore


def test_seat_store_map_available_and_sessions(tmp_path):
    store = SeatStore(tmp_path / "seats.db")
    saved = store.save_seats([
        {"label": "S01", "x1": 0, "y1": 0, "x2": 100, "y2": 100},
        {"label": "S02", "x1": 120, "y1": 0, "x2": 220, "y2": 100},
    ])
    assert [seat["label"] for seat in saved] == ["S01", "S02"]
    assert store.available_labels() == ["S01", "S02"]
    store.update_status(saved[0]["id"], "OCCUPIED", "2026-01-01T10:00:00+00:00")
    store.update_status(saved[0]["id"], "EMPTY", "2026-01-01T10:10:00+00:00")
    assert store.analytics()["sessions_today"] == 0
    assert store.analytics()["occupied"] == 0


def test_occupancy_requires_overlap_and_dwell():
    seat = {"id": 1, "x1": 0, "y1": 0, "x2": 100, "y2": 100, "status": "EMPTY"}
    sitting = Detection(10, 10, 90, 90, 0.9, 0)
    passing = Detection(90, 0, 190, 100, 0.9, 0)
    assert overlap_ratio(sitting, seat) > 0.4
    assert overlap_ratio(passing, seat) <= 0.4
    engine = SeatOccupancyEngine()
    assert engine.update([seat], [sitting], 0)[1] == "EMPTY"
    assert engine.update([seat], [sitting], 2.9)[1] == "EMPTY"
    assert engine.update([seat], [sitting], 3.1)[1] == "OCCUPIED"
    assert engine.update([seat], [], 7.9)[1] == "OCCUPIED"
    assert engine.update([seat], [], 8.1)[1] == "OCCUPIED"
    assert engine.update([seat], [], 13.2)[1] == "EMPTY"
