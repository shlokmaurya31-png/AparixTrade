from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class MacroIndicator(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single macro data point (GDP, CPI, repo rate, ...). Seeded mock
    values, not live-fetched from RBI/MOSPI — see docs/ARCHITECTURE.md Phase
    3 trade-offs. A snapshot, not a time series: Phase 1/2's mock securities
    have full daily history because volatility/beta need it; a macro
    indicator here is only ever read as a single current value (e.g. the
    risk-free rate), so there's nothing to gain from a fake history."""

    __tablename__ = "macro_indicators"

    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
