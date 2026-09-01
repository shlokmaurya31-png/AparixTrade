import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.portfolio import Portfolio


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A simulated market order against a paper portfolio
    (domains/paper_trading). A rejection (insufficient cash/holding) is a
    normal outcome, persisted like any other order — not an exception, not
    a silently-dropped request."""

    __tablename__ = "orders"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"), index=True, nullable=False)
    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), index=True, nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # "buy" | "sell"
    quantity: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    requested_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    fill_price: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    slippage_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    brokerage_fee: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # "filled" | "rejected"
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="orders")
