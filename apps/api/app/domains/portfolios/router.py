import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.portfolios import service
from app.models.user import User
from app.schemas.portfolio import (
    AddHoldingRequest,
    CreatePortfolioRequest,
    HoldingOut,
    PortfolioAnalytics,
    PortfolioOut,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.post("", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    payload: CreatePortfolioRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> service.Portfolio:
    return await service.create_portfolio(db, user_id=current_user.id, name=payload.name, kind=payload.kind)


@router.get("", response_model=list[PortfolioOut])
async def list_portfolios(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list:
    return await service.list_portfolios(db, current_user.id)


@router.get("/{portfolio_id}/holdings", response_model=list[HoldingOut])
async def get_holdings(
    portfolio_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    try:
        portfolio = await service.get_portfolio(db, portfolio_id=portfolio_id, user_id=current_user.id)
    except service.PortfolioNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found") from exc

    rows = await service.get_holdings_with_quotes(db, portfolio)
    return [
        {
            "id": r["holding_id"],
            "symbol": r["security"].symbol,
            "name": r["security"].name,
            "sector": r["security"].sector,
            "quantity": r["metrics"].quantity,
            "avg_price": r["metrics"].avg_price,
            "last_price": r["metrics"].last_price,
            "market_value": r["metrics"].market_value,
            "unrealized_pnl": r["metrics"].unrealized_pnl,
            "unrealized_pnl_pct": r["metrics"].unrealized_pnl_pct,
        }
        for r in rows
    ]


@router.post("/{portfolio_id}/holdings", response_model=HoldingOut, status_code=status.HTTP_201_CREATED)
async def add_holding(
    portfolio_id: uuid.UUID,
    payload: AddHoldingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        holding = await service.add_holding(
            db,
            portfolio_id=portfolio_id,
            user_id=current_user.id,
            symbol=payload.symbol.upper(),
            quantity=payload.quantity,
            avg_price=payload.avg_price,
        )
    except service.PortfolioNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found") from exc
    except service.SecurityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown symbol: {exc}") from exc

    portfolio = await service.get_portfolio(db, portfolio_id=portfolio_id, user_id=current_user.id)
    rows = await service.get_holdings_with_quotes(db, portfolio)
    row = next(r for r in rows if r["holding_id"] == holding.id)
    return {
        "id": row["holding_id"],
        "symbol": row["security"].symbol,
        "name": row["security"].name,
        "sector": row["security"].sector,
        "quantity": row["metrics"].quantity,
        "avg_price": row["metrics"].avg_price,
        "last_price": row["metrics"].last_price,
        "market_value": row["metrics"].market_value,
        "unrealized_pnl": row["metrics"].unrealized_pnl,
        "unrealized_pnl_pct": row["metrics"].unrealized_pnl_pct,
    }


@router.get("/{portfolio_id}/analytics", response_model=PortfolioAnalytics)
async def get_analytics(
    portfolio_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        portfolio = await service.get_portfolio(db, portfolio_id=portfolio_id, user_id=current_user.id)
    except service.PortfolioNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found") from exc

    return await service.compute_portfolio_analytics(db, portfolio)
