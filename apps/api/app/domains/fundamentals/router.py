import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.fundamentals import service
from app.models.user import User
from app.schemas.fundamentals import FinancialStatementOut, RatiosOut

router = APIRouter(prefix="/fundamentals", tags=["fundamentals"])


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


@router.get("/{symbol}", response_model=FinancialStatementOut)
async def get_fundamentals(
    symbol: str,
    as_of: datetime.date | None = Query(default=None),
    period_type: str = Query(default="annual", pattern="^(annual|quarterly)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        security = await service.resolve_security(db, symbol)
    except service.UnknownSymbolError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown symbol: {exc}") from exc

    statement = await service.get_latest_statement_as_of(
        db, security.id, as_of=as_of or _today(), period_type=period_type
    )
    if statement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {period_type} fundamentals available for {security.symbol} as of {as_of or _today()}.",
        )
    return service.statement_to_dict(security, statement)


@router.get("/{symbol}/history", response_model=list[FinancialStatementOut])
async def get_fundamentals_history(
    symbol: str,
    as_of: datetime.date | None = Query(default=None),
    period_type: str = Query(default="annual", pattern="^(annual|quarterly)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    try:
        security = await service.resolve_security(db, symbol)
    except service.UnknownSymbolError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown symbol: {exc}") from exc

    statements = await service.list_statements_as_of(
        db, security.id, as_of=as_of or _today(), period_type=period_type
    )
    return [service.statement_to_dict(security, s) for s in statements]


@router.get("/{symbol}/ratios", response_model=RatiosOut)
async def get_fundamentals_ratios(
    symbol: str,
    as_of: datetime.date | None = Query(default=None),
    period_type: str = Query(default="annual", pattern="^(annual|quarterly)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        security = await service.resolve_security(db, symbol)
    except service.UnknownSymbolError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown symbol: {exc}") from exc

    effective_as_of = as_of or _today()
    statement = await service.get_latest_statement_as_of(
        db, security.id, as_of=effective_as_of, period_type=period_type
    )
    if statement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {period_type} fundamentals available for {security.symbol} as of {effective_as_of}.",
        )
    return await service.compute_ratios(db, security, statement, as_of=effective_as_of)
