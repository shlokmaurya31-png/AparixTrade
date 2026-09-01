import datetime

from pydantic import BaseModel


class ExpiryListOut(BaseModel):
    symbol: str
    expiries: list[datetime.date]


class OptionContractOut(BaseModel):
    strike: float
    option_type: str  # "call" | "put"
    premium: float
    iv_pct: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


class OptionChainOut(BaseModel):
    symbol: str
    spot: float
    expiry: datetime.date
    days_to_expiry: int
    risk_free_rate_annual_pct: float
    contracts: list[OptionContractOut]
    is_mock: bool = True


class SingleOptionOut(BaseModel):
    symbol: str
    spot: float
    strike: float
    option_type: str
    expiry: datetime.date
    days_to_expiry: int
    premium: float
    iv_pct: float
    risk_free_rate_annual_pct: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    is_mock: bool = True
