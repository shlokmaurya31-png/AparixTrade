"""Portfolio calculation engine.

Every function here is a pure function over plain Python data — no DB, no I/O.
This is deliberate: these are the numbers the product is allowed to show, and
per docs/ARCHITECTURE.md they are tested with fixed input -> expected-output
fixtures (see apps/api/tests/test_portfolio_analytics.py), not eyeballed.
Nothing here is extrapolated beyond Complexity Levels 1-2 (see spec):
VaR/CVaR/Sharpe/Monte Carlo need the Phase 2 quant engine and must not be
faked here.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class HoldingInput:
    symbol: str
    sector: str
    quantity: float
    avg_price: float
    last_price: float
    prev_close: float


@dataclass(frozen=True)
class HoldingMetrics:
    symbol: str
    sector: str
    quantity: float
    avg_price: float
    last_price: float
    market_value: float
    invested_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    day_pnl: float


def compute_holding_metrics(holding: HoldingInput) -> HoldingMetrics:
    market_value = holding.quantity * holding.last_price
    invested_value = holding.quantity * holding.avg_price
    unrealized_pnl = market_value - invested_value
    unrealized_pnl_pct = (unrealized_pnl / invested_value * 100) if invested_value else 0.0
    day_pnl = holding.quantity * (holding.last_price - holding.prev_close)

    return HoldingMetrics(
        symbol=holding.symbol,
        sector=holding.sector,
        quantity=holding.quantity,
        avg_price=holding.avg_price,
        last_price=holding.last_price,
        market_value=round(market_value, 2),
        invested_value=round(invested_value, 2),
        unrealized_pnl=round(unrealized_pnl, 2),
        unrealized_pnl_pct=round(unrealized_pnl_pct, 3),
        day_pnl=round(day_pnl, 2),
    )


def compute_sector_exposure(holdings: list[HoldingMetrics]) -> list[dict]:
    total_value = sum(h.market_value for h in holdings)
    if total_value <= 0:
        return []

    by_sector: dict[str, float] = {}
    for h in holdings:
        by_sector[h.sector] = by_sector.get(h.sector, 0.0) + h.market_value

    exposure = [
        {"sector": sector, "value": round(value, 2), "weight_pct": round(value / total_value * 100, 2)}
        for sector, value in by_sector.items()
    ]
    return sorted(exposure, key=lambda row: row["weight_pct"], reverse=True)


def compute_concentration_score(weights_pct: list[float]) -> float:
    """Herfindahl-Hirschman Index normalized to 0-100.
    0 = perfectly diversified across many holdings, 100 = a single holding.
    HHI = sum(weight_fraction^2); for N equal holdings HHI = 1/N.
    We rescale so a single holding (HHI=1) maps to 100 and the
    fully-diversified limit (HHI->0) maps toward 0.
    """
    if not weights_pct:
        return 0.0
    fractions = [w / 100 for w in weights_pct]
    hhi = sum(f * f for f in fractions)
    return round(hhi * 100, 2)


def compute_annualized_volatility_pct(daily_returns: list[float]) -> float | None:
    """Standard deviation of daily returns, annualized with sqrt(252).
    Returns None (not 0) when there isn't enough history to be meaningful —
    an unstated assumption here would violate the no-fake-numbers principle.
    """
    if len(daily_returns) < 2:
        return None

    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    daily_vol = math.sqrt(variance)
    return round(daily_vol * math.sqrt(252) * 100, 2)


def compute_beta(portfolio_returns: list[float], benchmark_returns: list[float]) -> float | None:
    """Simple OLS beta: cov(portfolio, benchmark) / var(benchmark)."""
    n = min(len(portfolio_returns), len(benchmark_returns))
    if n < 2:
        return None

    p = portfolio_returns[-n:]
    b = benchmark_returns[-n:]
    p_mean = sum(p) / n
    b_mean = sum(b) / n

    covariance = sum((p[i] - p_mean) * (b[i] - b_mean) for i in range(n)) / (n - 1)
    benchmark_variance = sum((x - b_mean) ** 2 for x in b) / (n - 1)

    if benchmark_variance == 0:
        return None

    return round(covariance / benchmark_variance, 3)


def compute_risk_score(
    *, concentration_score: float, annualized_volatility_pct: float | None, beta: float | None
) -> int:
    """A single 1-5 headline figure for Complexity Level 1 users. Combines
    concentration (always available) with volatility/beta when there's
    enough history; scores conservatively (mid-point) when data is missing
    rather than pretending precision that isn't there."""
    score = 1.0

    if concentration_score >= 60:
        score += 2
    elif concentration_score >= 35:
        score += 1

    if annualized_volatility_pct is not None:
        if annualized_volatility_pct >= 30:
            score += 1.5
        elif annualized_volatility_pct >= 18:
            score += 0.75
    else:
        score += 0.5  # unknown volatility is itself a mild risk factor, not zero risk

    if beta is not None and beta >= 1.2:
        score += 0.5

    return max(1, min(5, round(score)))
