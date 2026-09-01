import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.domains.news.provider import MockNewsProvider, NewsProvider
from app.domains.news.service import ingest_once, list_articles, search_articles
from app.models.event import Event
from app.models.news import NewsArticle

# ── Ingestion pipeline (fetch -> normalize -> dedupe -> classify -> store) ──


async def test_seed_if_needed_populated_mock_articles(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        articles = await list_articles(db, limit=50)
    assert len(articles) > 0
    assert all(a.is_mock for a in articles)


async def test_ingest_once_is_idempotent_real_deduplication(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        before = len(await list_articles(db, limit=1000))
        result_1 = await ingest_once(db, MockNewsProvider())
        after_first = len(await list_articles(db, limit=1000))
        result_2 = await ingest_once(db, MockNewsProvider())
        after_second = len(await list_articles(db, limit=1000))

    # First call after seeding already happened: everything's a dup already.
    assert result_1["new_articles"] == 0
    assert after_first == before
    assert result_2["new_articles"] == 0
    assert after_second == after_first


class _FakeProvider(NewsProvider):
    name = "fake"
    publisher = "Fake Publisher"
    source = "fake_source"

    def __init__(self, items: list[dict]) -> None:
        self._items = items

    async def fetch(self) -> list[dict]:
        return self._items


async def test_ingest_once_creates_a_real_event_for_a_classifiable_article(client: AsyncClient):
    import datetime

    unique_url = f"https://example.invalid/{uuid.uuid4().hex}"
    provider = _FakeProvider(
        [
            {
                "title": "RBI hikes repo rate by 25 basis points",
                "summary": "The Monetary Policy Committee raised the repo rate.",
                "url": unique_url,
                "published_at": datetime.datetime.now(datetime.timezone.utc),
            }
        ]
    )
    async with AsyncSessionLocal() as db:
        result = await ingest_once(db, provider)
        assert result["new_articles"] == 1
        assert result["events_created"] == 1

        article = (await db.execute(select(NewsArticle).where(NewsArticle.url == unique_url))).scalar_one()
        assert article.event_id is not None
        assert article.source == "fake_source"
        assert article.publisher == "Fake Publisher"
        assert article.is_mock is False  # a non-mock provider name -> real data

        event = await db.get(Event, article.event_id)
        assert event.severity == "high"
        assert event.direction == "negative"
        assert event.primary_target == "NIFTY50"
        assert event.is_mock is False


async def test_ingest_once_does_not_create_an_event_for_a_routine_article(client: AsyncClient):
    import datetime

    unique_url = f"https://example.invalid/{uuid.uuid4().hex}"
    provider = _FakeProvider(
        [
            {
                "title": "RBI to conduct routine VRRR auction",
                "summary": "A scheduled liquidity operation.",
                "url": unique_url,
                "published_at": datetime.datetime.now(datetime.timezone.utc),
            }
        ]
    )
    async with AsyncSessionLocal() as db:
        result = await ingest_once(db, provider)
        assert result["new_articles"] == 1
        assert result["events_created"] == 0

        article = (await db.execute(select(NewsArticle).where(NewsArticle.url == unique_url))).scalar_one()
        assert article.event_id is None


async def test_search_articles_filters_by_query(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        matches = await search_articles(db, "repo rate")
        no_match = await search_articles(db, f"nonexistent-{uuid.uuid4().hex}")
    assert len(matches) >= 1
    assert no_match == []


# ── HTTP endpoints ───────────────────────────────────────────────────────


async def test_get_news_endpoint(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/news", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) > 0
    assert "title" in body[0] and "publisher" in body[0]


async def test_ingest_endpoint_requires_admin(client: AsyncClient, auth_headers: dict):
    response = await client.post("/api/v1/news/ingest", headers=auth_headers)
    assert response.status_code == 403


async def test_ingest_endpoint_works_for_admin(client: AsyncClient, monkeypatch):
    from app.core import config

    admin_email = f"news-admin-{uuid.uuid4().hex}@example.com"
    monkeypatch.setenv("ADMIN_EMAILS", admin_email)
    config.get_settings.cache_clear()
    try:
        register = await client.post(
            "/api/v1/auth/register",
            json={"email": admin_email, "password": "correct-horse-battery", "full_name": "News Admin"},
        )
        headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
        response = await client.post("/api/v1/news/ingest", headers=headers)
        assert response.status_code == 200
        assert response.json()["provider"] == "mock"
    finally:
        config.get_settings.cache_clear()


# ── AI Terminal integration (mock provider) ─────────────────────────────


async def test_ai_chat_search_news_intent(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "NewsP", "kind": "trading"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "search news about repo rate"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "search_news"
