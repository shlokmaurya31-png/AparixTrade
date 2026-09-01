import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Portfolio(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "portfolios"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), default="long_term", nullable=False)
    # Only meaningful for kind="paper" (domains/paper_trading) — None for
    # every other kind, not a speculative column used elsewhere. See
    # docs/ARCHITECTURE.md Phase 4 trade-offs.
    cash_balance: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)

    holdings: Mapped[list["Holding"]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")


class Holding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Current position in a security within a portfolio. Manually entered in
    Phase 1 — broker-synced holdings arrive with the BrokerAdapter (Phase 5)."""

    __tablename__ = "holdings"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"), index=True, nullable=False)
    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), index=True, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    avg_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="holdings")


class Transaction(Base, UUIDPrimaryKeyMixin):
    """Immutable log backing each Holding's quantity/avg_price. Manually-
    added holdings (Phase 1) leave order_id null; order-driven trades
    (Phase 4, domains/paper_trading) set it."""

    __tablename__ = "transactions"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"), index=True, nullable=False)
    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), index=True, nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # "buy" | "sell"
    quantity: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(nullable=False)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="transactions")
