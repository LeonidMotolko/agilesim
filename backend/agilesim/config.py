"""Application settings, read from ``AGILESIM_*`` environment variables or a local ``.env``."""

from datetime import timedelta
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_DEVELOPMENT = "development"
DEFAULT_JWT_SECRET = "development-only-secret-change-me-0123456789"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGILESIM_", env_file=".env", extra="ignore")

    app_env: str = ENV_DEVELOPMENT
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    # Runtime connection: a limited login role (member of app_write), never a superuser.
    database_url: str | None = None
    # Schema owner used only by migrations; falls back to ``database_url`` when unset.
    migration_database_url: str | None = None
    # Signing key of access tokens. The default is for local development only: set a long random
    # value in every shared environment (the application refuses the default outside development).
    jwt_secret: str = DEFAULT_JWT_SECRET
    access_token_minutes: int = 480
    log_level: str = "INFO"

    @property
    def access_token_ttl(self) -> timedelta:
        return timedelta(minutes=self.access_token_minutes)


@lru_cache
def get_settings() -> Settings:
    return Settings()
