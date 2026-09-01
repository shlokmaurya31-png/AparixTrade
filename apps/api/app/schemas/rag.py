import datetime

from pydantic import BaseModel


class RagSearchResultOut(BaseModel):
    title: str
    summary: str
    publisher: str
    url: str
    published_at: datetime.datetime
    score: float
    is_mock: bool


class RagReindexResultOut(BaseModel):
    provider: str
    newly_indexed: int
