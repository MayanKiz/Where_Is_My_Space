from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    camera_id: Mapped[str] = mapped_column(String(100), unique=True)
    capacity: Mapped[int]
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    section: Mapped[str] = mapped_column(String(20), default="library", server_default="library")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    count_logs: Mapped[list["CountLog"]] = relationship(
        back_populates="region", cascade="all, delete-orphan"
    )


class CountLog(Base):
    __tablename__ = "count_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    count: Mapped[int]
    reserved_count: Mapped[int] = mapped_column(default=0, server_default="0")
    received_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    region: Mapped["Region"] = relationship(back_populates="count_logs")
