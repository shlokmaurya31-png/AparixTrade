import datetime as dt
import math

import pytest

from app.domains.portfolios.analytics import compute_annualized_volatility_pct
from app.domains.simulation.backtest import run_buy_and_hold_backtest
from app.domains.simulation.monte_carlo import simulate_bootstrap, simulate_gbm
from app.domains.simulation.stress_test import HoldingRow, apply_shock


# ── Monte Carlo ────────────────────────────────────────────────────────────


def test_gbm_simulation_is_deterministic_given_a_seed():
    returns = [0.001, -0.002, 0.003, -0.001, 0.002] * 6  # 30 obs, some variance
    result_a = simulate_gbm(current_value=100_000, daily_returns=returns, horizon_days=10, num_paths=50, seed=42)
    result_b = simulate_gbm(current_value=100_000, daily_returns=returns, horizon_days=10, num_paths=50, seed=42)

    assert result_a.p50 == result_b.p50
    assert result_a.sample_paths == result_b.sample_paths


def test_gbm_simulation_shape_and_bounds():
    returns = [0.001, -0.002, 0.003, -0.001, 0.002] * 6
    result = simulate_gbm(current_value=100_000, daily_returns=returns, horizon_days=10, num_paths=200, seed=1)

    assert result.num_paths == 200
    assert result.horizon_days == 10
    assert result.current_value == 100_000
    assert result.p5 <= result.p25 <= result.p50 <= result.p75 <= result.p95
    assert 0 <= result.probability_of_loss_pct <= 100
    assert len(result.sample_paths) <= 100  # MAX_SAMPLE_PATHS cap
    assert all(len(path) == 11 for path in result.sample_paths)  # start + horizon_days steps
    assert "Geometric Brownian Motion" in result.assumptions


def test_bootstrap_simulation_only_uses_observed_returns():
    # every return is identical -> every simulated path is forced deterministic
    returns = [0.01] * 20
    result = simulate_bootstrap(current_value=1000, daily_returns=returns, horizon_days=5, num_paths=10, seed=7)

    expected_terminal = 1000 * (1.01**5)
    assert result.p50 == pytest.approx(round(expected_terminal, 2))
    assert result.p5 == result.p95  # no variance possible when all returns are equal


def test_bootstrap_zero_paths_probability_of_loss_when_all_returns_positive():
    returns = [0.01] * 20
    result = simulate_bootstrap(current_value=1000, daily_returns=returns, horizon_days=5, num_paths=20, seed=3)
    assert result.probability_of_loss_pct == 0.0


# ── Stress test ─────────────────────────────────────────────────────────────


def test_stress_test_direct_symbol_shock_only_hits_that_holding():
    rows = [
        HoldingRow(symbol="RELIANCE", sector="Energy", market_value=10_000),
        HoldingRow(symbol="TCS", sector="Information Technology", market_value=10_000),
    ]
    result = apply_shock(rows, target="RELIANCE", shock_pct=-20, beta_by_symbol={})

    reliance_impact = next(r for r in result["per_holding_impact"] if r["symbol"] == "RELIANCE")
    tcs_impact = next(r for r in result["per_holding_impact"] if r["symbol"] == "TCS")

    assert reliance_impact["impact"] == pytest.approx(-2000.0)
    assert tcs_impact["impact"] == pytest.approx(0.0)
    assert result["estimated_impact"] == pytest.approx(-2000.0)
    assert result["portfolio_value_after"] == pytest.approx(18_000.0)


def test_stress_test_benchmark_shock_scales_by_beta():
    rows = [HoldingRow(symbol="RELIANCE", sector="Energy", market_value=10_000)]
    result = apply_shock(rows, target="NIFTY50", shock_pct=-10, beta_by_symbol={"RELIANCE": 1.5})

    # -10% * beta 1.5 = -15% applied
    assert result["per_holding_impact"][0]["shock_applied_pct"] == pytest.approx(-15.0)
    assert result["estimated_impact"] == pytest.approx(-1500.0)


def test_stress_test_defaults_beta_to_one_when_unknown():
    rows = [HoldingRow(symbol="ITC", sector="Consumer Staples", market_value=5_000)]
    result = apply_shock(rows, target="NIFTY50", shock_pct=-8, beta_by_symbol={})
    assert result["per_holding_impact"][0]["shock_applied_pct"] == pytest.approx(-8.0)


# ── Backtest ─────────────────────────────────────────────────────────────


def _d(offset: int) -> dt.date:
    return dt.date(2026, 1, 1) + dt.timedelta(days=offset)


def test_buy_and_hold_backtest_known_prices():
    candles_by_symbol = {
        "A": [
            {"trade_date": _d(0), "close": 100.0},
            {"trade_date": _d(1), "close": 110.0},
            {"trade_date": _d(2), "close": 121.0},
        ],
        "B": [
            {"trade_date": _d(0), "close": 50.0},
            {"trade_date": _d(1), "close": 45.0},
            {"trade_date": _d(2), "close": 40.0},
        ],
    }
    weights = {"A": 0.5, "B": 0.5}

    result = run_buy_and_hold_backtest(candles_by_symbol=candles_by_symbol, weights=weights, initial_value=1000.0)

    # units_A = 500/100 = 5, units_B = 500/50 = 10
    # day0: 5*100+10*50=1000, day1: 5*110+10*45=1000, day2: 5*121+10*40=1005
    values = [pt["value"] for pt in result["equity_curve"]]
    assert values == pytest.approx([1000.0, 1000.0, 1005.0])
    assert result["final_value"] == pytest.approx(1005.0)
    assert result["total_return_pct"] == pytest.approx(0.5)

    expected_cagr = ((1005.0 / 1000.0) ** (252 / 3) - 1) * 100
    assert result["cagr_pct"] == pytest.approx(round(expected_cagr, 3))

    # Only 2 daily returns generated from 3 days of data — below MIN_SAMPLE_SIZE (20),
    # so ratios must be None rather than a number computed from noise.
    assert result["sharpe_ratio"] is None
    assert result["sortino_ratio"] is None

    daily_returns = [0.0, 0.005]
    expected_vol = compute_annualized_volatility_pct(daily_returns)
    assert result["annualized_volatility_pct"] == pytest.approx(expected_vol)

    assert result["max_drawdown_pct"] == pytest.approx(0.0)  # never dips below a prior peak
    assert result["num_trading_days"] == 3


def test_backtest_empty_when_no_holdings():
    result = run_buy_and_hold_backtest(candles_by_symbol={}, weights={}, initial_value=50_000.0)
    assert result["equity_curve"] == []
    assert result["final_value"] == pytest.approx(50_000.0)
    assert result["cagr_pct"] is None
