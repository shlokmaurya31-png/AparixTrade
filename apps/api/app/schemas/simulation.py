import datetime
import uuid

from pydantic import BaseModel, Field


class MonteCarloRequest(BaseModel):
    method: str = Field(default="bootstrap", pattern="^(gbm|bootstrap)$")
    horizon_days: int = Field(default=30, ge=1, le=365)
    num_paths: int = Field(default=1000, ge=100, le=5000)


class MonteCarloResponse(BaseModel):
    method: str
    horizon_days: int
    num_paths: int
    current_value: float
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float
    probability_of_loss_pct: float
    sample_paths: list[list[float]]
    assumptions: str
    is_mock: bool = True


class StressTestRequest(BaseModel):
    target: str = Field(min_length=1, max_length=64, description='"NIFTY50", a sector name, or a holding symbol')
    shock_pct: float = Field(ge=-90, le=90)


class HoldingShockImpact(BaseModel):
    symbol: str
    sector: str
    shock_applied_pct: float
    impact: float
    basis: str


class StressTestResponse(BaseModel):
    target: str
    shock_pct: float
    portfolio_value_before: float
    estimated_impact: float
    estimated_impact_pct: float
    portfolio_value_after: float
    per_holding_impact: list[HoldingShockImpact]
    assumptions: str
    is_mock: bool = True


class BacktestRequest(BaseModel):
    initial_value: float = Field(default=100_000.0, gt=0)


class EquityPoint(BaseModel):
    trade_date: datetime.date
    value: float


class BacktestResponse(BaseModel):
    id: uuid.UUID | None = None
    initial_value: float
    final_value: float
    total_return_pct: float
    cagr_pct: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown_pct: float | None
    annualized_volatility_pct: float | None
    num_trading_days: int
    equity_curve: list[EquityPoint]
    assumptions: str
    created_at: datetime.datetime | None = None
    is_mock: bool = True
