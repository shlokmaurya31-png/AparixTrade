"""Risk calculation engine — Phase 2.

Same rules as domains/portfolios/analytics.py: every function here is pure
(no DB, no I/O) and unit-tested with fixed input -> expected-output fixtures
(tests/test_risk_analytics.py). Nothing here uses a distributional
assumption it can't show its work for — see docs/ARCHITECTURE.md Phase 2
trade-offs for why VaR/CVaR are historical-simulation (empirical
percentiles), not parametric.
"""

import math

TRADING_DAYS_PER_YEAR = 252

# Fixed assumption, not fetched live — Phase 1/2 has no macro/G-Sec data feed
# (that's Phase 3, RBI/macro ingestion). Every response using this states it
# explicitly rather than burying it, per the FACT vs MODEL OUTPUT distinction
# in docs/ARCHITECTURE.md §8.
DEFAULT_RISK_FREE_RATE_ANNUAL = 0.065

# Below this many daily observations, a percentile-based estimate (VaR/CVaR)
# or a ratio needing a stable std-dev (Sharpe/Sortino) is more noise than
# signal — return None rather than a number that looks precise but isn't.
MIN_SAMPLE_SIZE = 20


def historical_var_pct(returns: list[float], confidence: float) -> float | None:
    """Historical-simulation VaR as a positive loss percentage at the given
    confidence level (e.g. confidence=0.95 -> the 95% VaR)."""
    if len(returns) < MIN_SAMPLE_SIZE:
        return None
    sorted_returns = sorted(returns)
    index = max(0, min(int((1 - confidence) * len(sorted_returns)), len(sorted_returns) - 1))
    return round(-sorted_returns[index] * 100, 3)


def historical_cvar_pct(returns: list[float], confidence: float) -> float | None:
    """Expected Shortfall: average loss in the tail beyond the VaR cutoff."""
    if len(returns) < MIN_SAMPLE_SIZE:
        return None
    sorted_returns = sorted(returns)
    cutoff = max(1, int((1 - confidence) * len(sorted_returns)))
    tail = sorted_returns[:cutoff]
    return round(-(sum(tail) / len(tail)) * 100, 3)


def _daily_mean_and_std(returns: list[float]) -> tuple[float, float] | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return mean, math.sqrt(variance)


def sharpe_ratio(returns: list[float], risk_free_rate_annual: float = DEFAULT_RISK_FREE_RATE_ANNUAL) -> float | None:
    if len(returns) < MIN_SAMPLE_SIZE:
        return None
    stats = _daily_mean_and_std(returns)
    if stats is None or stats[1] == 0:
        return None
    mean_daily, std_daily = stats
    rf_daily = risk_free_rate_annual / TRADING_DAYS_PER_YEAR
    return round(((mean_daily - rf_daily) / std_daily) * math.sqrt(TRADING_DAYS_PER_YEAR), 3)


def sortino_ratio(returns: list[float], risk_free_rate_annual: float = DEFAULT_RISK_FREE_RATE_ANNUAL) -> float | None:
    if len(returns) < MIN_SAMPLE_SIZE:
        return None
    mean_daily = sum(returns) / len(returns)
    rf_daily = risk_free_rate_annual / TRADING_DAYS_PER_YEAR
    downside = [min(0.0, r - rf_daily) for r in returns]
    downside_variance = sum(d * d for d in downside) / len(returns)
    downside_dev = math.sqrt(downside_variance)
    if downside_dev == 0:
        return None
    return round(((mean_daily - rf_daily) / downside_dev) * math.sqrt(TRADING_DAYS_PER_YEAR), 3)


def build_index_from_returns(returns: list[float], start: float = 100.0) -> list[float]:
    """Synthetic price index compounding a return series — used to compute
    drawdown for a return series that has no natural price level of its own
    (e.g. the weighted portfolio return series)."""
    index = [start]
    for r in returns:
        index.append(index[-1] * (1 + r))
    return index


def max_drawdown_pct(price_series: list[float]) -> float | None:
    if len(price_series) < 2:
        return None
    peak = price_series[0]
    max_dd = 0.0
    for price in price_series:
        peak = max(peak, price)
        if peak > 0:
            max_dd = max(max_dd, (peak - price) / peak)
    return round(max_dd * 100, 3)


def _pearson_correlation(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 2:
        return None
    a, b = a[:n], b[:n]
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((x - mean_b) ** 2 for x in b)
    if var_a == 0 or var_b == 0:
        return None
    return cov / math.sqrt(var_a * var_b)


def correlation_matrix(returns_by_symbol: dict[str, list[float]]) -> dict:
    symbols = list(returns_by_symbol.keys())
    matrix = {
        s1: {s2: (round(r, 3) if (r := _pearson_correlation(returns_by_symbol[s1], returns_by_symbol[s2])) is not None else None) for s2 in symbols}
        for s1 in symbols
    }
    return {"symbols": symbols, "matrix": matrix}


def covariance_matrix(returns_by_symbol: dict[str, list[float]]) -> dict:
    """Annualized covariance (daily covariance * 252 trading days)."""
    symbols = list(returns_by_symbol.keys())
    matrix: dict[str, dict[str, float | None]] = {}
    for s1 in symbols:
        a = returns_by_symbol[s1]
        mean_a = sum(a) / len(a) if a else 0.0
        matrix[s1] = {}
        for s2 in symbols:
            b = returns_by_symbol[s2]
            n = min(len(a), len(b))
            if n < 2:
                matrix[s1][s2] = None
                continue
            mean_b = sum(b[:n]) / n
            cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n)) / (n - 1)
            matrix[s1][s2] = round(cov * TRADING_DAYS_PER_YEAR, 6)
    return {"symbols": symbols, "matrix": matrix}
