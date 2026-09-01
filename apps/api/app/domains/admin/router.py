from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_admin_user
from app.domains.admin import data_quality, service
from app.schemas.admin import (
    AdminAIUsageOut,
    AdminAuditLogOut,
    AdminSystemHealthOut,
    AdminUserOut,
    DataQualityFindingOut,
)

# Every route here is behind get_current_admin_user — real RBAC as of
# Tier 1 (core/roles.py), with the ADMIN_EMAILS allowlist preserved as a
# backward-compatible alternate grant. All read-only.
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin_user)])


@router.get("/users", response_model=list[AdminUserOut])
async def get_users(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await service.list_users(db)


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
