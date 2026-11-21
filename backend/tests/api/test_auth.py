import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import PASSWORD, register_facilitator

pytestmark = pytest.mark.db


def test_register_returns_a_facilitator_token(client: TestClient) -> None:
    response = client.post(
        "/v1/auth/register",
        json={"email": "Anna@Example.com", "display_name": "Anna", "password": PASSWORD},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "facilitator"
    assert response.json()["token_type"] == "bearer"


def test_register_stores_a_hash_and_a_lower_case_email(client: TestClient, db) -> None:
    import sqlalchemy as sa

    from agilesim.db.models import Facilitator

    client.post(
        "/v1/auth/register",
        json={"email": "Mixed@Example.com", "display_name": "M", "password": PASSWORD},
    )

    stored = db.scalars(
        sa.select(Facilitator).where(Facilitator.email == "mixed@example.com")
    ).one()
    assert stored.password_hash.startswith("$argon2id$")
    assert PASSWORD not in stored.password_hash


def test_registering_the_same_email_twice_is_a_conflict(client: TestClient) -> None:
    register_facilitator(client, "dup@example.com")

    response = client.post(
        "/v1/auth/register",
        json={"email": "DUP@example.com", "display_name": "Again", "password": PASSWORD},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "display_name": "A", "password": PASSWORD},
        {"email": "a@example.com", "display_name": "A", "password": "short"},
        {"email": "a@example.com", "display_name": "   ", "password": PASSWORD},
        {"email": "a@example.com", "password": PASSWORD},
    ],
)
def test_register_validates_input(client: TestClient, body: dict) -> None:
    response = client.post("/v1/auth/register", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_login_with_the_right_password(client: TestClient) -> None:
    register_facilitator(client, "login@example.com")

    response = client.post(
        "/v1/auth/login", json={"email": "login@example.com", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_a_wrong_password_or_unknown_email_is_unauthorized(client: TestClient) -> None:
    register_facilitator(client, "who@example.com")

    wrong = client.post(
        "/v1/auth/login", json={"email": "who@example.com", "password": "nope-nope"}
    )
    unknown = client.post("/v1/auth/login", json={"email": "no@example.com", "password": PASSWORD})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
