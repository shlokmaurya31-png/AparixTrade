"""MacroDataProvider abstraction (Tier 1) — the macro domain is the first
data domain (outside market data and AI) migrated to the
interface-+ Mock-implementation pattern proven by
domains/market_data/provider.py, domains/ai/provider.py, and
domains/broker/adapter.py. See docs/APARIX_TIER1_AUDIT.md §5-6.

Only a Mock implementation exists this session, wrapping the existing
seeded `macro_indicators` table exactly as before — this is a refactor
(same data, same behavior), not a new data source. The point is proving
the seam works so a real RBI/MOSPI-backed provider is a new class later,
not a rewrite of everything that calls this.
"""

from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.macro import MacroIndicator


class MacroDataProvider(ABC):
    name: str

    @abstractmethod
    async def get_indicator(self, db: AsyncSession, code: str) -> MacroIndicator | None:
        raise NotImplementedError

    @abstractmethod
    async def get_latest(self, db: AsyncSession) -> list[MacroIndicator]:
        raise NotImplementedError

    async def get_series(self, db: AsyncSession, code: str) -> list[MacroIndicator]:
        """A real provider would return a time series (see
        docs/APARIX_TIER1_AUDIT.md — macro vintage/revision tracking is
        explicitly deferred). The mock domain only ever has one row per
        indicator, so this returns that single point, not a fabricated
        history."""
        indicator = await self.get_indicator(db, code)
        return [indicator] if indicator else []


class MockMacroDataProvider(MacroDataProvider):
    name = "mock"

    async def get_indicator(self, db: AsyncSession, code: str) -> MacroIndicator | None:
        result = await db.execute(select(MacroIndicator).where(MacroIndicator.code == code))
        return result.scalar_one_or_none()

    async def get_latest(self, db: AsyncSession) -> list[MacroIndicator]:
        result = await db.execute(select(MacroIndicator).order_by(MacroIndicator.code))
        return list(result.scalars().all())


def get_macro_provider() -> MacroDataProvider:
    # Mirrors get_model_provider() (domains/ai/provider.py) and
    # get_broker_adapter() (domains/broker/service.py): env-driven
    # selection via MACRO_PROVIDER. "mock" is the only value that exists
    # yet — same position AI_PROVIDER/BROKER_PROVIDER were in before
    # Ollama/Zerodha were added — but the config knob and the branch point
    # exist now, not retrofitted later.
    from app.core.config import get_settings

    settings = get_settings()
    if settings.macro_provider == "mock":
        return MockMacroDataProvider()
    raise ValueError(f"Unknown MACRO_PROVIDER: {settings.macro_provider!r}")
