import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.audit.service import log_action
from app.domains.market_data import service as market_service
from app.domains.market_data.service import live_market_state
from app.domains.portfolios.analytics import (
    HoldingInput,
    compute_annualized_volatility_pct,
    compute_beta,
    compute_concentration_score,
    compute_holding_metrics,
    compute_risk_score,
    compute_sector_exposure,
)
from app.models.portfolio import Holding, Portfolio, Transaction
from app.models.security import Security


class SecurityNotFoundError(Exception):
    pass


class PortfolioNotFoundError(Exception):
    pass


async def create_portfolio(db: AsyncSession, *, user_id: uuid.UUID, name: str, kind: str) -> Portfolio:
    portfolio = Portfolio(user_id=user_id, name=name, kind=kind)
    db.add(portfolio)
    await log_action(db, user_id=user_id, action="portfolio.create", input_data={"name": name, "kind": kind})
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


async def list_portfolios(db: AsyncSession, user_id: uuid.UUID) -> list[Portfolio]:
    result = await db.execute(select(Portfolio).where(Portfolio.user_id == user_id).order_by(Portfolio.created_at))
    return list(result.scalars().all())


async def get_portfolio(db: AsyncSession, *, portfolio_id: uuid.UUID, user_id: uuid.UUID) -> Portfolio:
    result = await db.execute(
        select(Portfolio)
        .options(selectinload(Portfolio.holdings))
        .where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise PortfolioNotFoundError(str(portfolio_id))
    return portfolio


async def add_holding(
    db: AsyncSession, *, portfolio_id: uuid.UUID, user_id: uuid.UUID, symbol: str, quantity: float, avg_price: float
) -> Holding:
    portfolio = await get_portfolio(db, portfolio_id=portfolio_id, user_id=user_id)

    security = await market_service.get_security_by_symbol(db, symbol)
    if security is None:
        raise SecurityNotFoundError(symbol)

    existing = next((h for h in portfolio.holdings if h.security_id == security.id), None)
    if existing is not None:
        new_quantity = existing.quantity + quantity
        existing.avg_price = ((existing.quantity * existing.avg_price) + (quantity * avg_price)) / new_quantity
        existing.quantity = new_quantity
        holding = existing
    else:
        holding = Holding(portfolio_id=portfolio.id, security_id=security.id, quantity=quantity, avg_price=avg_price)
        db.add(holding)

    db.add(
        Transaction(
            portfolio_id=portfolio.id,
            security_id=security.id,
            side="buy",
            quantity=quantity,
            price=avg_price,
            executed_at=datetime.now(timezone.utc),
        )
    )

    await log_action(
        db,
        user_id=user_id,
        action="portfolio.add_holding",
        input_data={"portfolio_id": str(portfolio_id), "symbol": symbol, "quantity": quantity, "avg_price": avg_price},
    )
    await db.commit()
    await db.refresh(holding)
    return holding


async def _security_by_id_map(db: AsyncSession, security_ids: list[uuid.UUID]) -> dict[uuid.UUID, Security]:
    if not security_ids:
        return {}
    result = await db.execute(select(Security).where(Security.id.in_(security_ids)))
    return {s.id: s for s in result.scalars().all()}


async def get_holdings_with_quotes(db: AsyncSession, portfolio: Portfolio) -> list[dict]:
    if not portfolio.holdings:
        return []

    securities = await _security_by_id_map(db, [h.security_id for h in portfolio.holdings])
    rows = []
    for holding in portfolio.holdings:
        security = securities[holding.security_id]
        quote = live_market_state.get_quote(security.symbol)
        last_price = quote["last_price"] if quote else float(holding.avg_price)
        prev_close = quote["prev_close"] if quote else float(holding.avg_price)

        metrics = compute_holding_metrics(
            HoldingInput(
                symbol=security.symbol,
                sector=security.sector,
                quantity=float(holding.quantity),
                avg_price=float(holding.avg_price),
                last_price=last_price,
                prev_close=prev_close,
            )
        )
        rows.append({"holding_id": holding.id, "security": security, "metrics": metrics})
    return rows


BETA_LOOKBACK_DAYS = 252


async def compute_beta_by_symbol(
    db: AsyncSession, rows: list[dict], *, lookback: int = BETA_LOOKBACK_DAYS
) -> dict[str, float]:
    """Each holding's beta vs NIFTY 50. Shared by domains/simulation
    (stress testing) and domains/events (event impact) so there is exactly
    one beta calculation in the codebase, not one per caller."""
    nifty = await market_service.get_security_by_symbol(db, "NIFTY50")
    if nifty is None:
        return {}
    benchmark_returns = (await market_service.get_daily_returns(db, nifty.id, lookback=lookback))["returns"]

    betas: dict[str, float] = {}
    for r in rows:
        symbol = r["security"].symbol
        if symbol == "NIFTY50":
            continue
        holding_returns = (await market_service.get_daily_returns(db, r["security"].id, lookback=lookback))["returns"]
        beta = compute_beta(holding_returns, benchmark_returns)
        if beta is not None:
            betas[symbol] = beta
    return betas


async def compute_portfolio_return_series(
    db: AsyncSession, portfolio: Portfolio, *, lookback: int = 90, rows: list[dict] | None = None
) -> list[float] | None:
    """Portfolio daily-return series: weighted by *current* market-value
    weights applied to each holding's historical daily return. This is a
    standard simplification when historical position sizes aren't tracked —
    documented here (and in docs/ARCHITECTURE.md) because it's a real
    analytical assumption, not hidden. Shared by the portfolio engine and the
    risk/simulation engines (domains/risk, domains/simulation) so they use
    the exact same methodology."""
    if rows is None:
        rows = await get_holdings_with_quotes(db, portfolio)
    total_value = sum(r["metrics"].market_value for r in rows)
    if not rows or total_value <= 0:
        return None

    weights = {r["security"].symbol: r["metrics"].market_value / total_value for r in rows}
    per_symbol_returns: dict[str, list[float]] = {}
    min_len = None
    for r in rows:
        data = await market_service.get_daily_returns(db, r["security"].id, lookback=lookback)
        per_symbol_returns[r["security"].symbol] = data["returns"]
        min_len = len(data["returns"]) if min_len is None else min(min_len, len(data["returns"]))

    if not min_len or min_len < 2:
        return None

    return [
        sum(weights[symbol] * per_symbol_returns[symbol][-min_len:][i] for symbol in weights)
        for i in range(min_len)
    ]


async def compute_portfolio_analytics(db: AsyncSession, portfolio: Portfolio) -> dict:
    rows = await get_holdings_with_quotes(db, portfolio)
    holding_metrics = [r["metrics"] for r in rows]

    total_value = sum(m.market_value for m in holding_metrics)
    total_invested = sum(m.invested_value for m in holding_metrics)
    total_pnl = total_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0.0
    day_pnl = sum(m.day_pnl for m in holding_metrics)
    day_pnl_pct = (day_pnl / total_value * 100) if total_value else 0.0

    sector_exposure = compute_sector_exposure(holding_metrics)
    concentration_score = compute_concentration_score([row["weight_pct"] for row in sector_exposure]) if sector_exposure else 0.0

    portfolio_returns = await compute_portfolio_return_series(db, portfolio, rows=rows)
    annualized_volatility_pct = compute_annualized_volatility_pct(portfolio_returns) if portfolio_returns else None

    beta_vs_nifty = None
    nifty = await market_service.get_security_by_symbol(db, "NIFTY50")
    if portfolio_returns and nifty:
        benchmark_data = await market_service.get_daily_returns(db, nifty.id, lookback=90)
        beta_vs_nifty = compute_beta(portfolio_returns, benchmark_data["returns"])

    risk_score = compute_risk_score(
        concentration_score=concentration_score,
        annualized_volatility_pct=annualized_volatility_pct,
        beta=beta_vs_nifty,
    )

    return {
        "portfolio_id": str(portfolio.id),
        "total_value": round(total_value, 2),
        "total_invested": round(total_invested, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 3),
        "day_pnl": round(day_pnl, 2),
        "day_pnl_pct": round(day_pnl_pct, 3),
        "holdings_count": len(rows),
        "sector_exposure": sector_exposure,
        "concentration_score": concentration_score,
        "annualized_volatility_pct": annualized_volatility_pct,
        "beta_vs_nifty": beta_vs_nifty,
        "risk_score": risk_score,
        "is_mock": True,
    }
