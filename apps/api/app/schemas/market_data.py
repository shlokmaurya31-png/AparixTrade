import datetime
import uuid

from pydantic import BaseModel


class SecurityOut(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    sector: str
    is_index: bool
    is_mock: bool

    model_config = {"from_attributes": True}


class QuoteOut(BaseModel):
    symbol: str
    last_price: float
    prev_close: float
    change_pct: float
    as_of: datetime.datetime
    is_mock: bool = True


class CandleOut(BaseModel):
    trade_date: datetime.date
    open: float
    high: float
    low: float
    close: float
    volume: int
