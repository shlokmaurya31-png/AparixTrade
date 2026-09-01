"""Backtesting engine — Phase 2, buy-and-hold only.

No strategy DSL exists yet (that's its own project) — this answers "how
would today's portfolio weights have performed over the available history",
walking strictly forward through the mock daily candles with no look-ahead:
day i's valuation only ever uses candle data up to and including day i.
No transaction costs, slippage, or rebalancing are modeled — a single
notional entry at day 0, held throughout. See docs/ARCHITECTURE.md Phase 2
trade-offs.
"""

import datetime as dt

from app.domains.portfolios.analytics import compute_annualized_volatility_pct
from app.domains.risk.analytics import DEFAULT_RISK_FREE_RATE_ANNUAL, max_drawdown_pct, sharpe_ratio, sortino_ratio

TRADING_DAYS_PER_YEAR = 252

ASSUMPTIONS = (
    "Buy-and-hold using each holding's current portfolio weight, entered on the first available "
    "trading day in the mock history and held with no rebalancing. No transaction costs, slippage, "
    "brokerage, or taxes are modeled."
)


def run_buy_and_hold_backtest(
    *,
    candles_by_symbol: dict[str, list[dict]],
    weights: dict[str, float],
    initial_value: float,
    risk_free_rate_annual: float = DEFAULT_RISK_FREE_RATE_ANNUAL,
) -> dict:
    if not candles_by_symbol or not weights:
        return _empty_result(initial_value)

    min_len = min(len(candles) for candles in candles_by_symbol.values())
    if min_len < 2:
        return _empty_result(initial_value)

    # Align every symbol to the same trailing window so day i means the same
    # calendar day across all holdings (mock securities share the same
    # generation calendar, but this stays defensive rather than assuming it).
    aligned = {symbol: candles[-min_len:] for symbol, candles in candles_by_symbol.items()}
    dates: list[dt.date] = [c["trade_date"] for c in next(iter(aligned.values()))]

    units = {
        symbol: (initial_value * weight) / aligned[symbol][0]["close"] if aligned[symbol][0]["close"] else 0.0
        for symbol, weight in weights.items()
    }

    equity_curve = []
    for i in range(min_len):
        value = sum(units[symbol] * aligned[symbol][i]["close"] for symbol in weights)
        equity_curve.append({"trade_date": dates[i], "value": round(value, 2)})

    values = [pt["value"] for pt in equity_curve]
    daily_returns = [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values)) if values[i - 1]]

    years = min_len / TRADING_DAYS_PER_YEAR
    cagr_pct = ((values[-1] / values[0]) ** (1 / years) - 1) * 100 if years > 0 and values[0] > 0 else None

    return {
        "initial_value": round(initial_value, 2),
        "final_value": round(values[-1], 2),
        "total_return_pct": round((values[-1] - values[0]) / values[0] * 100, 3) if values[0] else 0.0,
        "cagr_pct": round(cagr_pct, 3) if cagr_pct is not None else None,
        "sharpe_ratio": sharpe_ratio(daily_returns, risk_free_rate_annual),
        "sortino_ratio": sortino_ratio(daily_returns, risk_free_rate_annual),
        "max_drawdown_pct": max_drawdown_pct(values),
        "annualized_volatility_pct": compute_annualized_volatility_pct(daily_returns),
        "num_trading_days": min_len,
        "equity_curve": equity_curve,
        "assumptions": ASSUMPTIONS,
        "is_mock": True,
    }


def _empty_result(initial_value: float) -> dict:
    return {
        "initial_value": round(initial_value, 2),
        "final_value": round(initial_value, 2),
        "total_return_pct": 0.0,
        "cagr_pct": None,
        "sharpe_ratio": None,
        "sortino_ratio": None,
        "max_drawdown_pct": None,
        "annualized_volatility_pct": None,
        "num_trading_days": 0,
        "equity_curve": [],
        "assumptions": ASSUMPTIONS,
        "is_mock": True,
    }
