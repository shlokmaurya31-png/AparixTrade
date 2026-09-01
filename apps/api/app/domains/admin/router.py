import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_admin_user
from app.domains.admin import data_quality, service
from app.models.user import User
from app.schemas.admin import (
    AdminAIUsageOut,
    AdminAuditLogOut,
    AdminSystemHealthOut,
    AdminUserOut,
    DataQualityFindingOut,
    UpdateUserRoleRequest,
    UserRoleOut,
)

# Every route here is behind get_current_admin_user — real RBAC as of
# Tier 1 (core/roles.py), with the ADMIN_EMAILS allowlist preserved as a
# backward-compatible alternate grant. Read-only except the role-update
# endpoint below (Tier 1 Session 7), which has its own extra privilege
# guards beyond just "is an admin" — see domains/admin/service.py.
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin_user)])


@router.get("/users", response_model=list[AdminUserOut])
async def get_users(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await service.list_users(db)


@router.patch("/users/{user_id}/role", response_model=UserRoleOut)
async def update_user_role(
    user_id: uuid.UUID,
    payload: UpdateUserRoleRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await service.update_user_role(db, actor=current_user, target_user_id=user_id, new_role=payload.role)
    except service.SelfRoleChangeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except service.UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.InsufficientPrivilegeError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/audit-logs", response_model=list[AdminAuditLogOut])
async def get_audit_logs(db: AsyncSession = Depends(get_db)) -> list:
    return await service.list_audit_logs(db)


@router.get("/ai-usage", response_model=AdminAIUsageOut)
async def get_ai_usage(db: AsyncSession = Depends(get_db)) -> dict:
    return await service.get_ai_usage(db)


@router.get("/system-health", response_model=AdminSystemHealthOut)
async def get_system_health(db: AsyncSession = Depends(get_db)) -> dict:
    return await service.get_system_health(db)


@router.get("/data-quality", response_model=list[DataQualityFindingOut])
async def get_data_quality(db: AsyncSession = Depends(get_db)) -> list:
    return await data_quality.run_all_checks(db)
