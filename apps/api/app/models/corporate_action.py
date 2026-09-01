import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CorporateAction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single corporate action against a security (Tier 1 §10) — dividend,
    split, bonus, rights, buyback, merger, demerger, symbol change, ISIN
    change, or delisting (core/corporate_action_types.py::ALL_ACTION_TYPES).

    Point-in-time anchor is `effective_date` (same discipline as
    FinancialStatement — see domains/fundamentals/service.py's module
    docstring): a query "as of" a date must never surface an action before
    it was actually publicly known.

    `ratio`/`amount`/`new_security_id` are each meaningful only for certain
    action types (see core/corporate_action_types.py::RATIO_ACTION_TYPES) —
    nullable rather than one table per type, matching FinancialStatement's
    "one wide row" precedent for this codebase's data volume.
    """

    __tablename__ = "corporate_actions"

    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), index=True, nullable=False)
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Split/bonus/rights: new_shares / old_shares (e.g. a 2-for-1 split is
    # 2.0 — every pre-ex-date share becomes 2). Null for other types.
    ratio: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    # Dividend/buyback: INR per share. Null for other types.
    amount: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    # Merger/demerger/symbol_change: the resulting security, if it's one
    # already in this app's universe. Null otherwise.
    new_security_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("securities.id"), nullable=True)

    announcement_date: Mapped[date] = mapped_column(Date, nullable=False)
    record_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    source: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    is_mock: Mapped[bool] = mapped_column(default=True, nullable=False)

    @property
    def provenance(self):  # -> app.core.provenance.Provenance
        """Not a stored column — same pattern as FinancialStatement.provenance
        (models/fundamentals.py) and MacroIndicator.provenance."""
        from app.core.provenance import statement_provenance

        return statement_provenance(
            provider_name=self.source,
            announcement_date=self.announcement_date,
            effective_date=self.effective_date,
            source="aparix-mock-corporate-actions",
        )
