import uuid

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core import migrations

# These tests exercise app.core.migrations.run_migrations() directly against
# throwaway databases — separate from the shared test DB every other test
# file uses via the `client` fixture (which already proves the "fresh
# database" and "already migrated" paths work, since every test run hits
# both). What's untested elsewhere is the one-time "pre-Alembic database"
# reconciliation path, since a freshly-created test DB never starts in that
# state — see docs/DATABASE_MIGRATION.md.


async def test_run_migrations_on_a_truly_fresh_database_creates_full_schema(tmp_path, monkeypatch):
    from app.core import config

    db_path = tmp_path / f"fresh_{uuid.uuid4().hex}.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    config.get_settings.cache_clear()
    temp_engine = create_async_engine(db_url)
    monkeypatch.setattr(migrations, "engine", temp_engine)

    try:
        await migrations.run_migrations()
        async with temp_engine.connect() as conn:
            tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        assert "alembic_version" in tables
        assert {"users", "securities", "portfolios", "broker_connections"} <= tables
    finally:
        await temp_engine.dispose()
        config.get_settings.cache_clear()


async def test_run_migrations_is_idempotent_when_already_at_head(tmp_path, monkeypatch):
    from app.core import config

    db_path = tmp_path / f"idempotent_{uuid.uuid4().hex}.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    config.get_settings.cache_clear()
    temp_engine = create_async_engine(db_url)
    monkeypatch.setattr(migrations, "engine", temp_engine)

    try:
        await migrations.run_migrations()
        await migrations.run_migrations()  # a second run must not fail or duplicate anything
        async with temp_engine.connect() as conn:
            version_rows = (await conn.execute(text("SELECT version_num FROM alembic_version"))).all()
        assert len(version_rows) == 1
    finally:
        await temp_engine.dispose()
        config.get_settings.cache_clear()


async def test_run_migrations_reconciles_a_pre_alembic_database(tmp_path, monkeypatch):
    """Simulates this codebase's own real transition: a database created by
    the old create_all() path (application tables exist, no alembic_version,
    missing the columns Tier 1 added in the baseline migration)."""
    from app.core import config

    db_path = tmp_path / f"pre_alembic_{uuid.uuid4().hex}.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    config.get_settings.cache_clear()
    temp_engine = create_async_engine(db_url)
    monkeypatch.setattr(migrations, "engine", temp_engine)

    try:
        async with temp_engine.begin() as conn:
            await conn.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT)"))
            await conn.execute(text("CREATE TABLE securities (id TEXT PRIMARY KEY, symbol TEXT)"))

        await migrations.run_migrations()

        async with temp_engine.connect() as conn:
            tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
            user_columns = await conn.run_sync(lambda c: {col["name"] for col in inspect(c).get_columns("users")})
            security_columns = await conn.run_sync(
                lambda c: {col["name"] for col in inspect(c).get_columns("securities")}
            )

        assert "alembic_version" in tables
        assert "role" in user_columns
        assert {"isin", "segment", "asset_class", "lot_size", "tick_size"} <= security_columns
    finally:
        await temp_engine.dispose()
        config.get_settings.cache_clear()
