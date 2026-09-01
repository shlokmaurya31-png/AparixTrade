import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.events.impact import compute_event_impact
from app.domains.events.seed_data import SEED_EVENTS
from app.domains.knowledge_graph.service import exposure_multipliers, resolve_graph_exposure
from app.domains.portfolios.service import compute_beta_by_symbol, get_holdings_with_quotes
from app.domains.simulation.stress_test import HoldingRow
from app.models.event import Event
from app.models.portfolio import Portfolio


class NoHoldingsError(Exception):
    pass


async def seed_if_needed(db: AsyncSession) -> None:
    """Idempotent, same pattern as market_data.service.seed_if_needed."""
    count = await db.scalar(select(func.count()).select_from(Event))
    if count and count > 0:
        return

    now = datetime.now(timezone.utc)
    for headline, summary, event_type, severity, direction, primary_target, tags, region, days_ago in SEED_EVENTS:
        db.add(
            Event(
                headline=headline,
                summary=summary,
                event_type=event_type,
                severity=severity,
                direction=direction,
                primary_target=primary_target,
                secondary_tags=tags,
                region=region,
                published_at=now - timedelta(days=days_ago),
                is_mock=True,
            )
        )
    await db.commit()


async def list_events(db: AsyncSession, limit: int = 50) -> list[Event]:
    result = await db.execute(select(Event).order_by(Event.published_at.desc()).limit(limit))
    return list(result.scalars().all())


async def get_event(db: AsyncSession, event_id: uuid.UUID) -> Event | None:
    result = await db.execute(select(Event).where(Event.id == event_id))
    return result.scalar_one_or_none()


async def get_most_recent_significant_event(db: AsyncSession) -> Event | None:
    """Default used by the AI tool when no event is specified — the most
    recent medium/high-severity event, same "sensible default, state it
    explicitly" pattern as the Phase 2 stress-test tool's NIFTY50 -15%."""
    result = await db.execute(
        select(Event).where(Event.severity.in_(["medium", "high"])).order_by(Event.published_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def compute_impact_for_portfolio(db: AsyncSession, event: Event, portfolio: Portfolio) -> dict:
    rows = await get_holdings_with_quotes(db, portfolio)
    if not rows:
        raise NoHoldingsError("Portfolio has no holdings to assess event impact for.")

    beta_lookup = await compute_beta_by_symbol(db, rows)
    holding_rows = [
        HoldingRow(symbol=r["security"].symbol, sector=r["security"].sector, market_value=r["metrics"].market_value)
        for r in rows
    ]
    # A location/commodity primary_target (Tier 1 — knowledge-graph
    # propagation) resolves to real indirectly-exposed holdings here;
    # None for an ordinary direct symbol/sector/NIFTY50 target, in which
    # case exposure_multipliers() returns {} and apply_shock()'s existing
    # behavior is completely unchanged.
    resolved = await resolve_graph_exposure(db, event.primary_target)
    return compute_event_impact(event, holding_rows, beta_lookup, exposure_multipliers(resolved))
