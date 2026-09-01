import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.market_data.provider import MockMarketDataProvider
from app.domains.market_data.seed_data import SEED_SECURITIES
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


async def list_securities(db: AsyncSession) -> list[Security]:
    result = await db.execute(select(Security).order_by(Security.is_index.desc(), Security.symbol))
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
