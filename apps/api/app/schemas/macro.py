import datetime

from pydantic import BaseModel

from app.core.provenance import Provenance


class MacroIndicatorOut(BaseModel):
    code: str
    name: str
    value: float
    unit: str
    is_mock: bool = True
    provenance: Provenance

    model_config = {"from_attributes": True}


class MacroIndicatorReleaseOut(BaseModel):
    code: str
    period: datetime.date
    value: float
    unit: str
    frequency: str
    revision_number: int
    release_date: datetime.date
    source: str
    is_mock: bool = True
    provenance: Provenance

    model_config = {"from_attributes": True}
