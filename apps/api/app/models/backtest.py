import uuid

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Backtest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A saved buy-and-hold backtest run. Monte Carlo and stress-test results
    are NOT persisted (see docs/ARCHITECTURE.md Phase 2 trade-offs) — a
    backtest is comparatively expensive to (re)compute and a run history is
    genuinely useful, so it gets a table; the others stay stateless."""

    __tablename__ = "backtests"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"), index=True, nullable=False)
    params: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    results: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
