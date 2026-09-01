from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.provenance import quote_provenance
from app.domains.market_data import service
from app.schemas.market_data import CandleOut, QuoteOut, SecurityOut

router = APIRouter(prefix="/market", tags=["market"])


def _with_provenance(quote: dict) -> dict:
    return {**quote, "provenance": quote_provenance(provider_name=service.provider.__class__.__name__, as_of=quote["as_of"])}


@router.get("/securities", response_model=list[SecurityOut])
async def get_securities(db: AsyncSession = Depends(get_db)) -> list:
    return await service.list_securities(db)


@router.get("/quotes/{symbol}", response_model=QuoteOut)
async def get_quote(symbol: str) -> dict:
    quote = service.live_market_state.get_quote(symbol.upper())
    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
    return _with_provenance(quote)


@router.get("/quotes", response_model=list[QuoteOut])
async def get_all_quotes() -> list[dict]:
    return [_with_provenance(q) for q in service.live_market_state.all_quotes()]


@router.get("/candles/{symbol}", response_model=list[CandleOut])
async def get_candles(symbol: str, limit: int = 180, db: AsyncSession = Depends(get_db)) -> list:
    security = await service.get_security_by_symbol(db, symbol)
    if security is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
    return await service.get_candles(db, security.id, limit=limit)
