import datetime
import uuid

from pydantic import BaseModel, field_validator

from app.core.roles import ALL_ROLES


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    created_at: datetime.datetime
    experience_level: str
    complexity_level: int
    portfolio_count: int


class UpdateUserRoleRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def role_must_be_known(cls, value: str) -> str:
        if value not in ALL_ROLES:
            raise ValueError(f"Unknown role {value!r}. Known roles: {', '.join(ALL_ROLES)}")
        return value


class UserRoleOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str


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


class DataQualityFindingOut(BaseModel):
    check: str
    status: str  # "GOOD" | "WARNING" | "STALE" | "INVALID" | "UNKNOWN"
    detail: str
