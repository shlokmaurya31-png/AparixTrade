import uuid

from pydantic import BaseModel


class MatrixOut(BaseModel):
    symbols: list[str]
    matrix: dict[str, dict[str, float | None]]


class RiskProfile(BaseModel):
    portfolio_id: uuid.UUID
    sample_size: int = 0
    risk_free_rate_annual_pct: float
    var_95_pct: float | None
    var_99_pct: float | None
    cvar_95_pct: float | None
    cvar_99_pct: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown_pct: float | None
    correlation_matrix: MatrixOut | None
    covariance_matrix: MatrixOut | None
    is_mock: bool = True
