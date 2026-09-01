"""Ratio/valuation engine — pure functions, no I/O, unit-tested with fixed
input -> hand-computed expected-output fixtures
(tests/test_fundamentals_analytics.py), same discipline as
domains/risk/analytics.py and domains/options/pricing.py. Every function
takes plain numbers, never a DB session — callers (domains/fundamentals/service.py)
are responsible for resolving the point-in-time statement and price first.
"""


def roe_pct(pat: float, total_equity: float) -> float | None:
    if total_equity == 0:
        return None
    return round(pat / total_equity * 100, 3)


def roce_pct(ebit: float, total_assets: float, current_liabilities: float) -> float | None:
    capital_employed = total_assets - current_liabilities
    if capital_employed == 0:
        return None
    return round(ebit / capital_employed * 100, 3)


def roa_pct(pat: float, total_assets: float) -> float | None:
    if total_assets == 0:
        return None
    return round(pat / total_assets * 100, 3)


def debt_to_equity(total_debt: float, total_equity: float) -> float | None:
    if total_equity == 0:
        return None
    return round(total_debt / total_equity, 4)


def interest_coverage(ebit: float, interest_expense: float) -> float | None:
    if interest_expense == 0:
        return None
    return round(ebit / interest_expense, 3)


def current_ratio(current_assets: float, current_liabilities: float) -> float | None:
    if current_liabilities == 0:
        return None
    return round(current_assets / current_liabilities, 3)


def asset_turnover(revenue: float, total_assets: float) -> float | None:
    if total_assets == 0:
        return None
    return round(revenue / total_assets, 4)


def market_cap(price: float, shares_outstanding: float | None) -> float | None:
    if not shares_outstanding:
        return None
    return round(price * shares_outstanding, 2)


def pe_ratio(price: float, eps: float) -> float | None:
    if eps == 0:
        return None
    return round(price / eps, 3)


def pb_ratio(price: float, total_equity: float, shares_outstanding: float | None) -> float | None:
    if not shares_outstanding:
        return None
    book_value_per_share = total_equity / shares_outstanding
    if book_value_per_share == 0:
        return None
    return round(price / book_value_per_share, 3)


def enterprise_value(mcap: float | None, total_debt: float, cash_and_equivalents: float) -> float | None:
    if mcap is None:
        return None
    return round(mcap + total_debt - cash_and_equivalents, 2)


def ev_to_ebitda(ev: float | None, ebitda: float) -> float | None:
    if ev is None or ebitda == 0:
        return None
    return round(ev / ebitda, 3)


def ev_to_sales(ev: float | None, revenue: float) -> float | None:
    if ev is None or revenue == 0:
        return None
    return round(ev / revenue, 3)


def fcf_yield_pct(free_cash_flow: float, mcap: float | None) -> float | None:
    if not mcap:
        return None
    return round(free_cash_flow / mcap * 100, 3)
