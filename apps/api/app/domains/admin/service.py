import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.roles import Role
from app.domains.audit.service import log_action
from app.domains.market_data.service import live_market_state
from app.models.ai import AIMessage, AISession, AIToolCall
from app.models.audit import AuditLog
from app.models.event import Event
from app.models.portfolio import Portfolio
from app.models.security import Security
from app.models.user import User


class UserNotFoundError(Exception):
    pass


class SelfRoleChangeError(Exception):
    pass


class InsufficientPrivilegeError(Exception):
    pass


async def list_users(db: AsyncSession, limit: int = 100) -> list[dict]:
    result = await db.execute(
        select(User).options(selectinload(User.preferences)).order_by(User.created_at.desc()).limit(limit)
    )
    users = list(result.scalars().all())

    counts_result = await db.execute(select(Portfolio.user_id, func.count(Portfolio.id)).group_by(Portfolio.user_id))
    portfolio_counts = dict(counts_result.all())

    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "created_at": u.created_at,
            "experience_level": u.preferences.experience_level,
            "complexity_level": u.preferences.complexity_level,
            "portfolio_count": portfolio_counts.get(u.id, 0),
        }
        for u in users
    ]


async def update_user_role(db: AsyncSession, *, actor: User, target_user_id: uuid.UUID, new_role: str) -> dict:
    """Real role changes, with real privilege-escalation guards — the gap
    flagged since Session 1 ("no role-editing UI or audit trail specifically
    for role changes yet... a real gap for whenever a role-management
    endpoint is built"). `UpdateUserRoleRequest`'s field_validator already
    rejects an unknown role string before this is ever called.

    Two guards a naive "any admin can PATCH any user's role" endpoint would
    miss:
    - **Self-role-change is blocked entirely**, not just for super_admin.
      A compromised or careless admin session changing its own role is a
      real risk (accidental self-lockout, or a compromised token
      self-escalating) that a second admin's involvement prevents.
    - **Only a super_admin can grant OR touch the super_admin role** — a
      plain admin promoting someone to super_admin (or demoting an
      existing super_admin) would let a lower-privileged account mint or
      strip the platform's highest privilege, which defeats having tiers
      at all.
    """
    if target_user_id == actor.id:
        raise SelfRoleChangeError("Cannot change your own role — ask another admin.")

    result = await db.execute(select(User).where(User.id == target_user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise UserNotFoundError(f"No user with id {target_user_id}")

    touches_super_admin = new_role == Role.SUPER_ADMIN or target.role == Role.SUPER_ADMIN
    if touches_super_admin and actor.role != Role.SUPER_ADMIN:
        raise InsufficientPrivilegeError("Only a super_admin can grant or change the super_admin role.")

    old_role = target.role
    target.role = new_role
    await log_action(
        db,
        user_id=actor.id,
        action="admin.update_user_role",
        input_data={"target_user_id": str(target_user_id), "old_role": old_role, "new_role": new_role},
    )
    await db.commit()
    await db.refresh(target)
    return {"id": target.id, "email": target.email, "role": target.role}


async def list_audit_logs(db: AsyncSession, limit: int = 100) -> list[AuditLog]:
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    return list(result.scalars().all())


async def get_ai_usage(db: AsyncSession) -> dict:
    total_sessions = await db.scalar(select(func.count()).select_from(AISession)) or 0
    total_messages = await db.scalar(select(func.count()).select_from(AIMessage)) or 0

    tool_counts_result = await db.execute(
        select(AIToolCall.tool_name, func.count(AIToolCall.id))
        .group_by(AIToolCall.tool_name)
        .order_by(func.count(AIToolCall.id).desc())
    )
    tool_usage = [{"tool_name": name, "count": count} for name, count in tool_counts_result.all()]

    return {"total_sessions": total_sessions, "total_messages": total_messages, "tool_usage": tool_usage}


async def get_system_health(db: AsyncSession) -> dict:
    users_count = await db.scalar(select(func.count()).select_from(User)) or 0
    portfolios_count = await db.scalar(select(func.count()).select_from(Portfolio)) or 0
    securities_count = await db.scalar(select(func.count()).select_from(Security)) or 0
    events_count = await db.scalar(select(func.count()).select_from(Event)) or 0

    return {
        "users_count": users_count,
        "portfolios_count": portfolios_count,
        "securities_count": securities_count,
        "events_count": events_count,
        "last_market_tick": live_market_state.last_tick_at(),
        "database_backend": get_settings().database_url.split("://")[0],
    }
