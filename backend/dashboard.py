from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Region, CountLog
from schemas import RegionOut, DashboardBroadcast
from config import get_settings

settings = get_settings()


def compute_status(
    count: int,
    capacity: int,
    last_updated: Optional[datetime],
    threshold: int,
) -> str:
    if last_updated is None:
        return "offline"
    age = (datetime.utcnow() - last_updated).total_seconds()
    if age > threshold:
        return "offline"
    if capacity <= 0:
        # Misconfigured region (no capacity) — don't divide by zero.
        return "free" if count == 0 else "full"
    pct = count / capacity * 100
    if pct < 40:
        return "free"
    if pct < 75:
        return "moderate"
    return "full"


async def build_dashboard_state(db: AsyncSession) -> DashboardBroadcast:
    result = await db.execute(select(Region).where(Region.is_active.is_(True)))
    regions = result.scalars().all()

    regions_out: list[RegionOut] = []
    for region in regions:
        log_result = await db.execute(
            select(CountLog)
            .where(CountLog.region_id == region.id)
            .order_by(CountLog.received_at.desc())
            .limit(1)
        )
        latest = log_result.scalar_one_or_none()

        count = latest.count if latest else 0
        reserved = latest.reserved_count if latest else 0
        last_updated = latest.received_at if latest else None
        status = compute_status(
            count, region.capacity, last_updated, settings.CAMERA_OFFLINE_THRESHOLD_SECONDS
        )
        occupancy_pct = round(count / region.capacity * 100, 1) if region.capacity > 0 else 0.0

        regions_out.append(
            RegionOut(
                id=region.id,
                name=region.name,
                camera_id=region.camera_id,
                capacity=region.capacity,
                current_count=count,
                reserved_count=reserved,
                occupancy_pct=occupancy_pct,
                status=status,
                camera_online=(status != "offline"),
                last_updated=last_updated,
                description=region.description,
                section=region.section,
            )
        )

    return DashboardBroadcast(regions=regions_out)
