import uuid

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.db import AsyncSessionLocal
from app.domains.news.service import ingest_once
from app.domains.rag.service import reindex_missing, retrieve
from app.models.document_embedding import DocumentEmbedding
from app.models.news import NewsArticle

# ── Indexing (real, incremental, idempotent) ────────────────────────────


async def test_seeded_mock_articles_are_indexed_by_startup(client: AsyncClient):
    # app.main's lifespan (which the `client` fixture runs) already calls
    # reindex_missing() once after seeding — this proves that actually
    # happened, not just that the function works if called directly.
    async with AsyncSessionLocal() as db:
        article_count = await db.scalar(select(func.count()).select_from(NewsArticle))
        embedding_count = await db.scalar(select(func.count()).select_from(DocumentEmbedding))
    assert article_count > 0
    assert embedding_count == article_count


async def test_reindex_missing_is_idempotent(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        newly_indexed = await reindex_missing(db)
    assert newly_indexed == 0  # everything was already indexed by startup


async def test_reindex_missing_only_embeds_the_new_article(client: AsyncClient):
    unique_url = f"https://example.invalid/{uuid.uuid4().hex}"
    from app.domains.news.provider import NewsProvider
    import datetime

    class _OneArticleProvider(NewsProvider):
        name = "fake-rag-test"

        async def fetch(self) -> list[dict]:
            return [
                {
                    "title": "A genuinely new test headline for indexing",
                    "summary": "Exists only to prove incremental indexing works.",
                    "url": unique_url,
                    "published_at": datetime.datetime.now(datetime.timezone.utc),
                }
            ]

    async with AsyncSessionLocal() as db:
        before = await db.scalar(select(func.count()).select_from(DocumentEmbedding))
        # ingest_once() already calls reindex_missing() internally (see
        # domains/news/service.py) — this proves that wiring, not just the
        # standalone function.
        result = await ingest_once(db, _OneArticleProvider())
        after = await db.scalar(select(func.count()).select_from(DocumentEmbedding))

    assert result["new_articles"] == 1
    assert result["newly_indexed_for_rag"] == 1
    assert after == before + 1


# ── retrieve() — real semantic ranking, not string matching ─────────────


async def test_retrieve_ranks_the_relevant_article_highest(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        results = await retrieve(db, "digital rupee pilot retail partners", top_k=5)
    assert len(results) > 0
    assert "digital rupee" in results[0]["title"].lower()


async def test_retrieve_respects_top_k(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        results = await retrieve(db, "RBI", top_k=1)
    assert len(results) <= 1


async def test_retrieve_scores_are_ordered_descending(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        results = await retrieve(db, "monetary policy and banking regulation", top_k=10)
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


# ── HTTP endpoints ───────────────────────────────────────────────────────


async def test_search_endpoint_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/rag/search", params={"query": "digital rupee"})
    assert response.status_code == 401


async def test_search_endpoint_returns_ranked_results(client: AsyncClient, auth_headers: dict):
    response = await client.get(
        "/api/v1/rag/search", params={"query": "digital rupee pilot"}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) > 0
    assert "score" in body[0] and "title" in body[0]


async def test_reindex_endpoint_requires_admin(client: AsyncClient, auth_headers: dict):
    response = await client.post("/api/v1/rag/reindex", headers=auth_headers)
    assert response.status_code == 403


async def test_reindex_endpoint_works_for_admin(client: AsyncClient, monkeypatch):
    from app.core import config

    admin_email = f"rag-admin-{uuid.uuid4().hex}@example.com"
    monkeypatch.setenv("ADMIN_EMAILS", admin_email)
    config.get_settings.cache_clear()
    try:
        register = await client.post(
            "/api/v1/auth/register",
            json={"email": admin_email, "password": "correct-horse-battery", "full_name": "RAG Admin"},
        )
        headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
        response = await client.post("/api/v1/rag/reindex", headers=headers)
        assert response.status_code == 200
        assert response.json()["provider"] == "hashing"
    finally:
        config.get_settings.cache_clear()


# ── AI Terminal integration (mock provider) ─────────────────────────────


async def test_search_knowledge_base_tool_coerces_a_string_top_k(client: AsyncClient):
    """Regression test for a real bug caught live: Ollama handed back
    top_k as the string "5" instead of an int, crashing a list slice
    (results[:top_k]) inside domains/rag/service.py::retrieve(). The tool
    wrapper now coerces it defensively — see domains/ai/tools.py."""
    from app.domains.ai.tools import search_knowledge_base_tool

    async with AsyncSessionLocal() as db:
        # Any real portfolio works — the tool doesn't use it.
        from sqlalchemy import select as _select

        from app.models.portfolio import Portfolio as _Portfolio

        portfolio = (await db.execute(_select(_Portfolio).limit(1))).scalars().first()
        result = await search_knowledge_base_tool(db, portfolio, query="digital rupee", top_k="5")
    assert "error" not in result
    assert len(result["results"]) <= 5


async def test_ai_chat_knowledge_base_intent(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "RagP", "kind": "trading"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "find documents about digital rupee"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "search_knowledge_base"
