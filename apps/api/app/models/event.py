from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Event(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A market-moving news event. Seeded mock data — no real news API key
    exists, so this follows the exact same pattern as MockMarketDataProvider
    (see docs/ARCHITECTURE.md Phase 3 trade-offs): clearly labeled, never
    presented as a live feed.

    `primary_target` drives the quantified impact calculation (a sector
    name, a security symbol, or "NIFTY50" for a market-wide event) — reused
    directly by domains/simulation/stress_test.py's apply_shock(), so there
    is exactly one impact-math implementation in the codebase, not two.
    `secondary_tags` is descriptive only (shown in the UI), not used in the
    impact calculation — see the Phase 3 trade-offs table for why a single
    target was chosen over multi-target aggregation.
    """

    __tablename__ = "events"

    headline: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)  # low | medium | high
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # positive | negative | neutral
    primary_target: Mapped[str] = mapped_column(String(50), nullable=False)
    secondary_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
