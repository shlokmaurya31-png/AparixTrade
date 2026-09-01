from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.domains.market_data.service import live_market_state
from app.models.ai import AIMessage, AISession, AIToolCall
from app.models.audit import AuditLog
from app.models.event import Event
from app.models.portfolio import Portfolio
from app.models.security import Security
from app.models.user import User


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
            "created_at": u.created_at,
            "experience_level": u.preferences.experience_level,
            "complexity_level": u.preferences.complexity_level,
            "portfolio_count": portfolio_counts.get(u.id, 0),
        }
        for u in users
    ]


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
