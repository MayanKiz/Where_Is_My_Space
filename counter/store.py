"""Encrypted-at-rest storage for camera credentials.

Camera links and passwords are written to `data/cameras.enc`, encrypted with a
key kept in `data/secret.key`. Both files live only on this machine. The running
program must decrypt them to connect to the cameras (this is unavoidable for any
software that opens a stream) — but nothing is ever stored in plain text on disk
and nothing leaves the machine.

Each camera record:
    {
      "camera_id":       "cam_02",             # MUST match the cloud region's camera_id
      "zone_name":       "Main Reading Hall",   # human label, shown in the portal
      "source_type":     "rtsp" | "webcam" | "test",
      "host_path":       "192.168.1.50:554/Streaming/Channels/101",  # rtsp only
      "username":        "...",                  # rtsp only
      "password":        "...",                  # rtsp only
      "webcam_index":    0,                       # webcam only
      "detect_reserved": true,                    # count laptops-on-empty-seats as reserved
      "enabled":         true
    }
"""

import os
import json
import hmac
import hashlib
import secrets
import threading
from pathlib import Path

from cryptography.fernet import Fernet

from config import get_settings

_settings = get_settings()
_DATA = Path(_settings.DATA_DIR)
_KEY_FILE = _DATA / "secret.key"
_ENC_FILE = _DATA / "cameras.enc"
_AUTH_FILE = _DATA / "portal_auth.json"
_lock = threading.RLock()


def _restrict(path: Path) -> None:
    """Best-effort tighten file permissions (no-op on filesystems that ignore it)."""
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def _fernet() -> Fernet:
    with _lock:
        if _KEY_FILE.exists():
            key = _KEY_FILE.read_bytes()
        else:
            key = Fernet.generate_key()
            _KEY_FILE.write_bytes(key)
            _restrict(_KEY_FILE)
        return Fernet(key)


def load_cameras() -> list[dict]:
    with _lock:
        if not _ENC_FILE.exists():
            return []
        try:
            raw = _fernet().decrypt(_ENC_FILE.read_bytes())
            return json.loads(raw)
        except Exception:
            # Corrupt or key-mismatched file — fail safe to empty rather than crash.
            return []


def save_cameras(cameras: list[dict]) -> None:
    with _lock:
        token = _fernet().encrypt(json.dumps(cameras).encode("utf-8"))
        _ENC_FILE.write_bytes(token)
        _restrict(_ENC_FILE)


def get_camera(camera_id: str) -> dict | None:
    return next((c for c in load_cameras() if c["camera_id"] == camera_id), None)


def upsert_camera(cam: dict) -> None:
    with _lock:
        cams = load_cameras()
        for i, existing in enumerate(cams):
            if existing["camera_id"] == cam["camera_id"]:
                cams[i] = cam
                break
        else:
            cams.append(cam)
        save_cameras(cams)


def delete_camera(camera_id: str) -> None:
    with _lock:
        cams = [c for c in load_cameras() if c["camera_id"] != camera_id]
        save_cameras(cams)


# ── portal login credentials (changeable from the portal) ────────────────────
# Stored as a PBKDF2 hash, not the password itself. If this file is absent the
# portal falls back to PORTAL_EMAIL / PORTAL_PASSWORD from .env (the initial login).
def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000)
    return dk.hex()


def load_auth() -> dict | None:
    with _lock:
        if not _AUTH_FILE.exists():
            return None
        try:
            return json.loads(_AUTH_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None


def save_auth(email: str, password: str) -> None:
    salt = secrets.token_hex(16)
    record = {"email": email.strip().lower(), "salt": salt, "hash": _hash_password(password, salt)}
    with _lock:
        _AUTH_FILE.write_text(json.dumps(record), encoding="utf-8")
        _restrict(_AUTH_FILE)


def verify_auth(email: str, password: str) -> bool:
    """Check against the stored (changed) credentials. Returns False if none set."""
    auth = load_auth()
    if not auth:
        return False
    email_ok = hmac.compare_digest(email.strip().lower(), auth["email"])
    pass_ok = hmac.compare_digest(_hash_password(password, auth["salt"]), auth["hash"])
    return email_ok and pass_ok
