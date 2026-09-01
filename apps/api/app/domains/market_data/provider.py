"""MarketDataProvider abstraction.

Aparix is designed so a real, licensed market data feed can be substituted
for MockMarketDataProvider without touching anything above this interface
(analytics, AI tools, API routes). See docs/ARCHITECTURE.md Trade-offs.
"""

import random
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta, timezone

HISTORY_DAYS = 365


class MarketDataProvider(ABC):
    @abstractmethod
    def generate_history(
        self, symbol: str, start_price: float, days: int, end_date: date | None = None
    ) -> list[dict]:
        """Returns `days` daily OHLCV rows ending the day before `end_date`
        (default: today), oldest first. `end_date` exists for historical-
        only securities (market_data/historical_seed_data.py) whose price
        history should stop at their real delisting date, not run forward
        to today for a security that no longer trades."""
        raise NotImplementedError

    @abstractmethod
    def tick(self, symbol: str, current_price: float) -> float:
        """Returns the next simulated last-traded price given the current one."""
        raise NotImplementedError


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic seeded random walk. Same symbol + start_price always
    produces the same history — reproducible for tests and demos. Every row
    this returns must be treated as DEMO DATA by callers, never as real
    historical prices."""

    def generate_history(
        self, symbol: str, start_price: float, days: int = HISTORY_DAYS, end_date: date | None = None
    ) -> list[dict]:
        rng = random.Random(f"aparix-mock-{symbol}")
        price = start_price
        anchor = end_date or datetime.now(timezone.utc).date()
        rows: list[dict] = []

        for offset in range(days, 0, -1):
            trade_date = anchor - timedelta(days=offset)
            if trade_date.weekday() >= 5:  # skip weekends — NSE is not open
                continue

            daily_return = rng.gauss(mu=0.0004, sigma=0.014)  # ~10%/yr drift, realistic daily vol
            open_price = price
            close_price = max(open_price * (1 + daily_return), 0.5)
            high_price = max(open_price, close_price) * (1 + abs(rng.gauss(0, 0.004)))
            low_price = min(open_price, close_price) * (1 - abs(rng.gauss(0, 0.004)))
            volume = int(rng.uniform(500_000, 8_000_000))

            rows.append(
                {
                    "trade_date": trade_date,
                    "open": round(open_price, 2),
                    "high": round(high_price, 2),
                    "low": round(low_price, 2),
                    "close": round(close_price, 2),
                    "volume": volume,
                }
            )
            price = close_price

        return rows

    def tick(self, symbol: str, current_price: float) -> float:
        rng = random.Random(f"{symbol}-{datetime.now(timezone.utc).timestamp()}")
        move = rng.gauss(mu=0.0, sigma=0.0015)
        return round(max(current_price * (1 + move), 0.5), 2)


def next_trade_date_history_end() -> date:
    return datetime.now(timezone.utc).date()
