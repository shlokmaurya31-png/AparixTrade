from pydantic import BaseModel, Field


class UpdatePreferencesRequest(BaseModel):
    experience_level: str | None = Field(default=None, pattern="^(beginner|retail|active_trader|hni|professional)$")
    complexity_level: int | None = Field(default=None, ge=1, le=5)
    ai_detail_level: int | None = Field(default=None, ge=1, le=5)
    ai_mode: str | None = Field(
        default=None,
        pattern="^(simple|analyst|quant|trader|risk_officer|portfolio_manager|macro_economist|options_specialist|researcher)$",
    )
