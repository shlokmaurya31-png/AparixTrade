from pydantic import BaseModel


class GraphAffectedSecurityOut(BaseModel):
    symbol: str
    relationship: str


class GraphExposureOut(BaseModel):
    kind: str  # "location" | "commodity"
    name: str
    pass_through_pct: float
    affected: list[GraphAffectedSecurityOut]
