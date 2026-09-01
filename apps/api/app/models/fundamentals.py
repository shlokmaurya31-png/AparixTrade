import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class FinancialStatement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One reported period's income statement + balance sheet + cash flow,
    combined (these are always reported together in practice) rather than
    three separate tables — see docs/ARCHITECTURE.md §12 trade-offs.

    `announcement_date`/`effective_date` are the point-in-time anchor
    (Tier 1 §15): a query "as of" a date must never return a statement
    whose `effective_date` is after that date, even if its `period_end`
    already passed — see domains/fundamentals/service.py and
    tests/test_point_in_time_integrity.py. Kept as two distinct columns
    (not collapsed into one) because a real provider could someday report
    a delay between "publicly announced" and "usable" (e.g. a provisional
    announcement later finalized) — this session sets them equal, but the
    schema doesn't assume they always will be.
    """

    __tablename__ = "financial_statements"
    __table_args__ = (
        Index(
            "ix_financial_statements_security_period",
            "security_id",
            "period_end",
            "period_type",
            unique=True,
        ),
    )

    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), index=True, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "annual" | "quarterly"
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    announcement_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_restated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="crore", nullable=False)
    shares_outstanding: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Income statement
    revenue: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    gross_profit: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    ebitda: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    ebit: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    pbt: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    pat: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    eps: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)

    # Balance sheet
    total_assets: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    total_liabilities: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    total_equity: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    cash_and_equivalents: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    total_debt: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    current_assets: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    current_liabilities: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    interest_expense: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)

    # Cash flow
    cfo: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    cfi: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    cff: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    free_cash_flow: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)

    @property
    def provenance(self):  # -> app.core.provenance.Provenance
        """Not a stored column — same pattern as MacroIndicator.provenance
        (models/macro.py). Uses announcement_date/effective_date, the
        point-in-time anchor, not created_at/updated_at."""
        from app.core.provenance import statement_provenance

        return statement_provenance(
            provider_name="mock", announcement_date=self.announcement_date, effective_date=self.effective_date
        )
