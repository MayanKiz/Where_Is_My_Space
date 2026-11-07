"""SQLite persistence for individual library seats and occupancy sessions."""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEAT_STATUSES = {"EMPTY", "OCCUPIED", "RESERVED"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SeatStore:
    def __init__(self, path: str | Path | None = None) -> None:
        default = Path(__file__).resolve().parents[1] / "data" / "wims.db"
        self.path = Path(path or os.getenv("WIMS_SQLITE_PATH", default))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialise(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS seats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL UNIQUE,
                    x1 REAL NOT NULL, y1 REAL NOT NULL,
                    x2 REAL NOT NULL, y2 REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'EMPTY'
                        CHECK (status IN ('EMPTY', 'OCCUPIED', 'RESERVED')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS seat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seat_id INTEGER NOT NULL REFERENCES seats(id) ON DELETE CASCADE,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_minutes REAL
                );
                CREATE INDEX IF NOT EXISTS seat_sessions_start_idx
                    ON seat_sessions(start_time);
                """
            )

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def list_seats(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as db:
            rows = db.execute("SELECT * FROM seats ORDER BY label").fetchall()
        return [self._row(row) for row in rows]

    def save_seats(self, seats: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = utcnow()
        with self._lock, self._connect() as db:
            for seat in seats:
                status = seat.get("status", "EMPTY")
                if status not in SEAT_STATUSES:
                    raise ValueError(f"Invalid seat status: {status}")
                values = (
                    seat["label"].strip(),
                    float(seat["x1"]),
                    float(seat["y1"]),
                    float(seat["x2"]),
                    float(seat["y2"]),
                    status,
                    seat.get("created_at") or now,
                )
                db.execute(
                    """
                    INSERT INTO seats(label, x1, y1, x2, y2, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(label) DO UPDATE SET
                        x1=excluded.x1, y1=excluded.y1, x2=excluded.x2,
                        y2=excluded.y2, status=excluded.status
                    """,
                    values,
                )
            labels = [seat["label"].strip() for seat in seats]
            if labels:
                placeholders = ",".join("?" for _ in labels)
                db.execute(
                    f"DELETE FROM seats WHERE label NOT IN ({placeholders})",
                    labels,
                )
            rows = db.execute("SELECT * FROM seats ORDER BY label").fetchall()
        return [self._row(row) for row in rows]

    def update_status(self, seat_id: int, status: str, at: str | None = None) -> dict[str, Any] | None:
        if status not in SEAT_STATUSES:
            raise ValueError(f"Invalid seat status: {status}")
        observed_at = at or utcnow()
        with self._lock, self._connect() as db:
            current = db.execute("SELECT * FROM seats WHERE id = ?", (seat_id,)).fetchone()
            if current is None:
                return None
            previous = current["status"]
            if previous == status:
                return self._row(current)
            if previous == "OCCUPIED":
                session = db.execute(
                    "SELECT id, start_time FROM seat_sessions WHERE seat_id = ? AND end_time IS NULL ORDER BY id DESC LIMIT 1",
                    (seat_id,),
                ).fetchone()
                if session:
                    start = datetime.fromisoformat(session["start_time"])
                    end = datetime.fromisoformat(observed_at)
                    duration = max(0.0, (end - start).total_seconds() / 60)
                    db.execute(
                        "UPDATE seat_sessions SET end_time = ?, duration_minutes = ? WHERE id = ?",
                        (observed_at, round(duration, 2), session["id"]),
                    )
            if status == "OCCUPIED":
                db.execute(
                    "INSERT INTO seat_sessions(seat_id, start_time) VALUES (?, ?)",
                    (seat_id, observed_at),
                )
            db.execute("UPDATE seats SET status = ? WHERE id = ?", (status, seat_id))
            row = db.execute("SELECT * FROM seats WHERE id = ?", (seat_id,)).fetchone()
        return self._row(row) if row else None

    def available_labels(self) -> list[str]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT label FROM seats WHERE status = 'EMPTY' ORDER BY label"
            ).fetchall()
        return [row["label"] for row in rows]

    def analytics(self) -> dict[str, Any]:
        with self._lock, self._connect() as db:
            counts = db.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN status = 'OCCUPIED' THEN 1 ELSE 0 END) AS occupied, "
                "SUM(CASE WHEN status = 'EMPTY' THEN 1 ELSE 0 END) AS empty "
                "FROM seats"
            ).fetchone()
            sessions = db.execute(
                "SELECT COUNT(*) AS count FROM seat_sessions "
                "WHERE date(start_time) = date('now', 'localtime')"
            ).fetchone()["count"]
        total = int(counts["total"] or 0)
        occupied = int(counts["occupied"] or 0)
        empty = int(counts["empty"] or 0)
        return {
            "total": total,
            "occupied": occupied,
            "empty": empty,
            "occupancy_rate": round(occupied / total, 4) if total else 0.0,
            "sessions_today": int(sessions),
        }

    def apply_statuses(self, statuses: dict[int, str], at: str | None = None) -> list[dict[str, Any]]:
        """Persist only changed statuses and return the resulting seat rows."""
        changed: list[dict[str, Any]] = []
        for seat_id, status in statuses.items():
            seat = self.update_status(seat_id, status, at=at)
            if seat is not None:
                changed.append(seat)
        return changed
