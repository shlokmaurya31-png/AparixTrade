import datetime
import uuid

from pydantic import BaseModel


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    created_at: datetime.datetime
    experience_level: str
    complexity_level: int
    portfolio_count: int


class AdminAuditLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    result: str
    created_at: datetime.datetime


class ToolUsageCount(BaseModel):
    tool_name: str
    count: int


class AdminAIUsageOut(BaseModel):
    total_sessions: int
    total_messages: int
    tool_usage: list[ToolUsageCount]


class AdminSystemHealthOut(BaseModel):
    users_count: int
    portfolios_count: int
    securities_count: int
    events_count: int
    last_market_tick: datetime.datetime | None
    database_backend: str
