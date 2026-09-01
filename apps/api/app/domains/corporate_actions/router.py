import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.corporate_actions import service
from app.models.user import User
from app.schemas.corporate_actions import CorporateActionOut

router = APIRouter(prefix="/corporate-actions", tags=["corporate-actions"])


@router.get("/{symbol}", response_model=list[CorporateActionOut])
async def get_corporate_actions(
    symbol: str,
    as_of: datetime.date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    try:
        security = await service.resolve_security(db, symbol)
    except service.UnknownSymbolError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown symbol: {exc}") from exc

    effective_as_of = as_of or datetime.datetime.now(datetime.timezone.utc).date()
    actions = await service.list_actions_as_of(db, security.id, as_of=effective_as_of)
    return [await service.action_to_dict(db, security, a) for a in actions]
