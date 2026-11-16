import hmac

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Region, CountLog
from schemas import CountUpdatePayload, DashboardBroadcast
from dashboard import build_dashboard_state
from websocket_manager import manager
from config import get_settings

router = APIRouter()
settings = get_settings()


async def verify_device_key(x_api_key: str | None = Header(default=None)) -> None:
    """Reject count submissions that don't carry the shared device key.

    If DEVICE_API_KEY is unset the check is skipped (so existing deployments
    keep working), but production should always set it.
    """
    expected = settings.DEVICE_API_KEY
    if not expected:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid or missing device API key")


@router.post("/update")
async def update_count(
    payload: CountUpdatePayload,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_device_key),
):
    result = await db.execute(
        select(Region).where(
            Region.camera_id == payload.camera_id,
            Region.is_active.is_(True),
        )
    )
    region = result.scalar_one_or_none()
    if not region:
        raise HTTPException(404, f"No active region for camera_id='{payload.camera_id}'")

    db.add(CountLog(region_id=region.id, count=payload.count, reserved_count=payload.reserved))
    await db.commit()

    state = await build_dashboard_state(db)
    await manager.broadcast(state.model_dump_json())

    return {"ok": True, "region_id": region.id, "region_name": region.name}


@router.get("/latest", response_model=DashboardBroadcast)
async def get_latest(db: AsyncSession = Depends(get_db)):
    return await build_dashboard_state(db)
