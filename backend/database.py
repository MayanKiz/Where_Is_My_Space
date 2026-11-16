import re

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import get_settings

settings = get_settings()


def _normalize_db_url(url: str) -> str:
    """Accept the URL a host hands out and make it async-driver ready.

    - postgres:// or postgresql://  ->  postgresql+asyncpg://
    - translate libpq's ?sslmode=require (Neon/Supabase/Render external) into
      asyncpg's ?ssl=require, and drop params asyncpg doesn't understand.
    Render's internal database URL has no query string and is left as-is.
    """
    url = re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", url)
    if "?" not in url:
        return url
    base, query = url.split("?", 1)
    kept, want_ssl = [], False
    for part in filter(None, query.split("&")):
        key, _, val = part.partition("=")
        if key == "sslmode":
            want_ssl = val not in ("", "disable")
        elif key in ("channel_binding",):
            continue  # not understood by asyncpg
        else:
            kept.append(part)
    if want_ssl:
        kept.append("ssl=require")
    return base + ("?" + "&".join(kept) if kept else "")


engine = create_async_engine(_normalize_db_url(settings.DATABASE_URL), echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    import models  # noqa: F401 — registers ORM models with Base.metadata
    import sqlalchemy

    # Create the tables first and commit this on its own.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Legacy migrations for pre-existing databases. Each runs in its OWN
    # transaction: on PostgreSQL a failed statement aborts its whole transaction,
    # so sharing one with create_all would roll the tables back. Isolating each
    # ALTER means a "column already exists" failure is harmless.
    for sql in [
        "ALTER TABLE count_logs ADD COLUMN reserved_count INTEGER DEFAULT 0",
        "ALTER TABLE regions ADD COLUMN section VARCHAR DEFAULT 'library'",
        # The dashboard asks for the latest count per region every few seconds;
        # without this index that query slows down as count_logs grows.
        "CREATE INDEX IF NOT EXISTS ix_count_logs_region_received "
        "ON count_logs (region_id, received_at)",
    ]:
        try:
            async with engine.begin() as conn:
                await conn.execute(sqlalchemy.text(sql))
        except Exception:
            pass  # column already exists
