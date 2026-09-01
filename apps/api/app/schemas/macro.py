from pydantic import BaseModel


class MacroIndicatorOut(BaseModel):
    code: str
    name: str
    value: float
    unit: str
    is_mock: bool = True

    model_config = {"from_attributes": True}
