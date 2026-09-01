from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.knowledge_graph import service
from app.models.user import User
from app.schemas.knowledge_graph import GraphExposureOut

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


@router.get("/exposure/{target}", response_model=GraphExposureOut)
async def get_exposure(
    target: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Who's really exposed to a location or commodity, and why — the same
    resolution domains/events/service.py and domains/simulation/service.py
    use internally for event-impact/stress-test propagation, exposed
    directly for inspection (e.g. "who's exposed to Gujarat")."""
    resolved = await service.resolve_graph_exposure(db, target)
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{target!r} doesn't match any known location or commodity in the knowledge graph.",
        )
    return resolved
