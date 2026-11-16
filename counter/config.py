"""Configuration for the on-premise counter.

All values come from a local `.env` file that stays on the institute's machine.
Nothing here is ever sent to the cloud except the counts themselves.
"""

import secrets
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # ── Cloud backend (where only the counts are sent) ──────────────────────
    BACKEND_URL: str = "http://localhost:8000"
    # Shared secret with the backend. MUST match the backend's DEVICE_API_KEY.
    DEVICE_API_KEY: str = ""

    # ── Local portal (runs only on this machine / LAN) ──────────────────────
    PORTAL_HOST: str = "127.0.0.1"   # 127.0.0.1 = this machine only. Use 0.0.0.0 for LAN access.
    PORTAL_PORT: int = 8900
    PORTAL_EMAIL: str = "it-admin@institute.edu"   # the IT login identity
    PORTAL_PASSWORD: str = ""                       # REQUIRED — set in .env
    SESSION_SECRET: str = ""                        # auto-generated if empty

    # ── Counting ────────────────────────────────────────────────────────────
    MODEL_NAME: str = "yolov8s.pt"
    INFERENCE_INTERVAL: int = 3        # seconds between counts
    CEILING_CAM: bool = False          # True if cameras are ceiling-mounted (top-down)
    DETECT_CONFIDENCE: float = 0.35    # YOLO min confidence (lower = more, noisier detections)

    # ── Login protection ─────────────────────────────────────────────────────
    LOGIN_MAX_ATTEMPTS: int = 5        # failed tries before a temporary lockout
    LOGIN_LOCKOUT_SECONDS: int = 300   # how long the lockout lasts
    SESSION_MAX_AGE: int = 28800       # portal session lifetime (8 hours)

    # ── Demo v1.0 (browser webcam) ──────────────────────────────────────────
    DEMO_PORT: int = 8901
    DEMO_CAMERA_ID: str = "cam_01"     # zone the demo counts for, by default

    # ── Local storage ───────────────────────────────────────────────────────
    DATA_DIR: str = str(BASE_DIR / "data")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> "Settings":
    s = Settings()
    data_dir = Path(s.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Persist an auto-generated session secret so logins survive restarts.
    if not s.SESSION_SECRET:
        secret_path = data_dir / "session.secret"
        if secret_path.exists():
            s.SESSION_SECRET = secret_path.read_text(encoding="utf-8").strip()
        else:
            s.SESSION_SECRET = secrets.token_hex(32)
            secret_path.write_text(s.SESSION_SECRET, encoding="utf-8")
    return s
