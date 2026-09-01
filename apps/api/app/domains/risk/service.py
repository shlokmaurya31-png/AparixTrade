from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.macro.service import get_indicator
from app.domains.market_data.service import get_daily_returns
from app.domains.portfolios.service import compute_portfolio_return_series, get_holdings_with_quotes
from app.domains.risk.analytics import (
    DEFAULT_RISK_FREE_RATE_ANNUAL,
    build_index_from_returns,
    correlation_matrix,
    covariance_matrix,
    historical_cvar_pct,
    historical_var_pct,
    max_drawdown_pct,
    sharpe_ratio,
    sortino_ratio,
)
from app.models.portfolio import Portfolio

# ~1 trading year. The mock market data generator seeds ~365 calendar days
# (domains/market_data/provider.py HISTORY_DAYS), so this is close to the
# ceiling of what's actually available — requesting more just returns
# whatever exists (see market_data.service.get_candles).
RISK_LOOKBACK_DAYS = 252


async def get_risk_free_rate_annual(db: AsyncSession) -> float:
    """Sourced from the mock macro domain's 10Y G-Sec yield (Phase 3) rather
    than a bare constant — still not live-fetched from RBI (see
    docs/ARCHITECTURE.md Phase 3 trade-offs), but structurally the right
    place for it now that domains/macro exists. Falls back to the constant
    if the indicator is somehow missing."""
    indicator = await get_indicator(db, "gsec_10y")
    return indicator.value / 100 if indicator else DEFAULT_RISK_FREE_RATE_ANNUAL


async def compute_risk_profile(db: AsyncSession, portfolio: Portfolio) -> dict:
    rows = await get_holdings_with_quotes(db, portfolio)
    risk_free_rate = await get_risk_free_rate_annual(db)

    empty: dict = {
        "portfolio_id": str(portfolio.id),
        "sample_size": 0,
        "risk_free_rate_annual_pct": round(risk_free_rate * 100, 2),
        "var_95_pct": None,
        "var_99_pct": None,
        "cvar_95_pct": None,
        "cvar_99_pct": None,
        "sharpe_ratio": None,
        "sortino_ratio": None,
        "max_drawdown_pct": None,
        "correlation_matrix": None,
        "covariance_matrix": None,
        "is_mock": True,
    }
    if not rows:
        return empty

    portfolio_returns = await compute_portfolio_return_series(db, portfolio, lookback=RISK_LOOKBACK_DAYS, rows=rows)
    if not portfolio_returns:
        return empty

    index = build_index_from_returns(portfolio_returns)

    # Per-holding return series, aligned to a common length, for the
    # correlation/covariance matrices — same alignment approach
    # compute_portfolio_return_series uses (trim to the shortest series).
    per_symbol_returns: dict[str, list[float]] = {}
    min_len = None
    for r in rows:
        data = await get_daily_returns(db, r["security"].id, lookback=RISK_LOOKBACK_DAYS)
        per_symbol_returns[r["security"].symbol] = data["returns"]
        min_len = len(data["returns"]) if min_len is None else min(min_len, len(data["returns"]))
    aligned = {symbol: rets[-min_len:] for symbol, rets in per_symbol_returns.items()} if min_len else {}

    return {
        "portfolio_id": str(portfolio.id),
        "sample_size": len(portfolio_returns),
        "risk_free_rate_annual_pct": round(risk_free_rate * 100, 2),
        "var_95_pct": historical_var_pct(portfolio_returns, 0.95),
        "var_99_pct": historical_var_pct(portfolio_returns, 0.99),
        "cvar_95_pct": historical_cvar_pct(portfolio_returns, 0.95),
        "cvar_99_pct": historical_cvar_pct(portfolio_returns, 0.99),
        "sharpe_ratio": sharpe_ratio(portfolio_returns, risk_free_rate),
        "sortino_ratio": sortino_ratio(portfolio_returns, risk_free_rate),
        "max_drawdown_pct": max_drawdown_pct(index),
        "correlation_matrix": correlation_matrix(aligned) if len(aligned) >= 2 else None,
        "covariance_matrix": covariance_matrix(aligned) if len(aligned) >= 2 else None,
        "is_mock": True,
    }
