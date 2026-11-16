import hmac
import time
import threading

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from auth import get_current_admin, create_access_token
from schemas import TokenResponse
from config import get_settings

router = APIRouter()
settings = get_settings()

# ── in-memory login throttle (per client IP) ─────────────────────────────────
_fails: dict[str, tuple[int, float]] = {}
_fails_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _lockout_remaining(ip: str) -> int:
    with _fails_lock:
        entry = _fails.get(ip)
        if not entry:
            return 0
        count, first_ts = entry
        if count < settings.ADMIN_LOGIN_MAX_ATTEMPTS:
            return 0
        elapsed = time.time() - first_ts
        if elapsed >= settings.ADMIN_LOGIN_LOCKOUT_SECONDS:
            _fails.pop(ip, None)
            return 0
        return int(settings.ADMIN_LOGIN_LOCKOUT_SECONDS - elapsed)


def _record_fail(ip: str) -> None:
    with _fails_lock:
        count, first_ts = _fails.get(ip, (0, time.time()))
        if time.time() - first_ts >= settings.ADMIN_LOGIN_LOCKOUT_SECONDS:
            count, first_ts = 0, time.time()
        _fails[ip] = (count + 1, first_ts)


def _clear_fails(ip: str) -> None:
    with _fails_lock:
        _fails.pop(ip, None)


class LoginPayload(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginPayload, request: Request):
    ip = _client_ip(request)
    remaining = _lockout_remaining(ip)
    if remaining:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Try again in about {(remaining + 59) // 60} minute(s).",
        )
    # constant-time comparison to avoid timing side-channels
    user_ok = hmac.compare_digest(payload.username, settings.ADMIN_USERNAME)
    pass_ok = hmac.compare_digest(payload.password, settings.ADMIN_PASSWORD)
    if not (user_ok and pass_ok):
        _record_fail(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    _clear_fails(ip)
    token = create_access_token({"sub": payload.username})
    return TokenResponse(access_token=token)


@router.get("/me")
async def get_me(username: str = Depends(get_current_admin)):
    return {"username": username}
