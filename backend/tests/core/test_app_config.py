import pytest

from agilesim.config import DEFAULT_JWT_SECRET, get_settings
from agilesim.main import create_app


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_secret_is_refused_outside_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGILESIM_APP_ENV", "production")
    monkeypatch.delenv("AGILESIM_JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="AGILESIM_JWT_SECRET"):
        create_app()


def test_custom_secret_is_accepted_outside_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGILESIM_APP_ENV", "production")
    monkeypatch.setenv("AGILESIM_JWT_SECRET", DEFAULT_JWT_SECRET + "-changed")

    assert create_app().title == "AgileSim API"
