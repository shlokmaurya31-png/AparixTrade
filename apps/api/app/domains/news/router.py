from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_admin_user, get_current_user
from app.domains.news import service
from app.models.user import User
from app.schemas.news import NewsArticleOut, NewsIngestResultOut

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=list[NewsArticleOut])
async def get_news(
    limit: int = Query(default=30, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    return await service.list_articles(db, limit=limit)


@router.post("/ingest", response_model=NewsIngestResultOut)
async def trigger_ingestion(
    current_user: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Admin-only: manually trigger a real ingestion run — real value when
    NEWS_PROVIDER=rss (a genuine external fetch, gated behind admin access
    rather than every user's browser being able to trigger outbound
    requests to a third-party server); a no-op-shaped refresh against the
    fixed set when NEWS_PROVIDER=mock."""
    return await service.ingest_once(db)
