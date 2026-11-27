import uuid

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from agilesim.db.enums import SessionStatus
from agilesim.db.models import GameSession
from tests.api.conftest import (
    auth_header,
    create_session,
    create_team,
    join,
    register_facilitator,
)

pytestmark = pytest.mark.db


def test_create_session_needs_a_token(client: TestClient) -> None:
    response = client.post("/v1/sessions", json={"name": "Group 1"})

    assert response.status_code == 401


def test_a_garbage_token_is_unauthorized(client: TestClient) -> None:
    response = client.get("/v1/sessions", headers=auth_header("garbage"))

    assert response.status_code == 401


def test_facilitator_creates_a_session_with_a_join_code(client: TestClient) -> None:
    headers = register_facilitator(client, "f1@example.com")

    session = create_session(client, headers)

    assert len(session["join_code"]) == 6
    assert session["join_code"].isalnum()
    assert session["status"] == "lobby"
    assert session["current_day"] == 0


def test_a_player_cannot_create_a_session(client: TestClient) -> None:
    headers = register_facilitator(client, "f2@example.com")
    session = create_session(client, headers)
    player = join(client, session["join_code"], "Anna")

    response = client.post(
        "/v1/sessions", json={"name": "Mine"}, headers=auth_header(player["access_token"])
    )

    assert response.status_code == 403


def test_a_facilitator_lists_only_own_sessions(client: TestClient) -> None:
    first = register_facilitator(client, "own1@example.com")
    second = register_facilitator(client, "own2@example.com")
    mine = create_session(client, first, "Mine")
    create_session(client, second, "Not mine")

    response = client.get("/v1/sessions", headers=first)

    assert [s["id"] for s in response.json()] == [mine["id"]]


def test_another_facilitator_cannot_open_the_session(client: TestClient) -> None:
    owner = register_facilitator(client, "owner@example.com")
    other = register_facilitator(client, "other@example.com")
    session = create_session(client, owner)

    assert client.get(f"/v1/sessions/{session['id']}", headers=other).status_code == 403
    assert client.get(f"/v1/sessions/{session['id']}", headers=owner).status_code == 200


def test_unknown_session_is_not_found(client: TestClient) -> None:
    headers = register_facilitator(client, "nf@example.com")

    response = client.get("/v1/sessions/00000000-0000-0000-0000-000000000000", headers=headers)

    assert response.status_code == 404


def test_teams_are_created_and_names_are_unique_per_session(client: TestClient) -> None:
    headers = register_facilitator(client, "teams@example.com")
    session = create_session(client, headers)
    create_team(client, headers, session["id"], "Alpha")

    duplicate = client.post(
        f"/v1/sessions/{session['id']}/teams", json={"name": "Alpha"}, headers=headers
    )
    listing = client.get(f"/v1/sessions/{session['id']}/teams", headers=headers)

    assert duplicate.status_code == 409
    assert [t["name"] for t in listing.json()] == ["Alpha"]


@pytest.mark.parametrize("status", [SessionStatus.RUNNING, SessionStatus.FINISHED])
def test_teams_cannot_be_added_after_the_game_has_started(
    client: TestClient, db, status: SessionStatus
) -> None:
    headers = register_facilitator(client, "late@example.com")
    session = create_session(client, headers)
    game = db.get(GameSession, uuid.UUID(session["id"]))
    game.status = status
    db.flush()

    response = client.post(
        f"/v1/sessions/{session['id']}/teams", json={"name": "Late"}, headers=headers
    )

    assert response.status_code == 409
    assert "before the game starts" in response.json()["error"]["message"]


def test_team_names_differ_by_more_than_letter_case(client: TestClient) -> None:
    headers = register_facilitator(client, "case@example.com")
    session = create_session(client, headers)
    create_team(client, headers, session["id"], "Alpha")

    duplicate = client.post(
        f"/v1/sessions/{session['id']}/teams", json={"name": "alpha"}, headers=headers
    )

    assert duplicate.status_code == 409


def test_only_the_owner_can_add_teams(client: TestClient) -> None:
    owner = register_facilitator(client, "to@example.com")
    other = register_facilitator(client, "tother@example.com")
    session = create_session(client, owner)

    response = client.post(
        f"/v1/sessions/{session['id']}/teams", json={"name": "Alpha"}, headers=other
    )

    assert response.status_code == 403


def test_a_player_joins_with_the_code_and_chooses_a_team(client: TestClient) -> None:
    headers = register_facilitator(client, "j1@example.com")
    session = create_session(client, headers)
    team = create_team(client, headers, session["id"], "Alpha")

    joined = join(client, session["join_code"].lower(), "Anna", team["id"])

    assert joined["participant"]["team_id"] == team["id"]
    assert joined["participant"]["role"] == "player"
    assert joined["rejoin_token"]
    me = client.get(f"/v1/sessions/{session['id']}", headers=auth_header(joined["access_token"]))
    assert me.status_code == 200


def test_the_database_stores_only_a_hash_of_the_rejoin_token(client: TestClient, db) -> None:
    from agilesim.db.models import Participant

    headers = register_facilitator(client, "hash@example.com")
    session = create_session(client, headers)

    joined = join(client, session["join_code"], "Anna")

    stored = db.scalars(sa.select(Participant)).one()
    assert stored.token_hash != joined["rejoin_token"]
    assert len(stored.token_hash) == 64


def test_joining_without_consent_is_refused(client: TestClient) -> None:
    headers = register_facilitator(client, "c@example.com")
    session = create_session(client, headers)

    response = client.post(
        "/v1/join",
        json={"join_code": session["join_code"], "display_name": "Anna", "consent": False},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "rule_violation"


def test_joining_with_an_unknown_code_is_not_found(client: TestClient) -> None:
    response = client.post(
        "/v1/join", json={"join_code": "ZZZZZZ", "display_name": "Anna", "consent": True}
    )

    assert response.status_code == 404


def test_a_malformed_code_is_a_validation_error(client: TestClient) -> None:
    response = client.post(
        "/v1/join", json={"join_code": "abc", "display_name": "Anna", "consent": True}
    )

    assert response.status_code == 422


def test_a_name_can_be_used_once_per_session(client: TestClient) -> None:
    headers = register_facilitator(client, "n@example.com")
    session = create_session(client, headers)
    join(client, session["join_code"], "Anna")

    response = client.post(
        "/v1/join",
        json={"join_code": session["join_code"], "display_name": "Anna", "consent": True},
    )

    assert response.status_code == 409


def test_player_names_differ_by_more_than_letter_case(client: TestClient) -> None:
    headers = register_facilitator(client, "pcase@example.com")
    session = create_session(client, headers)
    join(client, session["join_code"], "Anna")

    response = client.post(
        "/v1/join",
        json={"join_code": session["join_code"], "display_name": "ANNA", "consent": True},
    )

    assert response.status_code == 409


def test_a_team_of_another_session_cannot_be_chosen(client: TestClient) -> None:
    headers = register_facilitator(client, "x@example.com")
    first = create_session(client, headers, "First")
    second = create_session(client, headers, "Second")
    foreign_team = create_team(client, headers, second["id"], "Alpha")

    response = client.post(
        "/v1/join",
        json={
            "join_code": first["join_code"],
            "display_name": "Anna",
            "team_id": foreign_team["id"],
            "consent": True,
        },
    )

    assert response.status_code == 404


def test_nobody_joins_a_finished_session(client: TestClient, db) -> None:
    headers = register_facilitator(client, "fin@example.com")
    session = create_session(client, headers)
    game = db.get(GameSession, uuid.UUID(session["id"]))
    game.status = SessionStatus.FINISHED
    db.flush()

    response = client.post(
        "/v1/join",
        json={"join_code": session["join_code"], "display_name": "Anna", "consent": True},
    )

    assert response.status_code == 409


def test_rejoin_returns_a_new_access_token(client: TestClient) -> None:
    headers = register_facilitator(client, "r@example.com")
    session = create_session(client, headers)
    joined = join(client, session["join_code"], "Anna")

    response = client.post("/v1/rejoin", json={"rejoin_token": joined["rejoin_token"]})

    assert response.status_code == 200
    assert response.json()["participant"]["id"] == joined["participant"]["id"]
    assert client.post("/v1/rejoin", json={"rejoin_token": "x" * 40}).status_code == 404


def test_a_player_of_another_session_is_forbidden(client: TestClient) -> None:
    headers = register_facilitator(client, "iso@example.com")
    first = create_session(client, headers, "First")
    second = create_session(client, headers, "Second")
    player = join(client, first["join_code"], "Anna")

    response = client.get(
        f"/v1/sessions/{second['id']}", headers=auth_header(player["access_token"])
    )

    assert response.status_code == 403


def test_teams_can_be_listed_with_only_the_join_code(client: TestClient) -> None:
    headers = register_facilitator(client, "pub@example.com")
    session = create_session(client, headers)
    create_team(client, headers, session["id"], "Alpha")
    create_team(client, headers, session["id"], "Beta")

    response = client.get(f"/v1/join/{session['join_code']}/teams")

    assert sorted(t["name"] for t in response.json()) == ["Alpha", "Beta"]
    assert client.get("/v1/join/NOSUCH/teams").status_code == 404
