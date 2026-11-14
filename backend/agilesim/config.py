"""Application settings, read from ``AGILESIM_*`` environment variables or a local ``.env``."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGILESIM_", env_file=".env", extra="ignore")

    app_env: str = "development"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    # Runtime connection: a limited login role (member of app_write), never a superuser.
    database_url: str | None = None
    # Schema owner used only by migrations; falls back to ``database_url`` when unset.
    migration_database_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
