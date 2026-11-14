"""Checks that need no database: table list, URL handling, behaviour without a database."""

import pytest
from fastapi.testclient import TestClient

from agilesim.config import get_settings
from agilesim.db.base import Base, enum_check
from agilesim.db.enums import SessionStatus
from agilesim.db.session import get_engine, normalize_url
from agilesim.main import app

EXPECTED_TABLES = {
    "scenarios",
    "scenario_stages",
    "scenario_cards",
    "scenario_card_work",
    "scenario_events",
    "facilitators",
    "game_sessions",
    "session_stage_limits",
    "teams",
    "participants",
    "cards",
    "card_work",
    "game_events",
    "survey_responses",
    "ai_drafts",
    "card_movements",
    "dice_rolls",
    "point_spends",
}


def test_metadata_declares_all_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_every_table_has_a_primary_key() -> None:
    for table in Base.metadata.tables.values():
        assert table.primary_key.columns, table.name


def test_no_table_stores_json() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            assert column.type.__class__.__name__ not in {"JSON", "JSONB"}, (
                table.name,
                column.name,
            )


def test_enum_check_lists_the_enum_values() -> None:
    constraint = enum_check("status", SessionStatus)

    assert str(constraint.sqltext) == "status IN ('lobby', 'running', 'paused', 'finished')"
    assert constraint.name == "status_valid"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://u:p@db:5432/x", "postgresql+psycopg://u:p@db:5432/x"),
        ("postgres://u:p@db/x", "postgresql+psycopg://u:p@db/x"),
        ("postgresql+psycopg://u:p@db/x", "postgresql+psycopg://u:p@db/x"),
    ],
)
def test_normalize_url_selects_the_psycopg_driver(url: str, expected: str) -> None:
    assert normalize_url(url) == expected


def test_engine_requires_a_configured_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGILESIM_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        monkeypatch.setattr(get_settings(), "database_url", None)
        with pytest.raises(RuntimeError, match="AGILESIM_DATABASE_URL"):
            get_engine()
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()


def test_readiness_is_503_without_a_database(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        monkeypatch.setattr(get_settings(), "database_url", None)
        response = TestClient(app).get("/health/db")
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()

    assert response.status_code == 503
    assert response.json() == {"database": "unavailable"}
