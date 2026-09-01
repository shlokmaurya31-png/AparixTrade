from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.audit.service import log_action
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.user import UpdatePreferencesRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me/preferences", response_model=UserOut)
async def update_preferences(
    payload: UpdatePreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(current_user.preferences, field, value)

    await log_action(db, user_id=current_user.id, action="user.update_preferences", input_data=updates)
    await db.commit()
    await db.refresh(current_user, attribute_names=["preferences"])
    return current_user
