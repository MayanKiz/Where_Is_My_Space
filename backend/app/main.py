from __future__ import annotations

import asyncio
import logging
import os
import secrets
import tempfile
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field as PydanticField
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.concurrency import run_in_threadpool
from supabase import Client, create_client

from app.assistant import AssistantSettings, answer as answer_assistant
from app.occupancy import availability_status, normalize_polygon
from app.ratelimit import SlidingWindowLimiter

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("wims.api")

VIDEO_BUCKET = "wims-temporary-videos"
PREVIEW_BUCKET = "wims-job-previews"
MP4_SIGNATURE = b"ftyp"
WEBM_SIGNATURE = b"\x1aE\xdf\xa3"
CHUNK_SIZE = 1024 * 1024
SOURCE_COLUMNS = "id,name,source_type,status,device_label,location_id,zone_id,metadata,last_seen_at,created_at,updated_at"
ZONE_COLUMNS = "id,location_id,slug,name,description,capacity,polygon,is_active,is_public,created_at"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_video_bucket: str = VIDEO_BUCKET
    cors_origins: str = "http://localhost:3000"
    max_upload_mib: int = PydanticField(default=100, ge=1, le=512)
    upload_ttl_minutes: int = PydanticField(default=30, ge=5, le=1440)
    temp_upload_dir: str = "/tmp/wims-upload-staging"
    supabase_preview_bucket: str = PREVIEW_BUCKET
    rate_limit_per_minute: int = PydanticField(default=120, ge=1, le=10000)
    upload_rate_limit_per_minute: int = PydanticField(default=10, ge=1, le=1000)
    capture_access_code: str | None = None
    source_encryption_key: str | None = None
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "amazon.nova-lite-v1:0"
    bedrock_enabled: bool = False

    @property
    def upload_limit_bytes(self) -> int:
        return self.max_upload_mib * 1024 * 1024

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()


def build_supabase_client(config: Settings) -> Client | None:
    if not config.supabase_url or not config.supabase_service_role_key:
        logger.warning("Supabase server credentials are not configured; data routes will return 503.")
        return None
    try:
        return create_client(config.supabase_url, config.supabase_service_role_key)
    except Exception:
        logger.exception("Could not initialize the Supabase client.")
        return None


def require_supabase(request: Request) -> Client:
    client = getattr(request.app.state, "supabase", None)
    if client is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SUPABASE_NOT_CONFIGURED",
                "message": "The server has not been configured with Supabase credentials.",
            },
        )
    return client


async def require_capture_access(
    request: Request,
    x_wims_capture_key: str | None = Header(default=None, alias="X-WIMS-Capture-Key"),
) -> None:
    """A shared beta pairing code, not a user account or authentication system."""
    config: Settings = request.app.state.settings
    if not config.capture_access_code:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "CAPTURE_ACCESS_NOT_CONFIGURED",
                "message": "The WIMS Capture access code has not been configured by the project owner.",
            },
        )
    if not x_wims_capture_key or not secrets.compare_digest(x_wims_capture_key, config.capture_access_code):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_CAPTURE_CODE",
                "message": "Enter the valid WIMS Capture access code to continue.",
            },
        )


def get_fernet(config: Settings) -> Fernet:
    if not config.source_encryption_key:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SOURCE_ENCRYPTION_NOT_CONFIGURED",
                "message": "Secure RTSP camera registration is not configured on this server.",
            },
        )
    try:
        return Fernet(config.source_encryption_key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        logger.error("WIMS_SOURCE_ENCRYPTION_KEY is not a valid Fernet key.")
        raise HTTPException(status_code=503, detail="RTSP source encryption is misconfigured on the server.") from exc


def remove_storage_object(client: Client, bucket: str, path: str) -> None:
    client.storage.from_(bucket).remove([path])


def clean_expired_uploads(client: Client, config: Settings) -> int:
    """Delete expired private video objects; keep derived metadata and job history."""
    now = datetime.now(timezone.utc).isoformat()
    response = (
        client.table("processing_jobs")
        .select("id,status,storage_path,expires_at")
        .not_.is_("storage_path", "null")
        .lte("expires_at", now)
        .neq("status", "processing")
        .limit(100)
        .execute()
    )
    deleted = 0
    for job in response.data or []:
        object_path = job.get("storage_path")
        if not object_path:
            continue
        try:
            remove_storage_object(client, config.supabase_video_bucket, object_path)
            changes: dict[str, Any] = {
                "storage_path": None,
                "video_deleted_at": datetime.now(timezone.utc).isoformat(),
            }
            if job.get("status") in {"received", "queued"}:
                changes["status"] = "expired"
            client.table("processing_jobs").update(changes).eq("id", job["id"]).execute()
            deleted += 1
        except Exception:
            logger.exception("Could not clean expired video for processing job %s", job.get("id"))
    return deleted


async def cleanup_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(60)
        client = getattr(app.state, "supabase", None)
        if client is None:
            continue
        try:
            deleted = await run_in_threadpool(clean_expired_uploads, client, app.state.settings)
            if deleted:
                logger.info("Cleaned up %s expired WIMS video upload(s).", deleted)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("WIMS temporary upload cleanup pass failed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    app.state.supabase = build_supabase_client(settings)
    cleanup_task = asyncio.create_task(cleanup_loop(app))
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(
    title="Where Is My Space API",
    description=(
        "WIMS Capture API for mobile camera recordings, supported screen recordings, "
        "uploaded clips, and registered external camera sources. AI processing remains a separate worker."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "X-WIMS-Capture-Key"],
)

_default_limiter = SlidingWindowLimiter(window_seconds=60, max_events=settings.rate_limit_per_minute)
_upload_limiter = SlidingWindowLimiter(window_seconds=60, max_events=settings.upload_rate_limit_per_minute)


def _rate_limit_key(request: Request) -> str:
    """Best-effort client identity: first X-Forwarded-For hop when behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/v1") and request.method != "OPTIONS":
        is_upload = request.url.path == "/v1/jobs/upload" and request.method == "POST"
        limiter = _upload_limiter if is_upload else _default_limiter
        limit = settings.upload_rate_limit_per_minute if is_upload else settings.rate_limit_per_minute
        if not limiter.allow(_rate_limit_key(request)):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "code": "RATE_LIMITED",
                        "message": f"Too many requests. The limit is {limit} per minute for this endpoint.",
                    }
                },
                headers={"Retry-After": "60"},
            )
    return await call_next(request)


class SourceCreate(BaseModel):
    name: str = PydanticField(min_length=1, max_length=120)
    source_type: Literal["phone_camera", "screen_share", "uploaded_video", "rtsp_camera"]
    device_label: str | None = PydanticField(default=None, max_length=120)
    location_id: UUID | None = None
    zone_id: UUID | None = None
    rtsp_url: str | None = PydanticField(default=None, max_length=2048)


class ZoneCreate(BaseModel):
    location_id: UUID
    slug: str = PydanticField(min_length=1, max_length=60, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = PydanticField(min_length=1, max_length=120)
    description: str | None = PydanticField(default=None, max_length=300)
    capacity: int = PydanticField(ge=0, le=100000)
    # Normalised polygon: [[x,y], ...] with 0..1 coordinates.
    polygon: list[list[float]] | None = None
    is_public: bool = True


class AssistantMessage(BaseModel):
    message: str = PydanticField(min_length=1, max_length=1200)
    history: list[dict[str, str]] = PydanticField(default_factory=list, max_length=8)


@app.get("/health", tags=["system"])
async def health(request: Request) -> dict[str, Any]:
    config: Settings = request.app.state.settings
    return {
        "status": "ok",
        "service": "wims-capture-api",
        "supabase_credentials_configured": getattr(request.app.state, "supabase", None) is not None,
        "capture_access_configured": bool(config.capture_access_code),
        "rtsp_encryption_configured": bool(config.source_encryption_key),
        "video_processing": "queued_for_ai_worker",
    }


@app.get("/v1/sources", tags=["sources"], dependencies=[Depends(require_capture_access)])
async def list_sources(
    client: Client = Depends(require_supabase),
) -> dict[str, Any]:
    try:
        response = await run_in_threadpool(
            lambda: client.table("video_sources").select(SOURCE_COLUMNS).order("created_at", desc=True).limit(50).execute()
        )
    except Exception as exc:
        logger.exception("Could not list WIMS sources.")
        raise HTTPException(status_code=502, detail="Could not load registered sources.") from exc
    return {"sources": response.data or []}


@app.post("/v1/sources", status_code=201, tags=["sources"], dependencies=[Depends(require_capture_access)])
async def register_source(
    payload: SourceCreate,
    request: Request,
    client: Client = Depends(require_supabase),
) -> dict[str, Any]:
    config: Settings = request.app.state.settings
    encrypted_url: str | None = None

    if payload.source_type == "rtsp_camera":
        if not payload.rtsp_url:
            raise HTTPException(status_code=422, detail="An RTSP/RTSPS URL is required for an external camera.")
        parsed_url = urlparse(payload.rtsp_url.strip())
        if parsed_url.scheme.lower() not in {"rtsp", "rtsps"} or not parsed_url.hostname:
            raise HTTPException(status_code=422, detail="Use a valid rtsp:// or rtsps:// camera URL.")
        encrypted_url = get_fernet(config).encrypt(payload.rtsp_url.strip().encode("utf-8")).decode("utf-8")
    elif payload.rtsp_url:
        raise HTTPException(status_code=422, detail="RTSP URL is only accepted for external camera sources.")

    if payload.zone_id:
        zone_lookup = await run_in_threadpool(
            lambda: client.table("zones").select("id").eq("id", str(payload.zone_id)).limit(1).execute()
        )
        if not zone_lookup.data:
            raise HTTPException(
                status_code=422,
                detail="zone_id must reference an existing zone. Create the zone first (POST /v1/zones).",
            )

    safe_metadata = {"registered_from": "wims-capture"}
    row: dict[str, Any] = {
        "name": payload.name.strip(),
        "source_type": payload.source_type,
        "status": "registered",
        "device_label": payload.device_label.strip() if payload.device_label else None,
        "location_id": str(payload.location_id) if payload.location_id else None,
        "zone_id": str(payload.zone_id) if payload.zone_id else None,
        "metadata": safe_metadata,
    }
    if encrypted_url:
        row["stream_url_ciphertext"] = encrypted_url

    try:
        response = await run_in_threadpool(lambda: client.table("video_sources").insert(row).execute())
    except Exception as exc:
        logger.exception("Could not register a WIMS source (type=%s).", payload.source_type)
        raise HTTPException(status_code=502, detail="Could not save the source metadata. Check that the WIMS migrations have been applied.") from exc

    if not response.data:
        raise HTTPException(status_code=502, detail="Source registration did not return a saved record.")
    saved = response.data[0]
    # Never return the encrypted or original RTSP URL to the client.
    return {key: saved.get(key) for key in SOURCE_COLUMNS.split(",")}


@app.post("/v1/jobs/upload", status_code=201, tags=["uploads"], dependencies=[Depends(require_capture_access)])
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    source_type: Literal["mp4", "phone_camera", "screen_share", "uploaded_video"] = Form(default="uploaded_video"),
    source_id: str | None = Form(default=None),
    location_id: str | None = Form(default=None),
    zone_id: str | None = Form(default=None),
    client: Client = Depends(require_supabase),
) -> dict[str, Any]:
    config: Settings = request.app.state.settings

    supplied_name = (file.filename or "").replace("\\", "/")
    original_filename = Path(supplied_name).name
    extension = Path(original_filename).suffix.lower()
    if not original_filename or extension not in {".mp4", ".webm"}:
        await file.close()
        raise HTTPException(status_code=415, detail="Upload an MP4 or WebM video to continue.")

    supplied_type = (file.content_type or "").lower().split(";")[0].strip()
    allowed_types = {"video/mp4", "video/webm", "application/octet-stream", ""}
    if supplied_type not in allowed_types:
        await file.close()
        raise HTTPException(status_code=415, detail="The uploaded file must be an MP4 or WebM video.")

    mime_type = "video/webm" if extension == ".webm" else "video/mp4"
    if supplied_type in {"video/mp4", "video/webm"} and supplied_type != mime_type:
        await file.close()
        raise HTTPException(status_code=415, detail="The file extension and video MIME type do not match.")

    try:
        parsed_source = str(UUID(source_id)) if source_id else None
        parsed_location = str(UUID(location_id)) if location_id else None
        parsed_zone = str(UUID(zone_id)) if zone_id else None
    except ValueError as exc:
        await file.close()
        raise HTTPException(status_code=422, detail="source_id, location_id and zone_id must be valid UUIDs.") from exc

    staging_dir = Path(config.temp_upload_dir)
    try:
        staging_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        await file.close()
        logger.exception("Could not prepare the temporary upload directory.")
        raise HTTPException(status_code=500, detail="Temporary upload storage is unavailable.") from exc

    temp_path: Path | None = None
    storage_path: str | None = None
    object_uploaded = False
    job_id = str(uuid4())
    size_bytes = 0
    header = bytearray()

    try:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=extension, dir=staging_dir, delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > config.upload_limit_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Video exceeds the {config.max_upload_mib} MiB upload limit.",
                    )
                if len(header) < 12:
                    header.extend(chunk[: 12 - len(header)])
                temp_file.write(chunk)

        valid_mp4 = extension == ".mp4" and size_bytes >= 12 and bytes(header[4:8]) == MP4_SIGNATURE
        valid_webm = extension == ".webm" and size_bytes >= 4 and bytes(header[:4]) == WEBM_SIGNATURE
        if not (valid_mp4 or valid_webm):
            raise HTTPException(status_code=415, detail="The file does not have a valid MP4/WebM container signature.")

        storage_path = f"{job_id}/source{extension}"

        def put_private_video() -> None:
            with temp_path.open("rb") as source:
                client.storage.from_(config.supabase_video_bucket).upload(
                    path=storage_path,
                    file=source,
                    file_options={"content-type": mime_type, "upsert": "false"},
                )

        await run_in_threadpool(put_private_video)
        object_uploaded = True
        now = datetime.now(timezone.utc)
        job_payload = {
            "id": job_id,
            "source_id": parsed_source,
            "location_id": parsed_location,
            "zone_id": parsed_zone,
            "source_type": source_type,
            "original_filename": original_filename,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "storage_path": storage_path,
            "status": "received",
            "progress_percent": 0,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=config.upload_ttl_minutes)).isoformat(),
            "result_summary": {
                "stage": "upload_received",
                "message": "Video received and queued for AI person detection by the inference worker.",
            },
        }
        await run_in_threadpool(lambda: client.table("processing_jobs").insert(job_payload).execute())

        return {
            "id": job_id,
            "source_id": parsed_source,
            "source_type": source_type,
            "status": "received",
            "progress_percent": 0,
            "original_filename": original_filename,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "created_at": now.isoformat(),
            "expires_at": job_payload["expires_at"],
            "message": "Video uploaded to private temporary storage and queued for AI processing.",
        }
    except HTTPException:
        if object_uploaded and storage_path:
            try:
                await run_in_threadpool(remove_storage_object, client, config.supabase_video_bucket, storage_path)
            except Exception:
                logger.exception("Could not roll back a failed video upload.")
        raise
    except Exception as exc:
        if object_uploaded and storage_path:
            try:
                await run_in_threadpool(remove_storage_object, client, config.supabase_video_bucket, storage_path)
            except Exception:
                logger.exception("Could not roll back a failed video upload.")
        logger.exception("WIMS video upload failed.")
        raise HTTPException(
            status_code=502,
            detail="The upload could not be saved. Check backend Supabase configuration and retry.",
        ) from exc
    finally:
        await file.close()
        if temp_path:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Temporary staging file could not be removed: %s", temp_path)


@app.get("/v1/jobs/{job_id}", tags=["jobs"], dependencies=[Depends(require_capture_access)])
async def get_job_status(
    job_id: UUID,
    client: Client = Depends(require_supabase),
) -> dict[str, Any]:
    try:
        response = await run_in_threadpool(
            lambda: (
                client.table("processing_jobs")
                .select("id,source_id,zone_id,source_type,status,progress_percent,original_filename,mime_type,size_bytes,created_at,started_at,finished_at,result_summary,error_code")
                .eq("id", str(job_id))
                .limit(1)
                .execute()
            )
        )
    except Exception as exc:
        logger.exception("Could not read processing job %s.", job_id)
        raise HTTPException(status_code=502, detail="Could not retrieve the processing job status.") from exc

    if not response.data:
        raise HTTPException(status_code=404, detail="Processing job not found.")
    return response.data[0]


@app.get("/v1/zones", tags=["zones"])
async def list_zones(client: Client = Depends(require_supabase)) -> dict[str, Any]:
    """Public zone configuration used by the dashboard (capacity + polygons)."""
    try:
        response = await run_in_threadpool(
            lambda: (
                client.table("zones")
                .select(ZONE_COLUMNS + ",locations(name,campus_name)")
                .eq("is_active", True)
                .eq("is_public", True)
                .order("name")
                .limit(200)
                .execute()
            )
        )
    except Exception as exc:
        logger.exception("Could not list WIMS zones.")
        raise HTTPException(status_code=502, detail="Could not load zones. Check that all migrations are applied.") from exc
    return {"zones": response.data or []}


@app.post("/v1/zones", status_code=201, tags=["zones"], dependencies=[Depends(require_capture_access)])
async def create_zone(
    payload: ZoneCreate,
    client: Client = Depends(require_supabase),
) -> dict[str, Any]:
    polygon = None
    if payload.polygon is not None:
        polygon = normalize_polygon(payload.polygon)
        if polygon is None:
            raise HTTPException(
                status_code=422,
                detail="polygon must be a list of at least 3 [x, y] points with 0..1 coordinates.",
            )

    location_lookup = await run_in_threadpool(
        lambda: client.table("locations").select("id").eq("id", str(payload.location_id)).limit(1).execute()
    )
    if not location_lookup.data:
        raise HTTPException(status_code=422, detail="location_id must reference an existing location.")

    row = {
        "location_id": str(payload.location_id),
        "slug": payload.slug,
        "name": payload.name.strip(),
        "description": payload.description,
        "capacity": payload.capacity,
        "polygon": [list(point) for point in polygon] if polygon else None,
        "is_public": payload.is_public,
        "is_active": True,
    }
    try:
        response = await run_in_threadpool(lambda: client.table("zones").insert(row).execute())
    except Exception as exc:
        message = str(exc).lower()
        if "duplicate" in message or "unique" in message:
            raise HTTPException(status_code=409, detail="A zone with this slug already exists in this location.") from exc
        logger.exception("Could not create a WIMS zone.")
        raise HTTPException(status_code=502, detail="Could not save the zone.") from exc
    if not response.data:
        raise HTTPException(status_code=502, detail="Zone creation did not return a saved record.")
    return {key: response.data[0].get(key) for key in ZONE_COLUMNS.split(",")}


@app.get("/v1/occupancy", tags=["occupancy"])
async def get_live_occupancy(client: Client = Depends(require_supabase)) -> dict[str, Any]:
    """Latest persisted occupancy per public zone — the dashboard's live feed."""
    try:
        zones_response = await run_in_threadpool(
            lambda: (
                client.table("zones")
                .select(ZONE_COLUMNS + ",locations(name,campus_name)")
                .eq("is_active", True)
                .eq("is_public", True)
                .limit(200)
                .execute()
            )
        )
        public_locations = await run_in_threadpool(
            lambda: client.table("locations").select("id,name").eq("is_public", True).limit(200).execute()
        )
        snapshots = await run_in_threadpool(
            lambda: (
                client.table("occupancy_snapshots")
                .select("zone_id,occupied_count,capacity_count,confidence,observed_at")
                .order("observed_at", desc=True)
                .limit(500)
                .execute()
            )
        )
    except Exception as exc:
        logger.exception("Could not read live occupancy.")
        raise HTTPException(
            status_code=502,
            detail="Could not load live occupancy. Check that the Supabase migrations are applied.",
        ) from exc

    allowed_locations = {row["id"]: row.get("name") for row in (public_locations.data or [])}
    latest: dict[str, dict[str, Any]] = {}
    for snap in snapshots.data or []:
        if snap.get("zone_id") not in latest:
            latest[snap["zone_id"]] = snap

    zones_output: list[dict[str, Any]] = []
    for zone in zones_response.data or []:
        location_id = zone.get("location_id")
        if location_id not in allowed_locations:
            continue
        snap = latest.get(zone["id"])
        occupied = snap.get("occupied_count") if snap else None
        capacity = zone.get("capacity")
        zones_output.append(
            {
                "id": zone["id"],
                "name": zone["name"],
                "slug": zone.get("slug"),
                "description": zone.get("description"),
                "capacity": capacity,
                "location_id": location_id,
                "location_name": zone.get("locations", {}).get("name")
                if isinstance(zone.get("locations"), dict)
                else allowed_locations.get(location_id),
                "observed_at": snap.get("observed_at") if snap else None,
                "confidence": snap.get("confidence") if snap else None,
                "has_live_data": snap is not None,
                "status": availability_status(occupied, capacity) if occupied is not None else "No data",
                "available_count": max(capacity - occupied, 0) if occupied is not None else None,
            }
        )

    zones_output.sort(key=lambda item: item["name"] or "")
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "zones": zones_output}


@app.post("/v1/assistant", tags=["assistant"])
async def ask_space_assistant(
    payload: AssistantMessage,
    request: Request,
) -> dict[str, Any]:
    """Answer space questions using public, derived occupancy metadata only."""
    client = getattr(request.app.state, "supabase", None)
    try:
        if client is None:
            raise HTTPException(status_code=503, detail="Supabase is not configured")
        feed = await get_live_occupancy(client)
        zones = [
            {
                "name": zone.get("name"),
                "location": zone.get("location_name"),
                "capacity": zone.get("capacity"),
                "occupied": (
                    zone.get("capacity") - zone.get("available_count")
                    if zone.get("available_count") is not None and zone.get("capacity") is not None
                    else None
                ),
                "status": zone.get("status"),
                "observed_at": zone.get("observed_at"),
            }
            for zone in feed["zones"]
        ]
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        # Keep the assistant useful for a first-run local demo before Supabase is configured.
        zones = []

    config: Settings = request.app.state.settings
    assistant_settings = AssistantSettings(
        region=config.aws_region,
        model_id=config.bedrock_model_id,
        enabled=config.bedrock_enabled,
    )
    try:
        response, provider = await run_in_threadpool(
            answer_assistant, payload.message, zones, payload.history, assistant_settings
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"answer": response, "provider": provider, "zones_considered": len(zones)}


@app.get("/v1/jobs/{job_id}/preview", tags=["jobs"], dependencies=[Depends(require_capture_access)])
async def get_job_preview(
    job_id: UUID,
    client: Client = Depends(require_supabase),
) -> Response:
    """Annotated preview (bounding boxes) for a completed AI job."""
    config: Settings = settings
    try:
        response = await run_in_threadpool(
            lambda: (
                client.table("processing_jobs")
                .select("result_summary,status")
                .eq("id", str(job_id))
                .limit(1)
                .execute()
            )
        )
    except Exception as exc:
        logger.exception("Could not read preview metadata for job %s", job_id)
        raise HTTPException(status_code=502, detail="Could not load the preview record.") from exc
    if not response.data:
        raise HTTPException(status_code=404, detail="Processing job not found.")
    job = response.data[0]
    preview_path = (job.get("result_summary") or {}).get("preview_path")
    if not preview_path or job.get("status") != "completed":
        raise HTTPException(
            status_code=404,
            detail="No AI preview is available for this job yet. It appears after the worker completes processing.",
        )
    try:
        image_bytes = await run_in_threadpool(
            lambda: client.storage.from_(config.supabase_preview_bucket).download(preview_path)
        )
    except Exception as exc:
        logger.exception("Could not download preview %s for job %s", preview_path, job_id)
        raise HTTPException(status_code=502, detail="The preview image could not be loaded.") from exc
    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=600"},
    )
