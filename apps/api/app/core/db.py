import json
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# JSON columns (e.g. AIToolCall.result) hold real tool output, which
# routinely includes UUIDs and datetimes — default=str keeps that from
# breaking on every new field a tool returns.
_json_serializer = lambda obj: json.dumps(obj, default=str)  # noqa: E731

engine = create_async_engine(
    settings.database_url, connect_args=connect_args, json_serializer=_json_serializer
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create tables from the current models directly, bypassing Alembic.
    Not called by app.main's lifespan (that runs core/migrations.py's
    run_migrations() as of Tier 1) — kept only as a manual escape hatch for
    local scratch/one-off scripts that want a schema without touching
    alembic_version. Never add a column to an existing table and expect
    this to pick it up: create_all() only creates missing tables (see
    docs/ARCHITECTURE.md §11) — use a real migration instead."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
