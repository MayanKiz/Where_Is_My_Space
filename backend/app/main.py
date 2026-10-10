from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.concurrency import run_in_threadpool
from supabase import Client, create_client

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("wims.api")

VIDEO_BUCKET = "wims-temporary-videos"
MP4_SIGNATURE = b"ftyp"
CHUNK_SIZE = 1024 * 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_video_bucket: str = VIDEO_BUCKET
    cors_origins: str = "http://localhost:3000"
    max_upload_mib: int = Field(default=100, ge=1, le=512)
    upload_ttl_minutes: int = Field(default=30, ge=5, le=1440)
    temp_upload_dir: str = "/tmp/wims-upload-staging"

    @property
    def upload_limit_bytes(self) -> int:
        return self.max_upload_mib * 1024 * 1024

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()


def build_supabase_client(config: Settings) -> Client | None:
    if not config.supabase_url or not config.supabase_service_role_key:
        logger.warning("Supabase server credentials are not configured; upload routes will return 503.")
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
        "WIMS upload and job-status API. This stage accepts private MP4 uploads; "
        "the computer-vision worker is a separate implementation step."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


@app.get("/health", tags=["system"])
async def health(request: Request) -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "wims-upload-api",
        "supabase_credentials_configured": getattr(request.app.state, "supabase", None) is not None,
        "video_processing": "not_implemented",
    }


@app.post("/v1/jobs/upload", status_code=201, tags=["uploads"])
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    location_id: str | None = Form(default=None),
    zone_id: str | None = Form(default=None),
    client: Client = Depends(require_supabase),
) -> dict[str, Any]:
    config: Settings = request.app.state.settings

    supplied_name = (file.filename or "").replace("\\", "/")
    original_filename = Path(supplied_name).name
    if not original_filename or not original_filename.lower().endswith(".mp4"):
        await file.close()
        raise HTTPException(status_code=415, detail="Upload an MP4 video (.mp4) to continue.")

    supplied_type = (file.content_type or "").lower()
    if supplied_type not in {"video/mp4", "application/octet-stream", ""}:
        await file.close()
        raise HTTPException(status_code=415, detail="The uploaded file must be an MP4 video.")

    try:
        parsed_location = str(UUID(location_id)) if location_id else None
        parsed_zone = str(UUID(zone_id)) if zone_id else None
    except ValueError as exc:
        await file.close()
        raise HTTPException(status_code=422, detail="location_id and zone_id must be valid UUIDs.") from exc

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
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".mp4", dir=staging_dir, delete=False) as temp_file:
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

        if size_bytes < 12 or bytes(header[4:8]) != MP4_SIGNATURE:
            raise HTTPException(status_code=415, detail="The file does not have a valid MP4 container signature.")

        storage_path = f"{job_id}/source.mp4"

        def put_private_video() -> None:
            with temp_path.open("rb") as source:
                client.storage.from_(config.supabase_video_bucket).upload(
                    path=storage_path,
                    file=source,
                    file_options={"content-type": "video/mp4", "upsert": "false"},
                )

        await run_in_threadpool(put_private_video)
        object_uploaded = True
        now = datetime.now(timezone.utc)
        job_payload = {
            "id": job_id,
            "location_id": parsed_location,
            "zone_id": parsed_zone,
            "source_type": "mp4",
            "original_filename": original_filename,
            "mime_type": "video/mp4",
            "size_bytes": size_bytes,
            "storage_path": storage_path,
            "status": "received",
            "progress_percent": 0,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=config.upload_ttl_minutes)).isoformat(),
            "result_summary": {
                "stage": "upload_received",
                "message": "Video received. AI processing worker is not enabled in this build yet.",
            },
        }
        await run_in_threadpool(lambda: client.table("processing_jobs").insert(job_payload).execute())

        return {
            "id": job_id,
            "status": "received",
            "progress_percent": 0,
            "original_filename": original_filename,
            "size_bytes": size_bytes,
            "created_at": now.isoformat(),
            "expires_at": job_payload["expires_at"],
            "message": "Video uploaded to private temporary storage. AI processing is not enabled in this build yet.",
        }
    except HTTPException:
        if object_uploaded and storage_path:
            try:
                await run_in_threadpool(remove_storage_object, client, config.supabase_video_bucket, storage_path)
            except Exception:
                logger.exception("Could not roll back a failed MP4 upload.")
        raise
    except Exception as exc:
        if object_uploaded and storage_path:
            try:
                await run_in_threadpool(remove_storage_object, client, config.supabase_video_bucket, storage_path)
            except Exception:
                logger.exception("Could not roll back a failed MP4 upload.")
        logger.exception("WIMS MP4 upload failed.")
        raise HTTPException(
            status_code=502,
            detail="The upload could not be saved. Check the backend Supabase configuration and retry.",
        ) from exc
    finally:
        await file.close()
        if temp_path:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Temporary staging file could not be removed: %s", temp_path)


@app.get("/v1/jobs/{job_id}", tags=["jobs"])
async def get_job_status(
    job_id: UUID,
    client: Client = Depends(require_supabase),
) -> dict[str, Any]:
    try:
        response = await run_in_threadpool(
            lambda: (
                client.table("processing_jobs")
                .select("id,status,progress_percent,original_filename,size_bytes,created_at,started_at,finished_at,result_summary,error_code")
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
