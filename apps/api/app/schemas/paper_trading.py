import datetime
import uuid

from pydantic import BaseModel, Field

from app.schemas.portfolio import SectorExposure


class PaperPortfolioOut(BaseModel):
    id: uuid.UUID
    name: str
    cash_balance: float
    is_mock: bool = True


class PlaceOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0)


class OrderOut(BaseModel):
    id: uuid.UUID
    symbol: str
    side: str
    quantity: float
    requested_price: float
    fill_price: float | None
    slippage_pct: float | None
    brokerage_fee: float | None
    status: str
    rejection_reason: str | None
    created_at: datetime.datetime
    is_mock: bool = True


class TradePreviewOut(BaseModel):
    symbol: str
    side: str
    quantity: float
    estimated_fill_price: float
    estimated_slippage_pct: float
    estimated_brokerage: float
    estimated_total: float
    cash_before: float
    cash_after: float
    affordable: bool
    concentration_score_before: float
    concentration_score_after: float
    sector_exposure_after: list[SectorExposure]
    is_mock: bool = True


class OrderEvaluationOut(BaseModel):
    order_id: uuid.UUID
    symbol: str | None
    side: str
    status: str
    fill_price: float | None
    range_30d_low: float | None
    range_30d_high: float | None
    fill_percentile_in_30d_range: float | None
    slippage_pct: float | None
    brokerage_fee: float | None
    assumptions: str
    is_mock: bool = True
