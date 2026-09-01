from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.macro.seed_data import SEED_INDICATORS
from app.models.macro import MacroIndicator


async def seed_if_needed(db: AsyncSession) -> None:
    """Idempotent, same pattern as market_data.service.seed_if_needed."""
    count = await db.scalar(select(func.count()).select_from(MacroIndicator))
    if count and count > 0:
        return

    for code, name, value, unit in SEED_INDICATORS:
        db.add(MacroIndicator(code=code, name=name, value=value, unit=unit, is_mock=True))
    await db.commit()


async def list_indicators(db: AsyncSession) -> list[MacroIndicator]:
    result = await db.execute(select(MacroIndicator).order_by(MacroIndicator.code))
    return list(result.scalars().all())


async def get_indicator(db: AsyncSession, code: str) -> MacroIndicator | None:
    result = await db.execute(select(MacroIndicator).where(MacroIndicator.code == code))
    return result.scalar_one_or_none()
