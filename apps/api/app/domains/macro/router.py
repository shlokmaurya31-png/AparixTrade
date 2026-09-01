import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.domains.macro import service
from app.schemas.macro import MacroIndicatorOut, MacroIndicatorReleaseOut

router = APIRouter(prefix="/macro", tags=["macro"])


@router.get("/indicators", response_model=list[MacroIndicatorOut])
async def get_indicators(db: AsyncSession = Depends(get_db)) -> list:
    return await service.list_indicators(db)


@router.get("/indicators/{code}/history", response_model=list[MacroIndicatorReleaseOut])
async def get_indicator_history(
    code: str,
    as_of: datetime.date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    effective_as_of = as_of or datetime.datetime.now(datetime.timezone.utc).date()
    releases = await service.get_releases_as_of(db, code, as_of=effective_as_of)
    if not releases:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No vintage history for {code!r} as of {effective_as_of} "
            "(only cpi_inflation/gdp_growth have real revision history — see docs/ARCHITECTURE.md §9).",
        )
    return releases
