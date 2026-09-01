"""FundamentalsProvider abstraction (Tier 1 Session 2) — the pattern
proven by domains/market_data/provider.py, domains/macro/provider.py,
domains/ai/provider.py, and domains/broker/adapter.py, generalized to the
one domain the Tier 1 request names explicitly and that had no real data
behind it until now.

Only a Mock implementation exists this session: deterministic synthetic
income-statement/balance-sheet/cash-flow data per seeded security, for
annual and quarterly periods, generated once at seed time (not per
request) since a real filing doesn't change on every read the way a live
quote does. See docs/APARIX_TIER1_AUDIT.md / ARCHITECTURE.md §12.

Anchored to the security's actual mock spot price, not generated in
isolation: an earlier version picked revenue/PAT independently of price
and produced a P/E of ~1667 for a ~₹3000 stock — internally consistent
(every number traced correctly) but implausible on sight, exactly the
kind of "technically not fake, but not believable either" result this
codebase's mock data has never shipped elsewhere (compare
MockMarketDataProvider's realistic daily vol, or the options chain's
plausible IV skew). Working backward from price -> target P/E -> EPS ->
PAT -> revenue guarantees every ratio lands in a believable band by
construction, not by chance.
"""

import random
from abc import ABC, abstractmethod
from datetime import date, timedelta

ANNUAL_YEARS = 3
QUARTERLY_PERIODS = 4
TARGET_PE_RANGE = (14.0, 34.0)  # plausible Indian large-cap band
TARGET_ROE_RANGE = (0.10, 0.24)
PAT_MARGIN_RANGE = (0.08, 0.20)
SHARES_OUTSTANDING_RANGE = (25.0, 400.0)  # crore shares
REVENUE_GROWTH_MEAN = 0.11  # ~11%/yr, roughly matching the mock market data's ~10%/yr price drift
REVENUE_GROWTH_STD = 0.04
ANNUAL_ANNOUNCEMENT_LAG_DAYS = (45, 60)
QUARTERLY_ANNOUNCEMENT_LAG_DAYS = (30, 45)


def _fiscal_year_end(year: int) -> date:
    return date(year, 3, 31)  # Indian fiscal year — matches the product's India focus


def generate_statements(symbol: str, today: date, spot_price: float) -> list[dict]:
    """Deterministic seeded RNG (same approach as
    MockMarketDataProvider.generate_history) — same symbol + spot_price
    always produces the same statements, reproducible for tests and demos.
    Returns plain dicts; the caller (service.py) maps them onto
    FinancialStatement rows."""
    rng = random.Random(f"aparix-fundamentals-{symbol}")

    current_fy = today.year if today.month > 3 else today.year - 1

    # Anchor to price first — every downstream number is sized so the
    # *latest* year's ratios land in the target bands, then earlier years
    # are scaled back by compounding growth.
    target_pe = rng.uniform(*TARGET_PE_RANGE)
    target_roe = rng.uniform(*TARGET_ROE_RANGE)
    pat_margin = rng.uniform(*PAT_MARGIN_RANGE)
    shares_outstanding = rng.uniform(*SHARES_OUTSTANDING_RANGE)

    latest_eps = spot_price / target_pe
    latest_pat = latest_eps * shares_outstanding
    latest_revenue = latest_pat / pat_margin

    ebit_margin = pat_margin + rng.uniform(0.03, 0.08)
    ebitda_margin = ebit_margin + rng.uniform(0.03, 0.08)
    gross_margin = ebitda_margin + rng.uniform(0.10, 0.25)

    # Work backward from the latest (anchored) year to earlier years,
    # undoing one year of compounding growth (with a little noise) each
    # step, so revenue at years_ago=0 is exactly latest_revenue.
    revenue_by_years_ago = {0: latest_revenue}
    revenue = latest_revenue
    for years_ago in range(1, ANNUAL_YEARS):
        growth = rng.gauss(REVENUE_GROWTH_MEAN, REVENUE_GROWTH_STD)
        revenue = max(revenue / max(1 + growth, 0.5), 1.0)
        revenue_by_years_ago[years_ago] = revenue

    statements: list[dict] = []
    for years_ago in range(ANNUAL_YEARS - 1, -1, -1):
        fy = current_fy - years_ago
        statements.append(
            _build_statement(
                rng,
                period_end=_fiscal_year_end(fy),
                period_type="annual",
                fiscal_year=fy,
                revenue=revenue_by_years_ago[years_ago],
                gross_margin=gross_margin,
                ebitda_margin=ebitda_margin,
                ebit_margin=ebit_margin,
                pat_margin=pat_margin,
                target_roe=target_roe,
                balance_sheet_revenue_basis=revenue_by_years_ago[years_ago],
                shares_outstanding=shares_outstanding,
                announcement_lag_range=ANNUAL_ANNOUNCEMENT_LAG_DAYS,
            )
        )

    # A handful of trailing quarterly periods off the latest annual run-rate.
    quarterly_revenue = latest_revenue / 4
    quarter_end = _latest_quarter_end(today)
    for i in range(QUARTERLY_PERIODS):
        q_end = _shift_quarter(quarter_end, -i)
        growth = rng.gauss(REVENUE_GROWTH_MEAN / 4, REVENUE_GROWTH_STD / 2)
        q_revenue = max(quarterly_revenue * (1 + growth) ** i, 1.0)
        statements.append(
            _build_statement(
                rng,
                period_end=q_end,
                period_type="quarterly",
                fiscal_year=q_end.year if q_end.month > 3 else q_end.year - 1,
                revenue=q_revenue,
                gross_margin=gross_margin,
                ebitda_margin=ebitda_margin,
                ebit_margin=ebit_margin,
                pat_margin=pat_margin,
                target_roe=target_roe,
                # Balance sheet items (assets/equity/debt/cash) are a
                # point-in-time snapshot, not a flow — they don't shrink to
                # a quarter's size the way revenue/PAT do. Size them off
                # annualized revenue even for a quarterly statement, or
                # equity ends up ~4x too small relative to the annual
                # statements for the same company.
                balance_sheet_revenue_basis=q_revenue * 4,
                shares_outstanding=shares_outstanding,
                announcement_lag_range=QUARTERLY_ANNOUNCEMENT_LAG_DAYS,
            )
        )

    return statements


def _latest_quarter_end(today: date) -> date:
    quarter_ends = [date(today.year, m, d) for m, d in [(3, 31), (6, 30), (9, 30), (12, 31)]]
    past = [q for q in quarter_ends if q <= today]
    return max(past) if past else date(today.year - 1, 12, 31)


def _shift_quarter(q_end: date, offset: int) -> date:
    quarter_starts_by_month = [3, 6, 9, 12]
    idx = quarter_starts_by_month.index(q_end.month)
    total = idx + offset
    year = q_end.year + total // 4
    idx = total % 4
    month = quarter_starts_by_month[idx]
    day = 31 if month in (3, 12) else 30
    return date(year, month, day)


def _build_statement(
    rng: random.Random,
    *,
    period_end: date,
    period_type: str,
    fiscal_year: int,
    revenue: float,
    gross_margin: float,
    ebitda_margin: float,
    ebit_margin: float,
    pat_margin: float,
    target_roe: float,
    balance_sheet_revenue_basis: float,
    shares_outstanding: float,
    announcement_lag_range: tuple[int, int],
) -> dict:
    gross_profit = revenue * gross_margin
    ebitda = revenue * ebitda_margin
    ebit = revenue * ebit_margin
    interest_expense = revenue * rng.uniform(0.01, 0.03)
    pbt = ebit - interest_expense
    pat = revenue * pat_margin
    eps = round(pat / shares_outstanding, 4) if shares_outstanding else 0.0

    # Equity sized off *annualized* PAT (balance_sheet_revenue_basis x
    # pat_margin), not this period's raw PAT — for a quarterly statement,
    # `pat` is one quarter's profit, but equity is a point-in-time
    # snapshot that doesn't shrink to a quarter's size. Same target ROE
    # for every period (with a little noise) keeps ROE roughly stable
    # across the reported history instead of jumping discontinuously.
    annualized_pat = balance_sheet_revenue_basis * pat_margin
    period_roe = max(target_roe * rng.uniform(0.9, 1.1), 0.01)
    total_equity = annualized_pat / period_roe
    total_assets = max(balance_sheet_revenue_basis * rng.uniform(1.1, 1.8), total_equity * rng.uniform(1.6, 2.2))
    total_debt = total_assets * rng.uniform(0.15, 0.35)
    cash_and_equivalents = total_assets * rng.uniform(0.05, 0.15)
    total_liabilities = total_assets - total_equity
    current_assets = total_assets * rng.uniform(0.25, 0.45)
    current_liabilities = total_liabilities * rng.uniform(0.3, 0.5)

    cfo = ebitda * rng.uniform(0.6, 0.9)
    cfi = -abs(ebitda) * rng.uniform(0.2, 0.4)
    cff = -abs(pat) * rng.uniform(0.1, 0.3)
    free_cash_flow = cfo + cfi

    lag_days = rng.randint(*announcement_lag_range)
    announcement_date = period_end + timedelta(days=lag_days)

    return {
        "period_end": period_end,
        "period_type": period_type,
        "fiscal_year": fiscal_year,
        "announcement_date": announcement_date,
        "effective_date": announcement_date,
        "is_restated": False,
        "shares_outstanding": round(shares_outstanding, 2),
        "revenue": round(revenue, 2),
        "gross_profit": round(gross_profit, 2),
        "ebitda": round(ebitda, 2),
        "ebit": round(ebit, 2),
        "pbt": round(pbt, 2),
        "pat": round(pat, 2),
        "eps": eps,
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_liabilities, 2),
        "total_equity": round(total_equity, 2),
        "cash_and_equivalents": round(cash_and_equivalents, 2),
        "total_debt": round(total_debt, 2),
        "current_assets": round(current_assets, 2),
        "current_liabilities": round(current_liabilities, 2),
        "interest_expense": round(interest_expense, 2),
        "cfo": round(cfo, 2),
        "cfi": round(cfi, 2),
        "cff": round(cff, 2),
        "free_cash_flow": round(free_cash_flow, 2),
    }


class FundamentalsProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, symbol: str, today: date, spot_price: float) -> list[dict]:
        raise NotImplementedError


class MockFundamentalsProvider(FundamentalsProvider):
    name = "mock"

    def generate(self, symbol: str, today: date, spot_price: float) -> list[dict]:
        return generate_statements(symbol, today, spot_price)


def get_fundamentals_provider() -> FundamentalsProvider:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.fundamentals_provider == "mock":
        return MockFundamentalsProvider()
    raise ValueError(f"Unknown FUNDAMENTALS_PROVIDER: {settings.fundamentals_provider!r}")
