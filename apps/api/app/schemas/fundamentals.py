import datetime

from pydantic import BaseModel

from app.core.provenance import Provenance


class FinancialStatementOut(BaseModel):
    symbol: str
    period_end: datetime.date
    period_type: str
    fiscal_year: int
    announcement_date: datetime.date
    effective_date: datetime.date
    is_restated: bool
    currency: str
    unit: str
    shares_outstanding: float | None

    revenue: float
    gross_profit: float
    ebitda: float
    ebit: float
    pbt: float
    pat: float
    eps: float

    total_assets: float
    total_liabilities: float
    total_equity: float
    cash_and_equivalents: float
    total_debt: float
    current_assets: float
    current_liabilities: float
    interest_expense: float

    cfo: float
    cfi: float
    cff: float
    free_cash_flow: float

    is_mock: bool = True
    provenance: Provenance


class RatiosOut(BaseModel):
    symbol: str
    as_of: datetime.date
    period_end: datetime.date
    price_used: float | None
    price_as_of: datetime.date | None

    roe_pct: float | None
    roce_pct: float | None
    roa_pct: float | None
    debt_to_equity: float | None
    interest_coverage: float | None
    current_ratio: float | None
    asset_turnover: float | None

    market_cap: float | None
    pe_ratio: float | None
    pb_ratio: float | None
    enterprise_value: float | None
    ev_to_ebitda: float | None
    ev_to_sales: float | None
    fcf_yield_pct: float | None

    assumptions: str
    is_mock: bool = True
