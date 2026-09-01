import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.options import service
from app.models.user import User
from app.schemas.options import ExpiryListOut, OptionChainOut, SingleOptionOut

router = APIRouter(prefix="/options", tags=["options"])


@router.get("/expiries", response_model=ExpiryListOut)
async def get_expiries(symbol: str = Query(...), current_user: User = Depends(get_current_user)) -> dict:
    return {"symbol": symbol.upper(), "expiries": service.list_expiries()}


@router.get("/chain", response_model=OptionChainOut)
async def get_chain(
    symbol: str = Query(...),
    expiry: datetime.date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await service.get_chain(db, symbol.upper(), expiry)
    except service.UnknownSymbolError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown symbol: {exc}") from exc


@router.get("/price", response_model=SingleOptionOut)
async def price_option(
    symbol: str = Query(...),
    strike: float = Query(..., gt=0),
    expiry: datetime.date = Query(...),
    option_type: str = Query(..., pattern="^(call|put)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await service.price_single_option(db, symbol.upper(), strike=strike, expiry=expiry, option_type=option_type)
    except service.UnknownSymbolError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown symbol: {exc}") from exc
