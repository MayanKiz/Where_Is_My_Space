from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class RegionCreate(BaseModel):
    name: str = Field(min_length=1)
    camera_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    capacity: int = Field(gt=0)
    description: Optional[str] = None
    section: str = "library"


class RegionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    camera_id: Optional[str] = Field(default=None, min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    capacity: Optional[int] = Field(default=None, gt=0)
    description: Optional[str] = None
    section: Optional[str] = None


class CountUpdatePayload(BaseModel):
    camera_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    # upper bounds stop a leaked key from pushing absurd numbers to the dashboard
    count: int = Field(ge=0, le=10000)
    reserved: int = Field(default=0, ge=0, le=10000)
    timestamp: Optional[datetime] = None


class RegionOut(BaseModel):
    id: int
    name: str
    camera_id: str
    capacity: int
    current_count: int
    reserved_count: int
    occupancy_pct: float
    status: Literal["free", "moderate", "full", "offline"]
    camera_online: bool
    last_updated: Optional[datetime]
    description: Optional[str] = None
    section: str = "library"

    model_config = ConfigDict(from_attributes=True)


class DashboardBroadcast(BaseModel):
    regions: list[RegionOut]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
