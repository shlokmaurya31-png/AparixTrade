import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DocumentEmbedding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A real vector embedding of one news_articles row's title+summary —
    the document corpus this Tier 1 RAG foundation indexes (Session 4's
    news ingestion is the only genuinely real, not fabricated, document
    domain that exists in this codebase — see docs/ARCHITECTURE.md §9/§12
    for why RAG wasn't scoped to a larger, invented corpus).

    `(article_id, model)` is unique, not just `article_id`, so switching
    EMBEDDING_PROVIDER (domains/rag/embeddings.py) doesn't require deleting
    old vectors first — domains/rag/service.py::reindex_missing() re-embeds
    for whichever provider is currently configured and leaves any prior
    provider's rows in place, untouched. `vector` is stored as a JSON-
    encoded float list rather than a dedicated vector column type — no ANN
    index exists at this corpus size (tens of rows), so there is nothing a
    vector-native column type would buy over JSON + a full-scan cosine
    comparison (domains/rag/analytics.py) yet.
    """

    __tablename__ = "document_embeddings"
    __table_args__ = (Index("ix_document_embeddings_article_model", "article_id", "model", unique=True),)

    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news_articles.id"), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)  # EmbeddingProvider.name, e.g. "hashing"/"ollama"
    dims: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded list[float]
