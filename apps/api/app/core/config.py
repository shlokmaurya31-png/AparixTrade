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

    # ADMIN_EMAILS is a dynamic bootstrap grant kept alongside the Tier 1
    # `User.role` column (core/roles.py) for backward compatibility — see
    # core/deps.py::require_role().
    admin_emails: str = ""

    # Macro data provider (Tier 1) — mirrors AI_PROVIDER/BROKER_PROVIDER.
    # "mock" is the only implementation that exists; see
    # domains/macro/provider.py.
    macro_provider: str = "mock"

    # Fundamentals data provider (Tier 1 Session 2) — same pattern; see
    # domains/fundamentals/provider.py.
    fundamentals_provider: str = "mock"

    # Corporate actions data provider (Tier 1 Session 3) — same pattern;
    # see domains/corporate_actions/provider.py.
    corporate_actions_provider: str = "mock"

    # Broker integration (Phase 5) — see domains/broker/. Mirrors the
    # AI_PROVIDER pattern: checked-in default is "mock" (zero external
    # deps), "zerodha" activates the real Kite Connect adapter once
    # credentials are supplied below.
    broker_provider: str = "mock"

    # Fernet key (44-char urlsafe-base64, e.g. `Fernet.generate_key()`) used
    # to encrypt broker credentials/tokens at rest — see core/crypto.py. No
    # secure default is possible; a broker connect attempt with this unset
    # fails loudly rather than silently storing secrets in plaintext.
    broker_encryption_key: str | None = None

    # Zerodha Kite Connect app credentials (https://developers.kite.trade) —
    # only meaningful when broker_provider == "zerodha". api_secret is used
    # once per login to compute the Kite token-exchange checksum; it's read
    # from env, never stored in the DB.
    zerodha_api_key: str | None = None
    zerodha_api_secret: str | None = None
    zerodha_redirect_url: str = "http://localhost:3000/broker/callback"

    # Real order placement through a connected broker stays off even once
    # zerodha is wired with real credentials — flipping this on is a
    # separate, deliberate decision, not a side effect of configuring
    # credentials. See docs/ARCHITECTURE.md Phase 5 trade-offs.
    broker_live_trading_enabled: bool = False

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
