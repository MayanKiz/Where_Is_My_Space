from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import Region

SEED_REGIONS = [
    {"name": "Entrance / Lobby",            "camera_id": "cam_01",         "capacity": 40,  "section": "library"},
    {"name": "Main Reading Hall",           "camera_id": "cam_02",         "capacity": 80,  "section": "library"},
    {"name": "Upper Floor / Quiet Zone",    "camera_id": "cam_03",         "capacity": 30,  "section": "library"},
    {"name": "Collaborative / Group Study", "camera_id": "cam_04",         "capacity": 25,  "section": "library"},
    {"name": "Main Lecture Theatre (LT)",   "camera_id": "cam_lt_01",     "capacity": 120, "section": "lt"},
    {"name": "CS-IT Canteen",               "camera_id": "cam_canteen_01", "capacity": 60,  "section": "canteen"},
]


async def seed_if_empty(session: AsyncSession) -> None:
    result = await session.execute(select(Region).limit(1))
    if result.first() is not None:
        return
    for data in SEED_REGIONS:
        session.add(Region(**data))
    await session.commit()
