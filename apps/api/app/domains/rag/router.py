from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_admin_user, get_current_user
from app.domains.rag import service
from app.domains.rag.embeddings import get_embedding_provider
from app.models.user import User
from app.schemas.rag import RagReindexResultOut, RagSearchResultOut

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/search", response_model=list[RagSearchResultOut])
async def search(
    query: str = Query(..., min_length=1),
    top_k: int = Query(default=3, ge=1, le=10),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await service.retrieve(db, query, top_k=top_k)


@router.post("/reindex", response_model=RagReindexResultOut)
async def trigger_reindex(
    current_user: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Admin-only, same gating rationale as POST /news/ingest — mostly a
    manual catch-up trigger since reindex_missing() already runs after
    every real news ingestion cycle and once at startup."""
    newly_indexed = await service.reindex_missing(db)
    return {"provider": get_embedding_provider().name, "newly_indexed": newly_indexed}
