import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class BrokerConnection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A user's link to a broker account (domains/broker). One row per
    user+broker — encrypted_api_secret/encrypted_access_token are Fernet
    ciphertext (core/crypto.py), never plaintext, never serialized in any
    API response. status transitions: disconnected -> connected -> expired
    (Kite access tokens expire daily) -> disconnected (on disconnect, the
    row's credentials are deleted, not just flagged)."""

    __tablename__ = "broker_connections"
    __table_args__ = (Index("ix_broker_connections_user_broker", "user_id", "broker", unique=True),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    broker: Mapped[str] = mapped_column(String(30), nullable=False)  # "mock" | "zerodha"
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "connected" | "expired" | "disconnected"

    # Only set for broker == "zerodha". Encrypted at rest (core/crypto.py) —
    # api_key isn't secret on its own but is kept alongside the secret for
    # simplicity; api_secret and access_token are the sensitive ones.
    encrypted_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    encrypted_api_secret: Mapped[str | None] = mapped_column(String(500), nullable=True)
    encrypted_access_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    broker_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # the broker's own account id
    connected_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
