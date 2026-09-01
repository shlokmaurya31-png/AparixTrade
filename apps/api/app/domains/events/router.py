import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.events import service
from app.domains.portfolios.service import PortfolioNotFoundError, get_portfolio
from app.models.user import User
from app.schemas.event import EventImpactOut, EventOut

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventOut])
async def list_events(limit: int = 50, db: AsyncSession = Depends(get_db)) -> list:
    return await service.list_events(db, limit=limit)


@router.get("/{event_id}/impact", response_model=EventImpactOut)
async def get_event_impact(
    event_id: uuid.UUID,
    portfolio_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    event = await service.get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    try:
        portfolio = await get_portfolio(db, portfolio_id=portfolio_id, user_id=current_user.id)
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found") from exc

    try:
        return await service.compute_impact_for_portfolio(db, event, portfolio)
    except service.NoHoldingsError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
