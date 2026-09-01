import datetime
import uuid

from pydantic import BaseModel, Field


class BrokerStatusOut(BaseModel):
    connected: bool
    broker: str | None = None
    status: str | None = None  # "connected" | "expired" | None
    broker_user_id: str | None = None
    connected_at: datetime.datetime | None = None
    last_synced_at: datetime.datetime | None = None
    live_trading_enabled: bool


class LoginUrlOut(BaseModel):
    broker: str
    login_url: str


class ConnectRequest(BaseModel):
    # Only meaningful for broker == "zerodha" — the request_token Zerodha's
    # redirect appends to ZERODHA_REDIRECT_URL after the user logs in there.
    # Ignored by the mock adapter, which connects unconditionally.
    request_token: str | None = None


class BrokerHoldingOut(BaseModel):
    symbol: str
    name: str
    sector: str
    quantity: float
    avg_price: float
    last_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class BrokerPortfolioOut(BaseModel):
    id: uuid.UUID
    name: str
    holdings: list[BrokerHoldingOut]
    total_value: float
    is_mock: bool


class SyncResultOut(BaseModel):
    synced_holdings: int
    skipped_symbols: list[str] = Field(
        default_factory=list,
        description="Broker holdings for symbols outside this app's seeded security universe — not synced.",
    )
    synced_at: datetime.datetime


class PlaceBrokerOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0)


class BrokerOrderResultOut(BaseModel):
    broker_order_id: str
    status: str
    fill_price: float | None
    message: str | None
