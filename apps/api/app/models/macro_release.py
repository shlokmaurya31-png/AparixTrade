from datetime import date

from sqlalchemy import Boolean, Date, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class MacroIndicatorRelease(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single vintage of a macro indicator reading — Tier 1 §17
    ("indicator, value, unit, frequency, period, release date, source,
    revision, vintage"). `MacroIndicator` (models/macro.py) stays exactly
    as it was — a single current value, unchanged, still used everywhere
    it already was — this is an additive, parallel time-series table, not
    a replacement.

    Point-in-time anchor is `release_date` (§15 discipline, same as
    FinancialStatement/CorporateAction): a query "as of" a date must never
    see a reading before it was actually published. `revision_number`
    makes real revision tracking possible — a statistics office routinely
    republishes an earlier period's figure with a corrected value (e.g.
    GDP growth "advance estimate" -> "provisional estimate" -> "final") —
    without silently overwriting the original vintage, which is exactly
    the kind of look-ahead bias §15 exists to prevent.
    """

    __tablename__ = "macro_indicator_releases"
    __table_args__ = (
        Index("ix_macro_releases_code_period_revision", "code", "period", "revision_number", unique=True),
    )

    code: Mapped[str] = mapped_column(String(30), index=True, nullable=False)  # matches MacroIndicator.code
    period: Mapped[date] = mapped_column(Date, nullable=False)  # the period this reading covers (e.g. quarter-end)
    value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)  # "monthly" | "quarterly"
    revision_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 = first release
    release_date: Mapped[date] = mapped_column(Date, nullable=False)  # the point-in-time anchor
    source: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def provenance(self):  # -> app.core.provenance.Provenance
        from app.core.provenance import statement_provenance

        return statement_provenance(
            provider_name=self.source,
            announcement_date=self.release_date,
            effective_date=self.release_date,
            source="aparix-mock-macro-vintage",
        )
