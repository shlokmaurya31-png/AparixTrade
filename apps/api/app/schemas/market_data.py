import datetime
import uuid

from pydantic import BaseModel

from app.core.provenance import Provenance


class SecurityOut(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    sector: str
    is_index: bool
    is_mock: bool
    # Instrument master fields (Tier 1) — nullable, unpopulated for today's
    # seeded universe. See docs/APARIX_TIER1_AUDIT.md.
    isin: str | None = None
    segment: str | None = None
    asset_class: str | None = None
    lot_size: int | None = None
    tick_size: float | None = None

    model_config = {"from_attributes": True}


class QuoteOut(BaseModel):
    symbol: str
    last_price: float
    prev_close: float
    change_pct: float
    as_of: datetime.datetime
    is_mock: bool = True
    provenance: Provenance


class CandleOut(BaseModel):
    trade_date: datetime.date
    open: float
    high: float
    low: float
    close: float
    volume: int
