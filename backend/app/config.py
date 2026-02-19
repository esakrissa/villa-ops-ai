"""Application configuration using pydantic-settings."""

import warnings

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_JWT_DEFAULT = "change-me-in-production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "VillaOps AI"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"  # development, staging, production

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database (PostgreSQL)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/villaops"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT Auth
    jwt_secret_key: str = _INSECURE_JWT_DEFAULT
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/v1/auth/github/callback"

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""
    stripe_business_price_id: str = ""

    # LLM (LiteLLM)
    default_llm_model: str = "gemini/gemini-3-flash-preview"
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    litellm_cache_enabled: bool = True

    # MCP Server
    mcp_server_url: str = "http://localhost:8001/mcp"

    # Exa (Web Search via hosted MCP)
    exa_api_key: str = ""

    # Frontend
    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    @model_validator(mode="after")
    def _ensure_frontend_in_cors(self) -> "Settings":
        """Ensure the configured frontend_url is always in cors_origins."""
        if self.frontend_url and self.frontend_url not in self.cors_origins:
            self.cors_origins.append(self.frontend_url)
        return self

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        """Reject insecure JWT secret in production and warn in development."""
        if self.jwt_secret_key == _INSECURE_JWT_DEFAULT:
            if self.environment == "production":
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a strong random value in production. "
                    'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
                )
            warnings.warn(
                "Using default JWT secret — this is insecure and only acceptable for local development. "
                "Set JWT_SECRET_KEY in your .env file.",
                UserWarning,
                stacklevel=1,
            )
        return self

    @property
    def async_database_url(self) -> str:
        """Ensure the database URL uses the asyncpg driver."""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def psycopg_database_url(self) -> str:
        """Return a postgresql:// URL for psycopg (used by langgraph checkpointer)."""
        url = self.database_url
        if "+asyncpg" in url:
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url


settings = Settings()
