import datetime
import uuid

from pydantic import BaseModel


class NewsArticleOut(BaseModel):
    id: uuid.UUID
    title: str
    summary: str
    url: str
    publisher: str
    published_at: datetime.datetime
    discovered_at: datetime.datetime
    language: str
    region: str | None
    source: str
    event_id: uuid.UUID | None
    is_mock: bool = True

    model_config = {"from_attributes": True}


class NewsIngestResultOut(BaseModel):
    provider: str
    fetched: int
    new_articles: int
    events_created: int
