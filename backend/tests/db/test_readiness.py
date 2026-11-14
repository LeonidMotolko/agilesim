"""The readiness endpoint against a real database."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from agilesim.config import get_settings
from agilesim.db.session import get_engine
from agilesim.main import app

pytestmark = pytest.mark.db


@pytest.fixture
def configured(
    monkeypatch: pytest.MonkeyPatch, database_url: str, engine: object
) -> Iterator[None]:
    monkeypatch.setenv("AGILESIM_DATABASE_URL", database_url)
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield
    get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.mark.usefixtures("configured")
def test_readiness_is_200_when_the_database_answers() -> None:
    response = TestClient(app).get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"database": "ok"}
