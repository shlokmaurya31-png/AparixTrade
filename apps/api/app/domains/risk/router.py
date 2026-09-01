import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.portfolios.service import PortfolioNotFoundError, get_portfolio
from app.domains.risk.service import compute_risk_profile
from app.models.user import User
from app.schemas.risk import RiskProfile

router = APIRouter(prefix="/portfolios", tags=["risk"])


@router.get("/{portfolio_id}/risk", response_model=RiskProfile)
async def get_risk_profile(
    portfolio_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        portfolio = await get_portfolio(db, portfolio_id=portfolio_id, user_id=current_user.id)
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found") from exc

    return await compute_risk_profile(db, portfolio)
