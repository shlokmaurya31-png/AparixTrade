import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class NewsArticle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single ingested news/press-release item (Tier 1 §18-19). Real
    content when `source != "mock"` (see domains/news/provider.py) — fetched
    from an actual RSS feed, not fabricated. `event_id` is set only when
    domains/news/classifier.py judged the article market-moving enough to
    become a real Event row; most ingested articles (routine operational
    announcements) are stored but never become events — see
    docs/ARCHITECTURE.md §9.
    """

    __tablename__ = "news_articles"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    publisher: Mapped[str] = mapped_column(String(100), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # "mock" | "rbi_press_releases" | ...
    # sha256(title + url) — the actual dedup key (domains/news/service.py).
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
