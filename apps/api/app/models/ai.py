import uuid

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AISession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="simple", nullable=False)

    messages: Mapped[list["AIMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class AIMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_sessions.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_provider: Mapped[str] = mapped_column(String(30), default="mock", nullable=False)

    session: Mapped["AISession"] = relationship(back_populates="messages")
    tool_calls: Mapped[list["AIToolCall"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class AIToolCall(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Records exactly which tool ran and what it returned for a given AI
    message, so every number the AI cites is traceable — no hallucinated
    financial figures, per the product's core safety principle."""

    __tablename__ = "ai_tool_calls"

    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_messages.id"), index=True, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    arguments: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    message: Mapped["AIMessage"] = relationship(back_populates="tool_calls")
