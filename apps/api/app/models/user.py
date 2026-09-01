import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import is_admin_email
from app.core.db import Base
from app.core.roles import DEFAULT_ROLE
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # RBAC (Tier 1) — see core/roles.py. Not user-editable via any API this
    # session (§43: build the backend correctly, don't overcomplicate the
    # UI yet); ADMIN_EMAILS keeps working as a dynamic admin grant
    # independent of this column, so existing admin access isn't disturbed.
    role: Mapped[str] = mapped_column(String(20), default=DEFAULT_ROLE, nullable=False)

    preferences: Mapped["UserPreferences"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        """True via a stored `role` of admin/super_admin OR the
        ADMIN_EMAILS allowlist (core/config.py::is_admin_email) — the
        allowlist is a deliberately-preserved bootstrap path, not replaced,
        so existing admin access never silently breaks. See
        docs/ARCHITECTURE.md and docs/APARIX_TIER1_AUDIT.md."""
        from app.core.roles import Role

        return self.role in (Role.ADMIN, Role.SUPER_ADMIN) or is_admin_email(self.email)


class UserPreferences(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Drives the adaptive UI. complexity_level and ai_detail_level are both
    1-5 per the product spec's Complexity Slider / AI Detail settings."""

    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)

    experience_level: Mapped[str] = mapped_column(String(20), default="beginner", nullable=False)
    complexity_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ai_detail_level: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    ai_mode: Mapped[str] = mapped_column(String(20), default="simple", nullable=False)

    user: Mapped["User"] = relationship(back_populates="preferences")
