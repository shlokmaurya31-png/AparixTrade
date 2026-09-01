"""News ingestion pipeline: SOURCE -> FETCH -> NORMALIZE -> DEDUPLICATE ->
CLASSIFY -> EVENT EXTRACTION -> STORE (Tier 1 §18). Entity extraction and
the knowledge-graph step from the full spec pipeline are deliberately not
built this session — see docs/ARCHITECTURE.md §9/§12.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.domains.news.classifier import classify_article
from app.domains.news.provider import NewsProvider, get_news_provider
from app.models.event import Event
from app.models.news import NewsArticle

logger = logging.getLogger(__name__)


def _content_hash(title: str, url: str) -> str:
    return hashlib.sha256(f"{title.strip().lower()}|{url.strip()}".encode("utf-8")).hexdigest()


async def seed_if_needed(db: AsyncSession) -> None:
    """Idempotent, same pattern as every other domain — only for the mock
    provider (a real RSS provider is ingested via ingest_once()/the
    background loop, not a one-time seed)."""
    count = await db.scalar(select(func.count()).select_from(NewsArticle))
    if count and count > 0:
        return
    provider = get_news_provider()
    if provider.name == "mock":
        await ingest_once(db, provider)


async def ingest_once(db: AsyncSession, provider: NewsProvider | None = None) -> dict:
    """One real ingestion run: fetch -> normalize -> dedupe -> classify ->
    store, creating a real Event row for anything the classifier judges
    market-moving. Safe to call repeatedly (e.g. from the background loop
    or a manual admin trigger) — already-seen articles are skipped via
    content_hash, not re-inserted or re-classified."""
    provider = provider or get_news_provider()
    raw_articles = await provider.fetch()
    is_mock = provider.name == "mock"
    discovered_at = datetime.now(timezone.utc)

    new_articles = 0
    events_created = 0
    for raw in raw_articles:
        content_hash = _content_hash(raw["title"], raw["url"])
        existing = await db.execute(select(NewsArticle.id).where(NewsArticle.content_hash == content_hash))
        if existing.scalar_one_or_none() is not None:
            continue  # already ingested — real deduplication, not a re-fetch-and-overwrite

        classification = classify_article(raw["title"], raw["summary"])
        event_id = None
        if classification is not None:
            event = Event(
                headline=raw["title"][:255],
                summary=raw["summary"] or raw["title"],
                event_type=classification.event_type,
                severity=classification.severity,
                direction=classification.direction,
                primary_target=classification.primary_target,
                secondary_tags=[provider.name],
                region="India",
                published_at=raw["published_at"],
                is_mock=is_mock,
            )
            db.add(event)
            await db.flush()
            event_id = event.id
            events_created += 1

        db.add(
            NewsArticle(
                title=raw["title"],
                summary=raw["summary"],
                url=raw["url"],
                publisher=provider.name if is_mock else _publisher_for(provider),
                published_at=raw["published_at"],
                discovered_at=discovered_at,
                language="en",
                region="India",
                source=provider.name if is_mock else _source_for(provider),
                content_hash=content_hash,
                event_id=event_id,
                is_mock=is_mock,
            )
        )
        new_articles += 1

    await db.commit()
    return {
        "provider": provider.name,
        "fetched": len(raw_articles),
        "new_articles": new_articles,
        "events_created": events_created,
    }


def _publisher_for(provider: NewsProvider) -> str:
    return getattr(provider, "publisher", provider.name)


def _source_for(provider: NewsProvider) -> str:
    return getattr(provider, "source", provider.name)


async def list_articles(db: AsyncSession, limit: int = 30) -> list[NewsArticle]:
    result = await db.execute(select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(limit))
    return list(result.scalars().all())


async def search_articles(db: AsyncSession, query: str | None, limit: int = 10) -> list[NewsArticle]:
    stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc())
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(func.lower(NewsArticle.title).like(like) | func.lower(NewsArticle.summary).like(like))
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def run_news_ingestion_loop() -> None:
    """Periodic real ingestion — same asyncio-background-task pattern as
    domains/market_data/websocket.py::run_tick_loop(). app.main's lifespan
    only starts this task when NEWS_PROVIDER=rss; the checked-in "mock"
    default never runs it (mock is seeded once via seed_if_needed(), no
    polling needed or wanted)."""
    from app.core.config import get_settings

    while True:
        interval = get_settings().news_ingestion_interval_seconds
        await asyncio.sleep(interval)
        try:
            async with AsyncSessionLocal() as db:
                result = await ingest_once(db)
            logger.info("news ingestion run: %s", result)
        except Exception:
            # A real external feed can be temporarily unreachable — log and
            # retry next interval rather than crashing the background task
            # (and, with it, silently stopping all future ingestion).
            logger.exception("news ingestion run failed")
