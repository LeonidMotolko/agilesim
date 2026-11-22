"""API tests run the real application against the rolled-back database session of the tests."""

from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from agilesim.api.deps import DbSession, get_game_service
from agilesim.db.session import get_session
from agilesim.main import create_app
from agilesim.services.game import GameService
from tests.db import conftest as database_fixtures

# Reuse the database fixtures (migrated schema, one rolled-back transaction per test).
database_url = database_fixtures.database_url
engine = database_fixtures.engine
db = database_fixtures.db

PASSWORD = "a-long-test-password"


@pytest.fixture
def dice() -> list[int]:
    """Values the next die rolls will give, in order; a test appends what it needs."""
    return []


@pytest.fixture
def client(db: Session, dice: list[int]) -> Iterator[TestClient]:
    """The application, run with the privileges of ``app_write`` like in production.

    The tests connect as the schema owner, who may do anything; without the role switch a
    statement the application role is not allowed to run (a row lock on an append-only log, a
    write to the scenario catalogue) would only fail in Docker. The test body itself keeps the
    owner's rights, so it can still seed the catalogue.
    """

    def app_session() -> Iterator[Session]:
        db.flush()  # rows the test added are written as the owner, not as the application
        db.execute(sa.text("SET LOCAL ROLE app_write"))
        try:
            yield db
        except DBAPIError:
            db.rollback()  # leave the failed transaction so that the role can be reset
            raise
        finally:
            db.execute(sa.text("RESET ROLE"))

    def game_service(session: DbSession) -> GameService:
        return GameService(session, roll_die=lambda: dice.pop(0))

    app = create_app()
    app.dependency_overrides[get_session] = app_session
    app.dependency_overrides[get_game_service] = game_service
    with TestClient(app) as test_client:
        yield test_client


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_facilitator(client: TestClient, email: str) -> dict[str, str]:
    """Register a facilitator and return the Authorization header."""
    response = client.post(
        "/v1/auth/register",
        json={"email": email, "display_name": "Katsiaryna", "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    return auth_header(response.json()["access_token"])


def create_session(client: TestClient, headers: dict[str, str], name: str = "Group 1") -> dict:
    response = client.post("/v1/sessions", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def create_team(client: TestClient, headers: dict[str, str], session_id: str, name: str) -> dict:
    response = client.post(f"/v1/sessions/{session_id}/teams", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def join(client: TestClient, join_code: str, name: str, team_id: str | None = None) -> dict:
    response = client.post(
        "/v1/join",
        json={"join_code": join_code, "display_name": name, "team_id": team_id, "consent": True},
    )
    assert response.status_code == 201, response.text
    return response.json()
