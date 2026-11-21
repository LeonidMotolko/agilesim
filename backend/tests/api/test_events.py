"""Scenario events: proposed on their day, applied by the facilitator, with their effects."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.api.conftest import register_facilitator
from tests.api.test_game import EMERGENCY_NUMBER, Game, new_game

BIG_BACKLOG = 9  # cards 1..9: the five best (5..9) are pulled on day 1, 1..4 wait


def events(client: TestClient, game: Game) -> list[dict]:
    response = client.get(f"/v1/sessions/{game.session_id}/events", headers=game.facilitator)
    assert response.status_code == 200, response.text
    return response.json()


def event_with(client: TestClient, game: Game, effect: str) -> dict:
    return next(e for e in events(client, game) if e["effect"] == effect)


def apply(client: TestClient, game: Game, event: dict):
    url = f"/v1/sessions/{game.session_id}/events/{event['id']}/apply"
    return client.post(url, headers=game.facilitator)


def go_to_day(game: Game, day: int) -> None:
    for _ in range(day - 1):
        assert game.next_day().status_code == 200


@pytest.fixture
def game(client: TestClient, db: Session) -> Game:
    return new_game(client, db, cards=BIG_BACKLOG)


# --------------------------------------------------------------------------- proposing


def test_events_appear_on_their_day(client: TestClient, game: Game):
    assert events(client, game) == []  # no event on day 1
    game.next_day()
    [marketing] = events(client, game)
    assert marketing["day"] == 2
    assert marketing["title"] == "Marketing push"
    assert marketing["effect"] == "pull_cards"
    assert marketing["status"] == "proposed"
    assert marketing["source"] == "template"
    game.next_day()
    assert [e["day"] for e in events(client, game)] == [2, 3]


def test_events_are_not_proposed_twice(client: TestClient, game: Game):
    game.next_day()
    first = events(client, game)
    assert [e["id"] for e in events(client, game)] == [e["id"] for e in first]


def test_players_can_read_events_but_not_apply_them(client: TestClient, game: Game):
    game.next_day()
    [event] = events(client, game)
    as_player = client.get(f"/v1/sessions/{game.session_id}/events", headers=game.player)
    assert as_player.status_code == 200
    url = f"/v1/sessions/{game.session_id}/events/{event['id']}/apply"
    assert client.post(url, headers=game.player).status_code == 403


def test_only_the_session_owner_sees_and_applies_events(client: TestClient, game: Game):
    game.next_day()
    [event] = events(client, game)
    other = register_facilitator(client, "other@x.com")
    assert client.get(f"/v1/sessions/{game.session_id}/events", headers=other).status_code == 403
    url = f"/v1/sessions/{game.session_id}/events/{event['id']}/apply"
    assert client.post(url, headers=other).status_code == 403
    assert client.get(f"/v1/sessions/{game.session_id}/events").status_code == 401


# --------------------------------------------------------------------------- effects


def test_marketing_push_pulls_three_more_cards_regardless_of_the_wip_limit(
    client: TestClient, game: Game
):
    game.next_day()
    applied = apply(client, game, event_with(client, game, "pull_cards"))
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "applied"
    assert applied.json()["applied_at"] is not None
    stages = {c["number"]: c["stage"] for c in game.board()["cards"]}
    # Cards 4, 3 and 2 were the most valuable ones left in the backlog.
    assert [stages[n] for n in (4, 3, 2)] == ["analysis"] * 3
    assert stages[1] == "backlog"
    assert game.card(4)["state"] == "in_progress"


def test_an_applied_event_cannot_be_applied_again(client: TestClient, game: Game):
    game.next_day()
    event = event_with(client, game, "pull_cards")
    assert apply(client, game, event).status_code == 200
    again = apply(client, game, event)
    assert again.status_code == 409
    assert "already applied" in again.json()["error"]["message"]


def test_a_dismissed_event_has_no_effect_and_cannot_be_applied(client: TestClient, game: Game):
    game.next_day()
    event = event_with(client, game, "pull_cards")
    url = f"/v1/sessions/{game.session_id}/events/{event['id']}/dismiss"
    dismissed = client.post(url, headers=game.facilitator)
    assert dismissed.json()["status"] == "dismissed"
    assert game.card(4)["stage"] == "backlog"
    assert apply(client, game, event).status_code == 409


def test_unknown_event_is_not_found(client: TestClient, game: Game):
    response = apply(client, game, {"id": str(uuid.uuid4())})
    assert response.status_code == 404


def test_integration_error_blocks_the_best_card_in_development(
    client: TestClient, game: Game, dice: list[int]
):
    dice.extend([6, 5])
    game.roll("analysis")
    game.spend(9, "analysis", 2)
    assert game.move(9, "development").status_code == 200
    go_to_day(game, 3)
    applied = apply(client, game, event_with(client, game, "block_top_card"))
    assert applied.status_code == 200, applied.text
    assert game.card(9)["is_blocked"] is True
    assert game.card(8)["is_blocked"] is False

    blocked_move = game.move(9, "testing")
    assert blocked_move.status_code == 422
    assert "Card blocked" in blocked_move.json()["error"]["message"]

    game.roll("development")  # day 3, die shows 5
    wrong_stage = game.spend(9, "analysis", 1)  # no analysis die yet today, and not Development
    assert wrong_stage.status_code == 422


def test_three_development_points_remove_the_block_and_do_not_advance_the_card(
    client: TestClient, game: Game, dice: list[int]
):
    dice.extend([6, 6, 5])
    game.roll("analysis")
    game.spend(9, "analysis", 2)
    game.move(9, "development")
    go_to_day(game, 3)
    apply(client, game, event_with(client, game, "block_top_card"))
    game.roll("analysis")  # day 3: 6
    game.roll("development")  # day 3: 5

    other_stage = game.spend(9, "analysis", 2)
    assert other_stage.status_code == 422
    assert "only Development points" in other_stage.json()["error"]["message"]

    first = game.spend(9, "development", 2)
    assert first.status_code == 200, first.text
    assert first.json()["squares_crossed"] == 0
    assert first.json()["card"]["is_blocked"] is True
    assert first.json()["card"]["squares_left"]["development"] == 3

    too_many = game.spend(9, "development", 2)
    assert too_many.status_code == 422
    assert (
        "Only 1 more points are needed to unblock the card" in too_many.json()["error"]["message"]
    )

    last = game.spend(9, "development", 1)
    assert last.status_code == 200
    assert last.json()["card"]["is_blocked"] is False
    assert last.json()["points_left"] == 2
    assert game.card(9)["squares_left"]["development"] == 3

    working = game.spend(9, "development", 2)  # the card is free: points advance it again
    assert working.json()["squares_crossed"] == 2
    assert working.json()["card"]["squares_left"]["development"] == 1


def test_critical_bug_adds_the_emergency_card_outside_the_wip_limit(
    client: TestClient, db: Session
):
    game = new_game(client, db, cards=BIG_BACKLOG, emergency=True)
    go_to_day(game, 7)
    assert game.board()["wip_limits_enabled"] is True
    applied = apply(client, game, event_with(client, game, "emergency_card"))
    assert applied.status_code == 200, applied.text
    card = game.card(EMERGENCY_NUMBER)
    assert card["is_emergency"] is True
    assert card["value"] == 0
    assert card["stage"] == "analysis"
    assert card["state"] == "in_progress"


def test_critical_bug_without_an_emergency_card_in_the_scenario_is_refused(
    client: TestClient, db: Session
):
    game = new_game(client, db, cards=BIG_BACKLOG)
    go_to_day(game, 7)
    response = apply(client, game, event_with(client, game, "emergency_card"))
    assert response.status_code == 422
    assert "no emergency card" in response.json()["error"]["message"]
    assert event_with(client, game, "emergency_card")["status"] == "proposed"


def test_informational_events_are_just_marked_applied(client: TestClient, game: Game):
    go_to_day(game, 4)
    pile_up = next(e for e in events(client, game) if e["title"] == "Testing pile-up")
    assert apply(client, game, pile_up).json()["status"] == "applied"


# --------------------------------------------------------------------------- manual events


def test_facilitator_can_add_and_apply_an_event_of_their_own(client: TestClient, game: Game):
    created = client.post(
        f"/v1/sessions/{game.session_id}/events",
        json={"title": "Fire drill", "description": "Everyone leaves the room for a minute."},
        headers=game.facilitator,
    )
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["source"] == "manual"
    assert event["effect"] is None
    assert event["day"] == 1
    assert apply(client, game, event).json()["status"] == "applied"


def test_manual_event_needs_a_title_and_a_running_game(client: TestClient, game: Game):
    url = f"/v1/sessions/{game.session_id}/events"
    empty = client.post(url, json={"title": "", "description": "x"}, headers=game.facilitator)
    assert empty.status_code == 422
    as_player = client.post(url, json={"title": "a", "description": "b"}, headers=game.player)
    assert as_player.status_code == 403
