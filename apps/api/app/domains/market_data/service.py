import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.corporate_action_types import ActionType
from app.domains.market_data.historical_seed_data import DELISTED_SECURITY, MERGED_SECURITY
from app.domains.market_data.provider import MockMarketDataProvider
from app.domains.market_data.seed_data import SEED_SECURITIES
from app.models.corporate_action import CorporateAction
from app.models.security import Candle, Security

provider = MockMarketDataProvider()


async def seed_if_needed(db: AsyncSession) -> None:
    """Idempotent: only seeds securities/candles the first time the (SQLite)
    dev database is empty. DEMO DATA only — see seed_data.py."""
    count = await db.scalar(select(func.count()).select_from(Security))
    if count and count > 0:
        return

    for symbol, name, sector, start_price, is_index in SEED_SECURITIES:
        security = Security(symbol=symbol, name=name, sector=sector, is_index=is_index, is_mock=True)
        db.add(security)
        await db.flush()

        history = provider.generate_history(symbol, start_price)
        for row in history:
            db.add(Candle(security_id=security.id, is_mock=True, **row))

    await db.commit()


async def seed_historical_universe_if_needed(db: AsyncSession) -> None:
    """Idempotent, and deliberately independent of seed_if_needed() (not
    nested inside it) — the same "seed only runs once" gotcha already hit
    three times this session (news, macro vintage) would otherwise apply
    here too, since this repo's real dev database's `securities` table is
    long since non-empty. Seeds exactly 2 dedicated historical-only
    securities (market_data/historical_seed_data.py) — never added to or
    removed from the live tradable universe, just proof that
    list_securities_as_of() is a real point-in-time query and not a
    trivial pass-through. `is_tradable=False` keeps them out of
    list_securities() (frontend dropdowns), live tick seeding, and the
    fundamentals/corporate-actions domains' own direct seeding queries."""
    symbol, name, sector, start_price, listed_date, delisted_date = DELISTED_SECURITY
    existing = await get_security_by_symbol(db, symbol)
    if existing is not None:
        return

    delisted = Security(
        symbol=symbol,
        name=name,
        sector=sector,
        is_mock=True,
        is_tradable=False,
        listed_date=listed_date,
        delisted_date=delisted_date,
    )
    db.add(delisted)
    await db.flush()
    for row in provider.generate_history(symbol, start_price, end_date=delisted_date):
        db.add(Candle(security_id=delisted.id, is_mock=True, **row))
    db.add(
        CorporateAction(
            security_id=delisted.id,
            action_type=ActionType.DELISTING,
            announcement_date=delisted_date - timedelta(days=60),
            ex_date=delisted_date,
            effective_date=delisted_date,
            source="mock",
            is_mock=True,
        )
    )

    m_symbol, m_name, m_sector, m_start_price, m_listed_date, m_delisted_date, merged_into_symbol = MERGED_SECURITY
    merged_target = await get_security_by_symbol(db, merged_into_symbol)
    merged = Security(
        symbol=m_symbol,
        name=m_name,
        sector=m_sector,
        is_mock=True,
        is_tradable=False,
        listed_date=m_listed_date,
        delisted_date=m_delisted_date,
    )
    db.add(merged)
    await db.flush()
    for row in provider.generate_history(m_symbol, m_start_price, end_date=m_delisted_date):
        db.add(Candle(security_id=merged.id, is_mock=True, **row))
    db.add(
        CorporateAction(
            security_id=merged.id,
            action_type=ActionType.MERGER,
            new_security_id=merged_target.id if merged_target else None,
            announcement_date=m_delisted_date - timedelta(days=90),
            ex_date=m_delisted_date,
            effective_date=m_delisted_date,
            source="mock",
            is_mock=True,
        )
    )

    await db.commit()


async def list_securities(db: AsyncSession, *, include_delisted: bool = False) -> list[Security]:
    """Default excludes non-tradable (historical-only) securities — this is
    the live tradable universe every existing caller (frontend dropdowns,
    live tick seeding, other domains' own seeding queries) has always
    meant by "all securities," and stays that way by default so adding
    historical-only securities can never silently change their behavior.
    `include_delisted=True` is for callers that genuinely want the full
    roster (e.g. an admin view) — for the actual point-in-time survivorship
    query, see list_securities_as_of() below."""
    stmt = select(Security).order_by(Security.is_index.desc(), Security.symbol)
    if not include_delisted:
        stmt = stmt.where(Security.is_tradable.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_securities_as_of(db: AsyncSession, as_of: date) -> list[Security]:
    """The actual survivorship-bias fix (Tier 1): a security is part of the
    universe "as of" a date if it had been listed by then (or its listing
    date is unknown — null, not a false claim of "always existed") AND it
    had not yet been delisted by then. A query for a PAST date correctly
    includes a security that has since been delisted/merged — the entire
    point of point-in-time discipline (§15, same as fundamentals/corporate
    actions/macro vintage) applied to universe membership itself, not just
    to a single security's own data."""
    result = await db.execute(
        select(Security)
        .where(
            Security.is_index.is_(False),
            or_(Security.listed_date.is_(None), Security.listed_date <= as_of),
            or_(Security.delisted_date.is_(None), Security.delisted_date > as_of),
        )
        .order_by(Security.symbol)
    )
    return list(result.scalars().all())


async def get_security_by_symbol(db: AsyncSession, symbol: str) -> Security | None:
    result = await db.execute(select(Security).where(Security.symbol == symbol.upper()))
    return result.scalar_one_or_none()


async def get_candles(db: AsyncSession, security_id: uuid.UUID, limit: int = 180) -> list[Candle]:
    result = await db.execute(
        select(Candle).where(Candle.security_id == security_id).order_by(Candle.trade_date.desc()).limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def get_daily_returns(db: AsyncSession, security_id: uuid.UUID, lookback: int = 90) -> dict:
    """Close-over-close daily returns, oldest first. Shared by the portfolio
    engine (domains/portfolios) and the risk/simulation engines
    (domains/risk, domains/simulation) — all built on the same mock candle
    history, see docs/ARCHITECTURE.md."""
    candles = await get_candles(db, security_id, limit=lookback)
    closes = [float(c.close) for c in candles]
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1]]
    return {"dates": [c.trade_date for c in candles[1:]], "returns": returns}


class LiveMarketState:
    """In-memory last-traded price simulator, seeded from each security's
    latest mock candle close. This intentionally does not touch the database
    on every tick — ticking is a display simulation, not a data-write path."""

    def __init__(self) -> None:
        self._prices: dict[str, float] = {}
        self._prev_close: dict[str, float] = {}
        self._updated_at: dict[str, datetime] = {}

    async def init_from_db(self, db: AsyncSession) -> None:
        securities = await list_securities(db)
        for security in securities:
            candles = await get_candles(db, security.id, limit=1)
            if not candles:
                continue
            last_close = float(candles[-1].close)
            self._prices[security.symbol] = last_close
            self._prev_close[security.symbol] = last_close
            self._updated_at[security.symbol] = datetime.now(timezone.utc)

    def tick_all(self) -> list[dict]:
        changes = []
        for symbol, price in self._prices.items():
            new_price = provider.tick(symbol, price)
            self._prices[symbol] = new_price
            self._updated_at[symbol] = datetime.now(timezone.utc)
            changes.append(self.get_quote(symbol))
        return changes

    def get_quote(self, symbol: str) -> dict | None:
        if symbol not in self._prices:
            return None
        last_price = self._prices[symbol]
        prev_close = self._prev_close[symbol]
        change_pct = ((last_price - prev_close) / prev_close) * 100 if prev_close else 0.0
        return {
            "symbol": symbol,
            "last_price": last_price,
            "prev_close": prev_close,
            "change_pct": round(change_pct, 3),
            "as_of": self._updated_at[symbol],
            "is_mock": True,
        }

    def all_quotes(self) -> list[dict]:
        return [q for symbol in self._prices if (q := self.get_quote(symbol)) is not None]

    def last_tick_at(self) -> datetime | None:
        """Used by the admin system-health view to show market-data
        freshness."""
        return max(self._updated_at.values(), default=None)


live_market_state = LiveMarketState()
