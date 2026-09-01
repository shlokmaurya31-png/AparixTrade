from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app configuration, loaded from environment / .env.

    See ../../.env.example at the repo root for the full annotated list.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./aparix_dev.db"

    jwt_secret_key: str = "change-me-in-production-use-a-long-random-value"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 14

    ai_provider: str = "mock"
    anthropic_api_key: str | None = None

    # Local Ollama — see domains/ai/ollama_provider.py. Only used when
    # ai_provider == "ollama"; the checked-in default stays "mock" so the
    # repo runs with zero external services out of the box.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_request_timeout_seconds: float = 60.0

    cors_origins: str = "http://localhost:3000"

    # No RBAC system exists yet (see docs/ARCHITECTURE.md Phase 3 trade-offs)
    # — this is a placeholder allowlist, not a real roles/permissions model.
    admin_emails: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def admin_email_list(self) -> list[str]:
        return [email.strip().lower() for email in self.admin_emails.split(",") if email.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def is_admin_email(email: str) -> bool:
    """Shared by core/deps.py (route protection) and models/user.py (the
    User.is_admin property FastAPI serializes into UserOut) so there is one
    definition, not two that could drift."""
    return email.lower() in get_settings().admin_email_list
