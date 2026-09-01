"""Point-in-time corporate actions service — same discipline as
domains/fundamentals/service.py: a query "as of" a date must never surface
an action before its actual effective_date.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.corporate_action_types import RATIO_ACTION_TYPES
from app.domains.corporate_actions.provider import get_corporate_actions_provider
from app.domains.market_data.service import get_security_by_symbol
from app.models.corporate_action import CorporateAction
from app.models.security import Security


class UnknownSymbolError(Exception):
    pass


async def seed_if_needed(db: AsyncSession) -> None:
    """Idempotent, same pattern as every other domain's seeding. Only
    seeds against the tradable (non-index) universe — index-level
    corporate actions aren't a real concept."""
    count = await db.scalar(select(func.count()).select_from(CorporateAction))
    if count and count > 0:
        return

    provider = get_corporate_actions_provider()
    today = datetime.now(timezone.utc).date()
    result = await db.execute(select(Security).where(Security.is_index.is_(False)))
    securities = list(result.scalars().all())

    for security in securities:
        start_price = _approx_start_price(security)
        for row in provider.generate(security.symbol, start_price, today):
            db.add(CorporateAction(security_id=security.id, is_mock=True, **row))
    await db.commit()


def _approx_start_price(security: Security) -> float:
    """The corporate actions generator only needs a rough price scale (to
    decide dividend size and split-likelihood), not today's exact live
    quote — the seeded SEED_SECURITIES starting price is a stable,
    always-available proxy that doesn't require live_market_state to be
    initialized yet at the point this runs. See app.main's lifespan
    ordering: corporate actions seed before live_market_state ticks,
    intentionally decoupled from it."""
    from app.domains.market_data.seed_data import SEED_SECURITIES

    for symbol, _name, _sector, price, _is_index in SEED_SECURITIES:
        if symbol == security.symbol:
            return price
    return 1000.0


async def resolve_security(db: AsyncSession, symbol: str) -> Security:
    security = await get_security_by_symbol(db, symbol)
    if security is None:
        raise UnknownSymbolError(symbol)
    return security


async def list_actions_as_of(
    db: AsyncSession, security_id: uuid.UUID, *, as_of: date
) -> list[CorporateAction]:
    result = await db.execute(
        select(CorporateAction)
        .where(CorporateAction.security_id == security_id, CorporateAction.effective_date <= as_of)
        .order_by(CorporateAction.ex_date.asc())
    )
    return list(result.scalars().all())


async def action_to_dict(db: AsyncSession, security: Security, action: CorporateAction) -> dict:
    new_security_symbol = None
    if action.new_security_id is not None:
        new_security = await db.get(Security, action.new_security_id)
        new_security_symbol = new_security.symbol if new_security else None

    return {
        "id": action.id,
        "symbol": security.symbol,
        "action_type": action.action_type,
        "ratio": float(action.ratio) if action.ratio is not None else None,
        "amount": float(action.amount) if action.amount is not None else None,
        "new_security_symbol": new_security_symbol,
        "announcement_date": action.announcement_date,
        "record_date": action.record_date,
        "ex_date": action.ex_date,
        "effective_date": action.effective_date,
        "source": action.source,
        "is_mock": action.is_mock,
        "provenance": action.provenance,
    }


async def list_ratio_actions_as_of(db: AsyncSession, security_id: uuid.UUID, *, as_of: date) -> list[dict]:
    """The subset relevant to domains/corporate_actions/analytics.py::adjust_price_series
    — split/bonus/rights only, in the {"ex_date", "ratio"} shape it expects."""
    actions = await list_actions_as_of(db, security_id, as_of=as_of)
    return [
        {"ex_date": a.ex_date, "ratio": float(a.ratio)}
        for a in actions
        if a.action_type in RATIO_ACTION_TYPES and a.ratio is not None
    ]
