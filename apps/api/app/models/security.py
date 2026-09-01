import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class Security(Base, UUIDPrimaryKeyMixin):
    """A tradeable instrument. Phase 1 only ever contains the seeded mock
    NIFTY-subset universe — see domains/market_data/seed_data.py."""

    __tablename__ = "securities"

    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), default="NSE", nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(20), default="equity", nullable=False)
    is_index: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Instrument master fields (Tier 1) — nullable, unpopulated for the
    # existing seeded universe (no ISIN/lot-size data exists for mock
    # securities). Present so a real NSE/BSE/MCX-backed provider has
    # somewhere real to write to later, not a speculative guess at what
    # that provider's shape will be — see docs/APARIX_TIER1_AUDIT.md.
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    segment: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "equity" | "index" | "derivative"
    asset_class: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "equity" | "commodity" | "currency"
    lot_size: Mapped[int | None] = mapped_column(nullable=True)
    tick_size: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)

    # Survivorship-bias / point-in-time universe fields (Tier 1). Every
    # security seeded before this existed keeps `is_tradable=True` and null
    # listed/delisted dates — meaning "no known constraint," not a false
    # claim about a real listing date this app never had data for. Only the
    # 2 dedicated historical-only securities (market_data/historical_seed_data.py)
    # ever get `is_tradable=False` — see list_securities_as_of() in
    # domains/market_data/service.py for the actual point-in-time query,
    # and docs/ARCHITECTURE.md §9 for why the live tradable universe is
    # never touched by this.
    is_tradable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    listed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delisted_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Candle(Base, UUIDPrimaryKeyMixin):
    """Daily OHLCV. Phase 1 data is entirely synthetic (seeded random walk),
    never presented as real historical prices — see MockMarketDataProvider."""

    __tablename__ = "candles"

    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), index=True, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    open: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    volume: Mapped[int] = mapped_column(nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
