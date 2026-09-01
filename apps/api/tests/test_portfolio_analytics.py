"""Deterministic input -> expected-output fixtures for the portfolio
calculation engine, per docs/ARCHITECTURE.md §55: these numbers are never
eyeballed, only asserted with fixed tolerances."""

import pytest

from app.domains.portfolios.analytics import (
    HoldingInput,
    compute_annualized_volatility_pct,
    compute_beta,
    compute_concentration_score,
    compute_holding_metrics,
    compute_risk_score,
    compute_sector_exposure,
)


def test_holding_metrics_gain():
    holding = HoldingInput(
        symbol="RELIANCE", sector="Energy", quantity=10, avg_price=2000.0, last_price=2200.0, prev_close=2150.0
    )
    metrics = compute_holding_metrics(holding)

    assert metrics.market_value == 22000.0
    assert metrics.invested_value == 20000.0
    assert metrics.unrealized_pnl == 2000.0
    assert metrics.unrealized_pnl_pct == pytest.approx(10.0)
    assert metrics.day_pnl == pytest.approx(500.0)  # 10 * (2200 - 2150)


def test_holding_metrics_loss():
    holding = HoldingInput(
        symbol="TCS", sector="Information Technology", quantity=5, avg_price=4200.0, last_price=4000.0, prev_close=4050.0
    )
    metrics = compute_holding_metrics(holding)

    assert metrics.unrealized_pnl == -1000.0
    assert metrics.unrealized_pnl_pct == pytest.approx(-1000 / 21000 * 100, abs=1e-3)
    assert metrics.day_pnl == pytest.approx(-250.0)


def test_sector_exposure_weights_sum_to_100():
    holdings = [
        compute_holding_metrics(HoldingInput("A", "Financials", 10, 100, 100, 100)),
        compute_holding_metrics(HoldingInput("B", "Energy", 10, 100, 100, 100)),
        compute_holding_metrics(HoldingInput("C", "Financials", 10, 100, 300, 300)),
    ]
    exposure = compute_sector_exposure(holdings)

    total_weight = sum(row["weight_pct"] for row in exposure)
    assert total_weight == pytest.approx(100.0)
    # Financials = (1000 + 3000) / (1000 + 1000 + 3000) = 80%
    financials = next(row for row in exposure if row["sector"] == "Financials")
    assert financials["weight_pct"] == pytest.approx(80.0)


def test_concentration_score_single_holding_is_max():
    assert compute_concentration_score([100.0]) == pytest.approx(100.0)


def test_concentration_score_equal_split_is_low():
    # 4 equal holdings -> HHI = 4 * (25/100)^2 = 0.25 -> score 25
    score = compute_concentration_score([25.0, 25.0, 25.0, 25.0])
    assert score == pytest.approx(25.0)


def test_concentration_score_empty_is_zero():
    assert compute_concentration_score([]) == 0.0


def test_volatility_needs_at_least_two_returns():
    assert compute_annualized_volatility_pct([]) is None
    assert compute_annualized_volatility_pct([0.01]) is None


def test_volatility_zero_for_constant_returns():
    assert compute_annualized_volatility_pct([0.01, 0.01, 0.01, 0.01]) == pytest.approx(0.0)


def test_beta_perfectly_correlated_equal_magnitude_is_one():
    returns = [0.01, -0.02, 0.015, 0.005, -0.01]
    assert compute_beta(returns, returns) == pytest.approx(1.0)


def test_beta_none_when_insufficient_data():
    assert compute_beta([0.01], [0.01]) is None


def test_risk_score_bounds_are_respected():
    low = compute_risk_score(concentration_score=10, annualized_volatility_pct=5, beta=0.6)
    high = compute_risk_score(concentration_score=90, annualized_volatility_pct=45, beta=1.6)

    assert 1 <= low <= 5
    assert 1 <= high <= 5
    assert high > low
