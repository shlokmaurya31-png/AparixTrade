"""RAG foundation (Tier 1 §20-ish document-intelligence request): real
retrieval over the one genuinely real document corpus this codebase has —
ingested news articles (Session 4). Deliberately not built: a generic
document-upload model, PDF/filing ingestion, or a broader knowledge-graph
corpus — those are separate, real efforts (see docs/ARCHITECTURE.md §9).

Indexing is incremental and idempotent (`reindex_missing`), not a
one-time seed — the recurring "seed only runs once" gotcha this session
already hit three times (news, macro vintage) doesn't apply here by
construction: every call re-scans for articles missing an embedding for
the *currently configured* provider and only embeds those, so it's safe
to call on every startup and after every news ingestion run.
"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.rag.analytics import cosine_similarity
from app.domains.rag.embeddings import get_embedding_provider
from app.models.document_embedding import DocumentEmbedding
from app.models.news import NewsArticle


def _document_text(article: NewsArticle) -> str:
    return f"{article.title}\n{article.summary}"


async def reindex_missing(db: AsyncSession) -> int:
    """Embeds every NewsArticle that doesn't yet have a DocumentEmbedding
    row for the currently configured EmbeddingProvider. Returns the count
    newly indexed."""
    provider = get_embedding_provider()

    already_indexed = await db.execute(
        select(DocumentEmbedding.article_id).where(DocumentEmbedding.model == provider.name)
    )
    indexed_ids = {row[0] for row in already_indexed.all()}

    result = await db.execute(select(NewsArticle))
    articles = list(result.scalars().all())
    to_index = [a for a in articles if a.id not in indexed_ids]

    for article in to_index:
        vector = await provider.embed(_document_text(article))
        db.add(
            DocumentEmbedding(
                article_id=article.id, model=provider.name, dims=provider.dims, vector=json.dumps(vector)
            )
        )

    if to_index:
        await db.commit()
    return len(to_index)


async def retrieve(db: AsyncSession, query: str, top_k: int = 3) -> list[dict]:
    """Real semantic search: embeds `query` with the same provider every
    indexed document used, then ranks by cosine similarity — no keyword
    substring matching (that's search_news_tool's job; this is the
    embedding-based complement to it, better at synonyms/paraphrases with
    the ollama provider, weaker but still real with the hashing default).
    """
    provider = get_embedding_provider()
    query_vector = await provider.embed(query)

    result = await db.execute(
        select(DocumentEmbedding, NewsArticle)
        .join(NewsArticle, NewsArticle.id == DocumentEmbedding.article_id)
        .where(DocumentEmbedding.model == provider.name)
    )
    rows = result.all()

    scored = []
    for embedding_row, article in rows:
        vector = json.loads(embedding_row.vector)
        score = cosine_similarity(query_vector, vector)
        scored.append((score, article))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = scored[:top_k]

    return [
        {
            "title": article.title,
            "summary": article.summary,
            "publisher": article.publisher,
            "url": article.url,
            "published_at": article.published_at.isoformat(),
            "score": round(score, 4),
            "is_mock": article.is_mock,
        }
        for score, article in top
    ]
