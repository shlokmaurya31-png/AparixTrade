"""Fixed input -> expected-output fixtures for the risk engine, same
discipline as test_portfolio_analytics.py (docs/ARCHITECTURE.md §55):
expected values are derived from the mathematical definition independently
of the implementation, not copied from a first run of the code."""

import math

import pytest

from app.domains.risk.analytics import (
    build_index_from_returns,
    correlation_matrix,
    covariance_matrix,
    historical_cvar_pct,
    historical_var_pct,
    max_drawdown_pct,
    sharpe_ratio,
    sortino_ratio,
)

RF_ANNUAL = 0.065


def test_historical_var_and_cvar_known_distribution():
    # 100 evenly spaced returns from -0.050 to +0.049, already sorted ascending.
    returns = [(i - 50) / 1000 for i in range(100)]

    assert historical_var_pct(returns, 0.95) == pytest.approx(4.5)
    assert historical_var_pct(returns, 0.99) == pytest.approx(4.9)
    # CVaR95 tail = worst 5 obs: -0.050..-0.046 -> mean -0.048
    assert historical_cvar_pct(returns, 0.95) == pytest.approx(4.8)
    # CVaR99 tail = worst 1 obs: -0.050
    assert historical_cvar_pct(returns, 0.99) == pytest.approx(5.0)


def test_var_cvar_none_below_min_sample():
    assert historical_var_pct([0.01] * 5, 0.95) is None
    assert historical_cvar_pct([0.01] * 5, 0.95) is None


def test_sharpe_ratio_matches_independent_formula():
    returns = [0.01] * 10 + [-0.01] * 10
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(variance)
    rf_daily = RF_ANNUAL / 252
    expected = ((mean - rf_daily) / std) * math.sqrt(252)

    assert sharpe_ratio(returns, RF_ANNUAL) == pytest.approx(round(expected, 3))


def test_sortino_ratio_matches_independent_formula():
    returns = [0.02] * 15 + [-0.01] * 15
    mean = sum(returns) / len(returns)
    rf_daily = RF_ANNUAL / 252
    downside = [min(0.0, r - rf_daily) for r in returns]
    downside_dev = math.sqrt(sum(d * d for d in downside) / len(returns))
    expected = ((mean - rf_daily) / downside_dev) * math.sqrt(252)

    assert sortino_ratio(returns, RF_ANNUAL) == pytest.approx(round(expected, 3))


def test_sharpe_none_for_zero_volatility():
    assert sharpe_ratio([0.001] * 25, RF_ANNUAL) is None  # constant returns -> std 0


def test_build_index_from_returns_compounds_correctly():
    index = build_index_from_returns([0.10, -0.05, 0.02], start=100.0)
    assert index == pytest.approx([100.0, 110.0, 104.5, 106.59])


def test_max_drawdown_known_series():
    # Peak 110 at t=1, trough 80 at t=4 -> drawdown (110-80)/110 = 27.27%
    prices = [100, 110, 90, 95, 80, 120]
    assert max_drawdown_pct(prices) == pytest.approx(27.273, abs=1e-3)


def test_max_drawdown_monotonic_rise_is_zero():
    assert max_drawdown_pct([100, 110, 120, 130]) == pytest.approx(0.0)


def test_correlation_matrix_perfect_and_inverse():
    a = [0.01, 0.02, -0.01, 0.03, -0.02]
    inverse = [-x for x in a]
    result = correlation_matrix({"A": a, "A_COPY": a, "INVERSE": inverse})

    assert result["matrix"]["A"]["A_COPY"] == pytest.approx(1.0)
    assert result["matrix"]["A"]["INVERSE"] == pytest.approx(-1.0)
    assert result["matrix"]["A"]["A"] == pytest.approx(1.0)


def test_covariance_matrix_annualized_self_covariance():
    a = [0.01, 0.02, -0.01, 0.03, -0.02]
    result = covariance_matrix({"A": a})
    # variance(a, ddof=1) = 0.00043 -> annualized *252 = 0.10836
    assert result["matrix"]["A"]["A"] == pytest.approx(0.10836, abs=1e-5)
