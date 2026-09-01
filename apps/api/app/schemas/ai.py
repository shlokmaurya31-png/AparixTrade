import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    portfolio_id: uuid.UUID
    session_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=2000)


class ToolCallOut(BaseModel):
    tool_name: str
    arguments: dict
    result: dict


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    message: str
    mode: str
    provider: str
    tool_calls: list[ToolCallOut]


class AiConfigOut(BaseModel):
    provider: str
    model: str | None = None
    # Modes a real style-differentiated response is possible for right now —
    # depends on which provider is active, not just whether the mode exists
    # (see docs/ARCHITECTURE.md Phase 3.5). The frontend uses this instead
    # of hardcoding an "implemented" list that could silently go stale.
    supported_modes: list[str]
