import datetime
import uuid

from pydantic import BaseModel

from app.core.provenance import Provenance


class CorporateActionOut(BaseModel):
    id: uuid.UUID
    symbol: str
    action_type: str
    ratio: float | None
    amount: float | None
    new_security_symbol: str | None
    announcement_date: datetime.date
    record_date: datetime.date | None
    ex_date: datetime.date
    effective_date: datetime.date
    source: str
    is_mock: bool = True
    provenance: Provenance
