import uuid

from pydantic import BaseModel, Field


class CreatePortfolioRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    # "paper" and "broker" are excluded here on purpose — both are singleton
    # accounts lazily created by their own domain service
    # (get_or_create_paper_portfolio / get_or_create_broker_portfolio), not
    # user-createable via this generic endpoint. A DB-level unique index
    # enforces "one per user" for each; going through this endpoint with
    # kind="paper"/"broker" would just 500 on the second attempt.
    kind: str = Field(default="long_term", pattern="^(long_term|trading|options|experimental)$")


class PortfolioOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: str

    model_config = {"from_attributes": True}


class AddHoldingRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    quantity: float = Field(gt=0)
    avg_price: float = Field(gt=0)


class HoldingOut(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    sector: str
    quantity: float
    avg_price: float
    last_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    is_mock: bool = True


class SectorExposure(BaseModel):
    sector: str
    weight_pct: float
    value: float


class PortfolioAnalytics(BaseModel):
    portfolio_id: uuid.UUID
    total_value: float
    total_invested: float
    total_pnl: float
    total_pnl_pct: float
    day_pnl: float
    day_pnl_pct: float
    holdings_count: int
    sector_exposure: list[SectorExposure]
    concentration_score: float = Field(description="0 (fully diversified) to 100 (single-holding), HHI-based")
    annualized_volatility_pct: float | None
    beta_vs_nifty: float | None
    risk_score: int = Field(description="1 (low) to 5 (high), Complexity Level 1 headline figure")
    is_mock: bool = True
