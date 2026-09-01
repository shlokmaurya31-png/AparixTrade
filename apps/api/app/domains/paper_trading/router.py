import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.paper_trading import service
from app.models.security import Security
from app.models.user import User
from app.schemas.paper_trading import (
    OrderEvaluationOut,
    OrderOut,
    PaperPortfolioOut,
    PlaceOrderRequest,
    TradePreviewOut,
)

# Paper trading is one account per user (see get_or_create_paper_portfolio) —
# routes resolve the portfolio from the authenticated user, not a path
# param, which also avoids any ambiguity with /portfolios/{portfolio_id}/...
# in domains/portfolios/router.py.
router = APIRouter(prefix="/paper", tags=["paper-trading"])


def _order_out(order, symbol: str) -> dict:
    return {
        "id": order.id,
        "symbol": symbol,
        "side": order.side,
        "quantity": order.quantity,
        "requested_price": order.requested_price,
        "fill_price": order.fill_price,
        "slippage_pct": order.slippage_pct,
        "brokerage_fee": order.brokerage_fee,
        "status": order.status,
        "rejection_reason": order.rejection_reason,
        "created_at": order.created_at,
    }


@router.get("/portfolio", response_model=PaperPortfolioOut)
async def get_paper_portfolio(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    portfolio = await service.get_or_create_paper_portfolio(db, current_user.id)
    return {"id": portfolio.id, "name": portfolio.name, "cash_balance": float(portfolio.cash_balance or 0.0)}


@router.post("/portfolio/preview", response_model=TradePreviewOut)
async def preview_trade(
    payload: PlaceOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    portfolio = await service.get_or_create_paper_portfolio(db, current_user.id)
    try:
        return await service.preview_trade(
            db, portfolio, symbol=payload.symbol.upper(), side=payload.side, quantity=payload.quantity
        )
    except service.UnknownSymbolError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown symbol: {exc}") from exc


@router.post("/portfolio/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def place_order(
    payload: PlaceOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    portfolio = await service.get_or_create_paper_portfolio(db, current_user.id)
    try:
        order = await service.place_order(
            db,
            portfolio=portfolio,
            symbol=payload.symbol.upper(),
            side=payload.side,
            quantity=payload.quantity,
            user_id=current_user.id,
        )
    except service.UnknownSymbolError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown symbol: {exc}") from exc
    except service.NotAPaperPortfolioError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _order_out(order, payload.symbol.upper())


@router.get("/portfolio/orders", response_model=list[OrderOut])
async def get_orders(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    portfolio = await service.get_or_create_paper_portfolio(db, current_user.id)
    orders = await service.list_orders(db, portfolio.id)

    symbols_by_security_id: dict[uuid.UUID, str] = {}
    for order in orders:
        if order.security_id not in symbols_by_security_id:
            security = await db.get(Security, order.security_id)
            symbols_by_security_id[order.security_id] = security.symbol if security else "?"

    return [_order_out(order, symbols_by_security_id[order.security_id]) for order in orders]


@router.get("/portfolio/orders/{order_id}/evaluation", response_model=OrderEvaluationOut)
async def get_order_evaluation(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    portfolio = await service.get_or_create_paper_portfolio(db, current_user.id)
    order = await service.get_order(db, order_id, portfolio.id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return await service.evaluate_order(db, order)
