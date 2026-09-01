import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.service import log_action
from app.domains.market_data.service import get_candles, get_security_by_symbol, live_market_state
from app.domains.paper_trading.pricing import apply_slippage, compute_brokerage
from app.domains.portfolios.analytics import (
    HoldingInput,
    compute_concentration_score,
    compute_holding_metrics,
    compute_sector_exposure,
)
from app.domains.portfolios.service import get_holdings_with_quotes
from app.domains.portfolios.service import get_portfolio as get_portfolio_with_holdings
from app.models.order import Order
from app.models.portfolio import Holding, Portfolio, Transaction
from app.models.security import Security

STARTING_CAPITAL = 1_000_000.0  # ₹10 lakh virtual capital — see docs/ARCHITECTURE.md Phase 4


class NotAPaperPortfolioError(Exception):
    pass


class UnknownSymbolError(Exception):
    pass


async def get_or_create_paper_portfolio(db: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    result = await db.execute(select(Portfolio.id).where(Portfolio.user_id == user_id, Portfolio.kind == "paper"))
    existing_id = result.scalar_one_or_none()

    if existing_id is None:
        portfolio = Portfolio(user_id=user_id, name="Paper Trading", kind="paper", cash_balance=STARTING_CAPITAL)
        db.add(portfolio)
        await log_action(
            db, user_id=user_id, action="paper.create_account", input_data={"starting_capital": STARTING_CAPITAL}
        )
        await db.commit()
        existing_id = portfolio.id

    return await get_portfolio_with_holdings(db, portfolio_id=existing_id, user_id=user_id)


def _find_holding(portfolio: Portfolio, security_id: uuid.UUID) -> Holding | None:
    return next((h for h in portfolio.holdings if h.security_id == security_id), None)


async def _resolve_quote(db: AsyncSession, symbol: str) -> tuple[Security, dict]:
    security = await get_security_by_symbol(db, symbol)
    if security is None:
        raise UnknownSymbolError(symbol)
    quote = live_market_state.get_quote(security.symbol)
    if quote is None:
        raise UnknownSymbolError(symbol)
    return security, quote


async def place_order(
    db: AsyncSession, *, portfolio: Portfolio, symbol: str, side: str, quantity: float, user_id: uuid.UUID
) -> Order:
    if portfolio.kind != "paper":
        raise NotAPaperPortfolioError("Orders can only be placed against a paper trading portfolio.")

    security, quote = await _resolve_quote(db, symbol)
    requested_price = quote["last_price"]
    fill_price, slippage_pct = apply_slippage(requested_price, side)
    order_value = fill_price * quantity
    brokerage = compute_brokerage(order_value)
    existing_holding = _find_holding(portfolio, security.id)
    cash = float(portfolio.cash_balance or 0.0)

    async def _reject(reason: str) -> Order:
        order = Order(
            portfolio_id=portfolio.id,
            security_id=security.id,
            side=side,
            quantity=quantity,
            requested_price=requested_price,
            fill_price=None,
            slippage_pct=None,
            brokerage_fee=None,
            status="rejected",
            rejection_reason=reason,
        )
        db.add(order)
        await log_action(
            db,
            user_id=user_id,
            action="paper.order_rejected",
            input_data={"symbol": symbol, "side": side, "quantity": quantity},
            output_data={"reason": reason},
            result="rejected",
        )
        await db.commit()
        await db.refresh(order)
        return order

    if side == "buy":
        total_cost = order_value + brokerage
        if total_cost > cash:
            return await _reject(f"Insufficient cash: order needs ₹{total_cost:.2f}, portfolio has ₹{cash:.2f}.")

        portfolio.cash_balance = cash - total_cost
        if existing_holding is not None:
            existing_qty = float(existing_holding.quantity)
            new_qty = existing_qty + quantity
            existing_holding.avg_price = (
                existing_qty * float(existing_holding.avg_price) + quantity * fill_price
            ) / new_qty
            existing_holding.quantity = new_qty
        else:
            db.add(Holding(portfolio_id=portfolio.id, security_id=security.id, quantity=quantity, avg_price=fill_price))

    else:  # sell
        held_qty = float(existing_holding.quantity) if existing_holding else 0.0
        if quantity > held_qty:
            return await _reject(f"Insufficient holding: trying to sell {quantity}, only hold {held_qty}.")

        proceeds = order_value - brokerage
        portfolio.cash_balance = cash + proceeds
        remaining = held_qty - quantity
        if remaining <= 0:
            await db.delete(existing_holding)
        else:
            existing_holding.quantity = remaining  # avg_price is unchanged by a partial sell

    order = Order(
        portfolio_id=portfolio.id,
        security_id=security.id,
        side=side,
        quantity=quantity,
        requested_price=requested_price,
        fill_price=fill_price,
        slippage_pct=slippage_pct,
        brokerage_fee=brokerage,
        status="filled",
        rejection_reason=None,
    )
    db.add(order)
    await db.flush()  # populate order.id for the Transaction FK below

    db.add(
        Transaction(
            portfolio_id=portfolio.id,
            security_id=security.id,
            order_id=order.id,
            side=side,
            quantity=quantity,
            price=fill_price,
            executed_at=datetime.now(timezone.utc),
        )
    )

    await log_action(
        db,
        user_id=user_id,
        action=f"paper.order_{side}",
        input_data={"symbol": symbol, "side": side, "quantity": quantity},
        output_data={"fill_price": fill_price, "brokerage_fee": brokerage, "slippage_pct": slippage_pct},
    )
    await db.commit()
    await db.refresh(order)
    return order


async def list_orders(db: AsyncSession, portfolio_id: uuid.UUID, limit: int = 50) -> list[Order]:
    result = await db.execute(
        select(Order).where(Order.portfolio_id == portfolio_id).order_by(Order.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_order(db: AsyncSession, order_id: uuid.UUID, portfolio_id: uuid.UUID) -> Order | None:
    result = await db.execute(select(Order).where(Order.id == order_id, Order.portfolio_id == portfolio_id))
    return result.scalar_one_or_none()


async def preview_trade(db: AsyncSession, portfolio: Portfolio, *, symbol: str, side: str, quantity: float) -> dict:
    """No execution, no DB writes — a what-if preview for the AI coach and
    the order ticket UI to show real numbers before the user commits."""
    security, quote = await _resolve_quote(db, symbol)
    fill_price, slippage_pct = apply_slippage(quote["last_price"], side)
    order_value = fill_price * quantity
    brokerage = compute_brokerage(order_value)
    cash = float(portfolio.cash_balance or 0.0)
    existing_holding = _find_holding(portfolio, security.id)

    if side == "buy":
        total = order_value + brokerage
        cash_after = cash - total
        affordable = total <= cash
    else:
        held_qty = float(existing_holding.quantity) if existing_holding else 0.0
        total = order_value - brokerage
        cash_after = cash + total
        affordable = quantity <= held_qty

    rows = await get_holdings_with_quotes(db, portfolio)
    current_metrics = {r["security"].symbol: r["metrics"] for r in rows}

    before_exposure = compute_sector_exposure(list(current_metrics.values()))
    before_concentration = (
        compute_concentration_score([row["weight_pct"] for row in before_exposure]) if before_exposure else 0.0
    )

    hypothetical = dict(current_metrics)
    existing_metric = hypothetical.get(security.symbol)
    if side == "buy":
        prior_qty = existing_metric.quantity if existing_metric else 0.0
        prior_avg = existing_metric.avg_price if existing_metric else 0.0
        new_qty = prior_qty + quantity
        new_avg = (prior_qty * prior_avg + quantity * fill_price) / new_qty
    else:
        prior_qty = existing_metric.quantity if existing_metric else 0.0
        new_qty = prior_qty - quantity
        new_avg = existing_metric.avg_price if existing_metric else fill_price

    if new_qty > 0:
        hypothetical[security.symbol] = compute_holding_metrics(
            HoldingInput(
                symbol=security.symbol,
                sector=security.sector,
                quantity=new_qty,
                avg_price=new_avg,
                last_price=fill_price,
                prev_close=quote["prev_close"],
            )
        )
    else:
        hypothetical.pop(security.symbol, None)

    after_exposure = compute_sector_exposure(list(hypothetical.values()))
    after_concentration = (
        compute_concentration_score([row["weight_pct"] for row in after_exposure]) if after_exposure else 0.0
    )

    return {
        "symbol": security.symbol,
        "side": side,
        "quantity": quantity,
        "estimated_fill_price": fill_price,
        "estimated_slippage_pct": slippage_pct,
        "estimated_brokerage": brokerage,
        "estimated_total": round(total, 2),
        "cash_before": round(cash, 2),
        "cash_after": round(cash_after, 2),
        "affordable": affordable,
        "concentration_score_before": before_concentration,
        "concentration_score_after": after_concentration,
        "sector_exposure_after": after_exposure,
        "is_mock": True,
    }


async def evaluate_order(db: AsyncSession, order: Order) -> dict:
    """Entry-quality evaluation only — see docs/ARCHITECTURE.md Phase 4
    trade-offs for why this isn't a delayed/retrospective outcome review."""
    security = await db.get(Security, order.security_id)
    candles = await get_candles(db, order.security_id, limit=30)
    closes = [float(c.close) for c in candles]
    range_low = min(closes) if closes else None
    range_high = max(closes) if closes else None
    fill_price = float(order.fill_price) if order.fill_price is not None else None

    fill_percentile = None
    if fill_price is not None and range_low is not None and range_high is not None and range_high > range_low:
        fill_percentile = round((fill_price - range_low) / (range_high - range_low) * 100, 1)

    return {
        "order_id": str(order.id),
        "symbol": security.symbol if security else None,
        "side": order.side,
        "status": order.status,
        "fill_price": fill_price,
        "range_30d_low": range_low,
        "range_30d_high": range_high,
        "fill_percentile_in_30d_range": fill_percentile,
        "slippage_pct": float(order.slippage_pct) if order.slippage_pct is not None else None,
        "brokerage_fee": float(order.brokerage_fee) if order.brokerage_fee is not None else None,
        "assumptions": (
            "Evaluates entry quality only — where the fill price sits in the last 30 trading days' range "
            "(0 = at the 30-day low, 100 = at the 30-day high). Does not evaluate how the trade eventually "
            "turned out, which isn't knowable yet — a profitable trade isn't necessarily a good decision, "
            "and a losing one isn't necessarily a bad one."
        ),
        "is_mock": True,
    }
