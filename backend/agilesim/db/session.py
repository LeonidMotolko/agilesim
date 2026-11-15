"""Engine and session helpers (SQLAlchemy 2.0, psycopg 3)."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from agilesim.config import get_settings


def normalize_url(url: str) -> str:
    """Accept ``postgresql://`` and ``postgres://`` URLs and select the psycopg 3 driver."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


def make_engine(url: str) -> Engine:
    return create_engine(normalize_url(url), pool_pre_ping=True)


@lru_cache
def get_engine() -> Engine:
    """Engine of the application role (``AGILESIM_DATABASE_URL``), created on first use."""
    url = get_settings().database_url
    if not url:
        msg = "AGILESIM_DATABASE_URL is not set"
        raise RuntimeError(msg)
    return make_engine(url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed afterwards."""
    with get_session_factory()() as session:
        yield session
