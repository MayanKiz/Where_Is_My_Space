from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Region
from schemas import RegionCreate, RegionUpdate, RegionOut
from auth import get_current_admin
from dashboard import build_dashboard_state
from websocket_manager import manager

router = APIRouter()


@router.get("", response_model=list[RegionOut])
async def list_regions(db: AsyncSession = Depends(get_db)):
    state = await build_dashboard_state(db)
    return state.regions


@router.get("/{region_id}", response_model=RegionOut)
async def get_region(region_id: int, db: AsyncSession = Depends(get_db)):
    region = await db.get(Region, region_id)
    if not region or not region.is_active:
        raise HTTPException(404, "Region not found")
    state = await build_dashboard_state(db)
    for r in state.regions:
        if r.id == region_id:
            return r
    raise HTTPException(404, "Region not found in state")


@router.post("", response_model=RegionOut, status_code=201)
async def create_region(
    data: RegionCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    region = Region(**data.model_dump())
    db.add(region)
    await db.commit()
    await db.refresh(region)
    state = await build_dashboard_state(db)
    await manager.broadcast(state.model_dump_json())
    for r in state.regions:
        if r.id == region.id:
            return r
    raise HTTPException(500, "Region created but missing from dashboard state")


@router.put("/{region_id}", response_model=RegionOut)
async def update_region(
    region_id: int,
    data: RegionUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    region = await db.get(Region, region_id)
    if not region or not region.is_active:
        raise HTTPException(404, "Region not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(region, field, value)
    await db.commit()
    await db.refresh(region)
    state = await build_dashboard_state(db)
    await manager.broadcast(state.model_dump_json())
    for r in state.regions:
        if r.id == region_id:
            return r
    raise HTTPException(500, "Region updated but missing from dashboard state")


@router.delete("/{region_id}")
async def delete_region(
    region_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    region = await db.get(Region, region_id)
    if not region or not region.is_active:
        raise HTTPException(404, "Region not found")
    region.is_active = False
    await db.commit()
    state = await build_dashboard_state(db)
    await manager.broadcast(state.model_dump_json())
    return {"ok": True}
