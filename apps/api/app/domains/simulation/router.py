import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.portfolios.service import PortfolioNotFoundError, get_portfolio
from app.domains.simulation import service
from app.models.user import User
from app.schemas.simulation import (
    BacktestRequest,
    BacktestResponse,
    MonteCarloRequest,
    MonteCarloResponse,
    StressTestRequest,
    StressTestResponse,
)

router = APIRouter(prefix="/portfolios", tags=["simulation"])


async def _owned_portfolio(portfolio_id: uuid.UUID, current_user: User, db: AsyncSession):
    try:
        return await get_portfolio(db, portfolio_id=portfolio_id, user_id=current_user.id)
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found") from exc


@router.post("/{portfolio_id}/monte-carlo", response_model=MonteCarloResponse)
async def monte_carlo(
    portfolio_id: uuid.UUID,
    payload: MonteCarloRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    portfolio = await _owned_portfolio(portfolio_id, current_user, db)
    try:
        return await service.run_monte_carlo(
            db, portfolio, method=payload.method, horizon_days=payload.horizon_days, num_paths=payload.num_paths
        )
    except service.InsufficientHistoryError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{portfolio_id}/stress-test", response_model=StressTestResponse)
async def stress_test(
    portfolio_id: uuid.UUID,
    payload: StressTestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    portfolio = await _owned_portfolio(portfolio_id, current_user, db)
    try:
        return await service.run_stress_test(db, portfolio, target=payload.target, shock_pct=payload.shock_pct)
    except service.InsufficientHistoryError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{portfolio_id}/backtest", response_model=BacktestResponse)
async def backtest(
    portfolio_id: uuid.UUID,
    payload: BacktestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    portfolio = await _owned_portfolio(portfolio_id, current_user, db)
    try:
        return await service.run_backtest(
            db, portfolio, initial_value=payload.initial_value, persist=True, user_id=current_user.id
        )
    except service.InsufficientHistoryError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{portfolio_id}/backtests", response_model=list[BacktestResponse])
async def list_backtests(
    portfolio_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    await _owned_portfolio(portfolio_id, current_user, db)
    runs = await service.list_backtests(db, portfolio_id)
    return [{**run.results, "id": run.id, "created_at": run.created_at} for run in runs]
