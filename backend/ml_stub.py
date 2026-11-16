"""
Mock camera feed simulator — run alongside the backend for development.

    python ml_stub.py

━━━ HOW REAL YOLO CONNECTS ━━━
After each frame inference, POST to /count/update:

    POST http://localhost:8000/count/update
    { "camera_id": "cam_01", "count": 14 }

camera_id must match a Region's camera_id in the DB (configured in Admin Panel).
That's the entire integration contract. Nothing else changes.
"""

import asyncio
import random
import httpx
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"
MOCK_CAMERAS = {
    "cam_01": {"range": (0, 40),  "drift": 2},
    "cam_02": {"range": (10, 80), "drift": 5},
    "cam_03": {"range": (5, 30),  "drift": 3},
    "cam_04": {"range": (0, 25),  "drift": 2},
}
counts = {k: random.randint(*v["range"]) for k, v in MOCK_CAMERAS.items()}


async def simulate():
    async with httpx.AsyncClient() as client:
        while True:
            for cam_id, cfg in MOCK_CAMERAS.items():
                lo, hi, d = *cfg["range"], cfg["drift"]
                counts[cam_id] = max(lo, min(hi, counts[cam_id] + random.randint(-d, d)))
                try:
                    r = await client.post(
                        f"{BASE_URL}/count/update",
                        json={
                            "camera_id": cam_id,
                            "count": counts[cam_id],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    print(f"[{cam_id}] count={counts[cam_id]:>3}  status={r.status_code}")
                except Exception as e:
                    print(f"[{cam_id}] ERROR: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(simulate())
