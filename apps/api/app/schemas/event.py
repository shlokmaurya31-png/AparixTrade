import datetime
import uuid

from pydantic import BaseModel

from app.schemas.simulation import HoldingShockImpact


class EventOut(BaseModel):
    id: uuid.UUID
    headline: str
    summary: str
    event_type: str
    severity: str
    direction: str
    primary_target: str
    secondary_tags: list[str]
    region: str | None
    published_at: datetime.datetime
    is_mock: bool = True

    model_config = {"from_attributes": True}


class EventImpactOut(BaseModel):
    event_id: uuid.UUID
    headline: str
    severity: str
    direction: str
    target: str
    shock_pct: float
    portfolio_value_before: float
    estimated_impact: float
    estimated_impact_pct: float
    portfolio_value_after: float
    per_holding_impact: list[HoldingShockImpact]
    assumptions: str
    is_mock: bool = True
