import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.service import log_action
from app.domains.market_data.service import get_candles
from app.domains.risk.service import get_risk_free_rate_annual
from app.domains.portfolios.service import (
    compute_beta_by_symbol,
    compute_portfolio_return_series,
    get_holdings_with_quotes,
)
from app.domains.simulation.backtest import run_buy_and_hold_backtest
from app.domains.simulation.monte_carlo import simulate_bootstrap, simulate_gbm
from app.domains.simulation.stress_test import HoldingRow, apply_shock
from app.models.backtest import Backtest
from app.models.portfolio import Portfolio

BACKTEST_LOOKBACK_DAYS = 300  # more than the ~260 trading days the mock generator produces
BETA_LOOKBACK_DAYS = 252


class InsufficientHistoryError(Exception):
    pass


async def run_monte_carlo(
    db: AsyncSession, portfolio: Portfolio, *, method: str, horizon_days: int, num_paths: int
) -> dict:
    rows = await get_holdings_with_quotes(db, portfolio)
    current_value = sum(r["metrics"].market_value for r in rows)
    if not rows or current_value <= 0:
        raise InsufficientHistoryError("Portfolio has no holdings to simulate.")

    daily_returns = await compute_portfolio_return_series(db, portfolio, lookback=BETA_LOOKBACK_DAYS, rows=rows)
    if not daily_returns or len(daily_returns) < 20:
        raise InsufficientHistoryError("Not enough price history across current holdings to run a simulation.")

    simulate = simulate_gbm if method == "gbm" else simulate_bootstrap
    result = simulate(
        current_value=current_value, daily_returns=daily_returns, horizon_days=horizon_days, num_paths=num_paths
    )
    return {
        "method": result.method,
        "horizon_days": result.horizon_days,
        "num_paths": result.num_paths,
        "current_value": result.current_value,
        "p5": result.p5,
        "p25": result.p25,
        "p50": result.p50,
        "p75": result.p75,
        "p95": result.p95,
        "probability_of_loss_pct": result.probability_of_loss_pct,
        "sample_paths": result.sample_paths,
        "assumptions": result.assumptions,
        "is_mock": True,
    }


async def run_stress_test(db: AsyncSession, portfolio: Portfolio, *, target: str, shock_pct: float) -> dict:
    rows = await get_holdings_with_quotes(db, portfolio)
    if not rows:
        raise InsufficientHistoryError("Portfolio has no holdings to stress test.")

    beta_lookup = await compute_beta_by_symbol(db, rows, lookback=BETA_LOOKBACK_DAYS)
    holding_rows = [
        HoldingRow(symbol=r["security"].symbol, sector=r["security"].sector, market_value=r["metrics"].market_value)
        for r in rows
    ]
    return apply_shock(holding_rows, target=target.upper(), shock_pct=shock_pct, beta_by_symbol=beta_lookup)


async def run_backtest(
    db: AsyncSession, portfolio: Portfolio, *, initial_value: float, persist: bool = True, user_id: uuid.UUID | None = None
) -> dict:
    rows = await get_holdings_with_quotes(db, portfolio)
    total_value = sum(r["metrics"].market_value for r in rows)
    if not rows or total_value <= 0:
        raise InsufficientHistoryError("Portfolio has no holdings to backtest.")

    weights = {r["security"].symbol: r["metrics"].market_value / total_value for r in rows}
    candles_by_symbol: dict[str, list[dict]] = {}
    for r in rows:
        candles = await get_candles(db, r["security"].id, limit=BACKTEST_LOOKBACK_DAYS)
        candles_by_symbol[r["security"].symbol] = [{"trade_date": c.trade_date, "close": float(c.close)} for c in candles]

    risk_free_rate = await get_risk_free_rate_annual(db)
    result = run_buy_and_hold_backtest(
        candles_by_symbol=candles_by_symbol,
        weights=weights,
        initial_value=initial_value,
        risk_free_rate_annual=risk_free_rate,
    )

    if persist:
        record = Backtest(portfolio_id=portfolio.id, params={"initial_value": initial_value}, results=result)
        db.add(record)
        await log_action(
            db, user_id=user_id, action="backtest.run", input_data={"portfolio_id": str(portfolio.id), "initial_value": initial_value}
        )
        await db.commit()
        await db.refresh(record)
        result = {**result, "id": str(record.id), "created_at": record.created_at.isoformat()}

    return result


async def list_backtests(db: AsyncSession, portfolio_id: uuid.UUID, limit: int = 20) -> list[Backtest]:
    result = await db.execute(
        select(Backtest).where(Backtest.portfolio_id == portfolio_id).order_by(Backtest.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
