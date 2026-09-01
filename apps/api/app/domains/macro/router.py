from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.domains.macro import service
from app.schemas.macro import MacroIndicatorOut

router = APIRouter(prefix="/macro", tags=["macro"])


@router.get("/indicators", response_model=list[MacroIndicatorOut])
async def get_indicators(db: AsyncSession = Depends(get_db)) -> list:
    return await service.list_indicators(db)
