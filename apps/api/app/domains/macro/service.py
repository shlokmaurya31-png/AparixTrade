from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.macro.provider import get_macro_provider
from app.domains.macro.seed_data import SEED_INDICATORS
from app.domains.macro.vintage import generate_releases
from app.models.macro import MacroIndicator
from app.models.macro_release import MacroIndicatorRelease


async def seed_if_needed(db: AsyncSession) -> None:
    """Idempotent, same pattern as market_data.service.seed_if_needed."""
    count = await db.scalar(select(func.count()).select_from(MacroIndicator))
    if count and count > 0:
        return

    for code, name, value, unit in SEED_INDICATORS:
        db.add(MacroIndicator(code=code, name=name, value=value, unit=unit, is_mock=True))
    await db.commit()


async def seed_vintage_if_needed(db: AsyncSession) -> None:
    """Idempotent, and deliberately independent of seed_if_needed() (not
    nested inside it) — called separately from app.main's lifespan. A
    database whose macro_indicators table was already populated by an
    earlier phase (true for this repo's own real dev database, seeded
    back in Phase 3, long before this table existed) would otherwise skip
    seed_if_needed() entirely and never reach vintage seeding — the exact
    same "seed only runs once" gotcha already hit with news ingestion.
    Generates real point-in-time vintage/revision history
    (domains/macro/vintage.py) for the indicators that actually have one
    (CPI, GDP growth)."""
    count = await db.scalar(select(func.count()).select_from(MacroIndicatorRelease))
    if count and count > 0:
        return

    today = datetime.now(timezone.utc).date()
    for code, _name, value, unit in SEED_INDICATORS:
        for row in generate_releases(code, value, today):
            db.add(
                MacroIndicatorRelease(
                    code=code,
                    period=row["period"],
                    value=row["value"],
                    unit=unit,
                    frequency="monthly" if code == "cpi_inflation" else "quarterly",
                    revision_number=row["revision_number"],
                    release_date=row["release_date"],
                    source="mock",
                    is_mock=True,
                )
            )
    await db.commit()


async def list_indicators(db: AsyncSession) -> list[MacroIndicator]:
    # Routed through MacroDataProvider (provider.py, Tier 1) instead of
    # querying the table directly — same result, but callers no longer
    # depend on there being exactly one DB-backed implementation.
    return await get_macro_provider().get_latest(db)


async def get_indicator(db: AsyncSession, code: str) -> MacroIndicator | None:
    return await get_macro_provider().get_indicator(db, code)


async def get_releases_as_of(db: AsyncSession, code: str, *, as_of: date) -> list[MacroIndicatorRelease]:
    """Point-in-time (§15, same discipline as fundamentals/corporate
    actions): only releases actually published (release_date <= as_of),
    ordered oldest-period-first, latest-revision-last per period."""
    result = await db.execute(
        select(MacroIndicatorRelease)
        .where(MacroIndicatorRelease.code == code, MacroIndicatorRelease.release_date <= as_of)
        .order_by(MacroIndicatorRelease.period.asc(), MacroIndicatorRelease.revision_number.asc())
    )
    return list(result.scalars().all())


async def get_latest_known_reading_as_of(db: AsyncSession, code: str, *, as_of: date) -> MacroIndicatorRelease | None:
    """The single reading a point-in-time analysis dated `as_of` would
    actually have known — the highest (period, revision_number) among
    releases published by then. Never a later revision or a later
    period's figure, even if that figure is "more correct" with
    hindsight — using it would be exactly the look-ahead bias §15
    prohibits."""
    releases = await get_releases_as_of(db, code, as_of=as_of)
    if not releases:
        return None
    return max(releases, key=lambda r: (r.period, r.revision_number))
