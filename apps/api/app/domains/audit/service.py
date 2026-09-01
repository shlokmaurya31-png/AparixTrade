import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_action(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    input_data: dict | None = None,
    output_data: dict | None = None,
    result: str = "success",
) -> None:
    """Called from every auth/portfolio mutation and every AI tool call.
    Commits independently isn't required here — callers commit as part of
    their own transaction; this just adds the row to the session."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            input_data=input_data or {},
            output_data=output_data or {},
            result=result,
        )
    )
