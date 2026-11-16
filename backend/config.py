from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str = "change-this-to-a-random-64-char-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "bits2024"
    DATABASE_URL: str = "sqlite+aiosqlite:///./occupancy.db"
    CAMERA_OFFLINE_THRESHOLD_SECONDS: int = 12
    # Shared secret the on-prem counter must send in the X-API-Key header when
    # POSTing counts. Leave empty to disable the check (not recommended in prod).
    DEVICE_API_KEY: str = ""
    # Comma-separated list of browser origins allowed to call the API (CORS).
    # Set to your deployed frontend URL(s). "*" allows any origin (dev only).
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    # Admin-login brute-force protection.
    ADMIN_LOGIN_MAX_ATTEMPTS: int = 5
    ADMIN_LOGIN_LOCKOUT_SECONDS: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
