"""Alembic migration runner (Tier 1) — see docs/DATABASE_MIGRATION.md for
the full story. Replaces the bare `create_all()` call in app.main's
lifespan; `init_models()` (core/db.py) still exists as a documented manual
fallback, not deleted.

Three real states a database can be in at startup:

1. Already Alembic-managed (`alembic_version` table exists) — just
   `alembic upgrade head`. The common case from here forward.
2. Truly fresh (no tables at all) — `alembic upgrade head` creates
   everything from the baseline migration.
3. A pre-Tier-1 database created by the old `create_all()` path (has
   application tables, no `alembic_version`) — this is the one-time
   transition this codebase itself is in. `create_all()` never adds
   columns to existing tables (a real, twice-bitten gap — see
   docs/ARCHITECTURE.md §11), so such a database is missing exactly the
   columns Tier 1 added in the same commit as this baseline migration
   (`securities.isin/segment/asset_class/lot_size/tick_size`,
   `users.role`). Add those by hand, then `alembic stamp head` — adopting
   Alembic from this point forward rather than replaying history no
   migration ever recorded.
"""

import asyncio
from pathlib import Path

from sqlalchemy import inspect, text

from app.core.db import engine

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

# (table, column, DDL type) — exactly the columns the baseline migration
# added beyond what the pre-Tier-1 create_all() schema had. Not a generic
# schema-diff mechanism; see the module docstring for why a hardcoded list
# is the right scope here.
_PRE_ALEMBIC_COLUMN_GAPS: list[tuple[str, str, str]] = [
    ("securities", "isin", "VARCHAR(12)"),
    ("securities", "segment", "VARCHAR(20)"),
    ("securities", "asset_class", "VARCHAR(20)"),
    ("securities", "lot_size", "INTEGER"),
    ("securities", "tick_size", "NUMERIC(10, 4)"),
    ("users", "role", "VARCHAR(20) NOT NULL DEFAULT 'user'"),
]


def _sync_upgrade_head() -> None:
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(ALEMBIC_INI)), "head")


def _sync_stamp_head() -> None:
    from alembic import command
    from alembic.config import Config

    command.stamp(Config(str(ALEMBIC_INI)), "head")


async def _reconcile_pre_alembic_gaps() -> None:
    async with engine.begin() as conn:
        for table, column, ddl_type in _PRE_ALEMBIC_COLUMN_GAPS:
            existing_columns = await conn.run_sync(lambda sync_conn, t=table: {c["name"] for c in inspect(sync_conn).get_columns(t)})
            if column not in existing_columns:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


async def run_migrations() -> None:
    async with engine.connect() as conn:
        table_names = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))

    if "alembic_version" in table_names:
        await asyncio.to_thread(_sync_upgrade_head)
        return

    if table_names:
        await _reconcile_pre_alembic_gaps()
        await asyncio.to_thread(_sync_stamp_head)
        return

    await asyncio.to_thread(_sync_upgrade_head)
