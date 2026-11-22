"""The game endpoints: start, day control, dice, points, moves, WIP limits and results."""

import uuid
from dataclasses import dataclass
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agilesim.db.models import ScenarioCard, ScenarioCardWork
from tests.api.conftest import (
    auth_header,
    create_session,
    create_team,
    join,
    register_facilitator,
)
from tests.db import factories

pytestmark = pytest.mark.db

# Work squares of every test card: Analysis 2, Development 3, Testing 2.
SQUARES = {"analysis": 2, "development": 3, "testing": 2}
CARD_COUNT = 6  # numbers 1..6, worth 10..60: the five best are 2..6, card 1 stays in the backlog


@dataclass
class Game:
    client: TestClient
    facilitator: dict[str, str]
    session_id: str
    team_id: str
    player: dict[str, str]

    def post(self, path: str, body: dict | None = None, headers: dict[str, str] | None = None):
        return self.client.post(path, json=body or {}, headers=headers or self.player)

    def board(self) -> dict:
        response = self.client.get(f"/v1/teams/{self.team_id}/board", headers=self.player)
        assert response.status_code == 200, response.text
        return response.json()

    def card(self, number: int) -> dict:
        return next(c for c in self.board()["cards"] if c["number"] == number)

    def roll(self, stage: str):
        return self.post(f"/v1/teams/{self.team_id}/dice", {"stage": stage})

    def spend(self, number: int, source: str, points: int, request_id: str | None = None):
        body = {
            "card_id": self.card(number)["id"],
            "source_stage": source,
            "points": points,
            "request_id": request_id or str(uuid.uuid4()),
        }
        return self.post(f"/v1/teams/{self.team_id}/spend", body)

    def move(self, number: int, to_stage: str, request_id: str | None = None):
        body = {"to_stage": to_stage, "request_id": request_id or str(uuid.uuid4())}
        return self.post(f"/v1/teams/{self.team_id}/cards/{self.card(number)['id']}/move", body)

    def next_day(self):
        return self.client.post(
            f"/v1/sessions/{self.session_id}/next-day", headers=self.facilitator
        )


EMERGENCY_NUMBER = 99


def seed_cards(db: Session, count: int = CARD_COUNT, *, emergency: bool = False) -> None:
    scenario = factories.startup_flow(db)
    stage_ids = {code: stage.id for code, stage in factories.stages(db, scenario).items()}
    numbers = [*range(1, count + 1), *([EMERGENCY_NUMBER] if emergency else [])]
    for number in numbers:
        is_emergency = number == EMERGENCY_NUMBER
        card = ScenarioCard(
            scenario_id=scenario.id,
            number=number,
            title="Critical bug" if is_emergency else f"Card {number}",
            value=Decimal(0 if is_emergency else number * 10),
            is_emergency=is_emergency,
        )
        db.add(card)
        db.flush()
        for code, squares in SQUARES.items():
            db.add(
                ScenarioCardWork(
                    scenario_card_id=card.id,
                    stage_id=stage_ids[code],
                    scenario_id=scenario.id,
                    squares=squares,
                )
            )
    db.flush()


def new_game(
    client: TestClient,
    db: Session,
    *,
    start: bool = True,
    email: str = "f@x.com",
    cards: int = CARD_COUNT,
    emergency: bool = False,
) -> Game:
    seed_cards(db, cards, emergency=emergency)
    facilitator = register_facilitator(client, email)
    session = create_session(client, facilitator)
    team = create_team(client, facilitator, session["id"], "Alpha")
    joined = join(client, session["join_code"], "Anna", team["id"])
    game = Game(client, facilitator, session["id"], team["id"], auth_header(joined["access_token"]))
    if start:
        response = client.post(f"/v1/sessions/{session['id']}/start", headers=facilitator)
        assert response.status_code == 200, response.text
    return game


@pytest.fixture
def game(client: TestClient, db: Session) -> Game:
    return new_game(client, db)


# --------------------------------------------------------------------------- start and days


def test_start_deals_the_cards_and_pulls_the_five_most_valuable(game: Game):
    board = game.board()
    assert board["day"] == 1
    assert board["wip_limits_enabled"] is False
    assert len(board["cards"]) == CARD_COUNT
    stages = {c["number"]: c["stage"] for c in board["cards"]}
    assert stages == {
        1: "backlog",
        2: "analysis",
        3: "analysis",
        4: "analysis",
        5: "analysis",
        6: "analysis",
    }
    pulled = game.card(6)
    assert pulled["state"] == "in_progress"
    assert pulled["squares_left"] == SQUARES


def test_start_needs_a_lobby_session_with_a_team_and_enough_cards(client: TestClient, db: Session):
    facilitator = register_facilitator(client, "f@x.com")
    session = create_session(client, facilitator)
    url = f"/v1/sessions/{session['id']}/start"

    no_team = client.post(url, headers=facilitator)
    assert no_team.status_code == 422
    assert "at least one team" in no_team.json()["error"]["message"]

    create_team(client, facilitator, session["id"], "Alpha")
    no_cards = client.post(url, headers=facilitator)
    assert no_cards.status_code == 422
    assert "backlog cards" in no_cards.json()["error"]["message"]

    seed_cards(db)
    assert client.post(url, headers=facilitator).status_code == 200
    again = client.post(url, headers=facilitator)
    assert again.status_code == 409


def test_only_the_owner_facilitator_controls_the_days(client: TestClient, game: Game):
    other = register_facilitator(client, "other@x.com")
    response = client.post(f"/v1/sessions/{game.session_id}/next-day", headers=other)
    assert response.status_code == 403
    assert game.next_day().json()["current_day"] == 2


def test_players_cannot_start_or_close_days(client: TestClient, game: Game):
    response = client.post(f"/v1/sessions/{game.session_id}/next-day", headers=game.player)
    assert response.status_code == 403


def test_wip_limits_switch_on_after_day_four_and_game_ends_after_day_eight(game: Game):
    for expected_day in (2, 3, 4):
        assert game.next_day().json()["wip_limits_enabled"] is False
        assert game.board()["day"] == expected_day
    assert game.next_day().json()["wip_limits_enabled"] is True  # day 5
    for _ in range(3):
        game.next_day()
    last = game.next_day()  # closes day 8
    assert last.json()["status"] == "finished"
    assert last.json()["finished_at"] is not None
    assert game.next_day().status_code == 409
    assert game.roll("analysis").status_code == 409


# --------------------------------------------------------------------------- dice


def test_a_die_is_rolled_once_per_stage_and_day(game: Game, dice: list[int]):
    dice.extend([4, 5])
    first = game.roll("analysis")
    assert first.status_code == 200
    assert first.json() == {"stage": "analysis", "day": 1, "value": 4, "points_left": 4}
    assert game.roll("analysis").status_code == 409
    assert game.roll("development").json()["value"] == 5
    game.next_day()
    dice.append(2)
    assert game.roll("analysis").json()["day"] == 2


def test_dice_show_up_on_the_board_with_points_left(game: Game, dice: list[int]):
    dice.append(6)
    game.roll("analysis")
    game.spend(6, "analysis", 2)
    assert game.board()["dice"] == [{"stage": "analysis", "day": 1, "value": 6, "points_left": 4}]


def test_only_a_player_of_the_team_can_roll(client: TestClient, db: Session, game: Game):
    other_team = create_team(client, game.facilitator, game.session_id, "Beta")
    outsider = join(
        client,
        client.get(f"/v1/sessions/{game.session_id}", headers=game.facilitator).json()["join_code"],
        "Boris",
        other_team["id"],
    )
    response = client.post(
        f"/v1/teams/{game.team_id}/dice",
        json={"stage": "analysis"},
        headers=auth_header(outsider["access_token"]),
    )
    assert response.status_code == 403
    facilitator_roll = client.post(
        f"/v1/teams/{game.team_id}/dice", json={"stage": "analysis"}, headers=game.facilitator
    )
    assert facilitator_roll.status_code == 403
    unknown = game.roll("review")
    assert unknown.status_code == 422


# --------------------------------------------------------------------------- spending points


def test_points_in_the_own_stage_cross_one_square_each(game: Game, dice: list[int]):
    dice.append(4)
    game.roll("analysis")
    response = game.spend(6, "analysis", 1)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["squares_crossed"] == 1
    assert body["points_left"] == 3
    assert body["card"]["squares_left"]["analysis"] == 1
    assert body["card"]["state"] == "in_progress"


def test_finishing_the_work_marks_the_card_ready(game: Game, dice: list[int]):
    dice.append(4)
    game.roll("analysis")
    body = game.spend(6, "analysis", 2).json()
    assert body["card"]["squares_left"]["analysis"] == 0
    assert body["card"]["state"] == "ready"
    nothing_left = game.spend(6, "analysis", 1)
    assert nothing_left.status_code == 422
    assert "No work left in Analysis" in nothing_left.json()["error"]["message"]


def test_help_from_another_stage_counts_half_rounded_down(game: Game, dice: list[int]):
    dice.append(5)
    game.roll("development")
    body = game.spend(6, "development", 3).json()  # a card in Analysis, helped by Development
    assert body["squares_crossed"] == 1
    assert body["points_lost_to_rounding"] == 1
    assert body["points_left"] == 2
    assert body["card"]["squares_left"]["analysis"] == 1
    single = game.spend(6, "development", 1)
    assert single.status_code == 422
    assert "at least 2 points" in single.json()["error"]["message"]


def test_cannot_spend_more_than_the_die_gave_or_before_rolling(game: Game, dice: list[int]):
    before = game.spend(6, "analysis", 1)
    assert before.status_code == 422
    assert "Roll the Analysis die first" in before.json()["error"]["message"]
    dice.append(2)
    game.roll("analysis")
    too_many = game.spend(5, "analysis", 3)
    assert too_many.status_code == 422
    assert "Only 2 points left" in too_many.json()["error"]["message"]
    assert game.spend(6, "analysis", 2).status_code == 200
    assert game.spend(5, "analysis", 1).status_code == 422  # the die is used up


def test_cannot_spend_more_squares_than_the_card_needs(game: Game, dice: list[int]):
    dice.append(6)
    game.roll("analysis")
    response = game.spend(6, "analysis", 3)
    assert response.status_code == 422
    assert "only 2 squares left" in response.json()["error"]["message"]


def test_a_repeated_spend_request_changes_nothing(game: Game, dice: list[int]):
    dice.append(6)
    game.roll("analysis")
    request_id = str(uuid.uuid4())
    first = game.spend(6, "analysis", 1, request_id)
    second = game.spend(6, "analysis", 1, request_id)
    assert second.status_code == 200
    assert second.json()["replayed"] is True
    assert second.json()["points_left"] == first.json()["points_left"] == 5
    assert game.card(6)["squares_left"]["analysis"] == 1


def test_backlog_cards_take_no_points(game: Game, dice: list[int]):
    dice.append(6)
    game.roll("analysis")
    response = game.spend(1, "analysis", 1)
    assert response.status_code == 422
    assert "work stage" in response.json()["error"]["message"]


# --------------------------------------------------------------------------- moves


def test_card_walks_through_the_board_one_stage_at_a_time(game: Game, dice: list[int]):
    dice.extend([6, 6, 6])
    for stage in ("analysis", "development", "testing"):
        game.roll(stage)
    game.spend(6, "analysis", 2)
    moved = game.move(6, "development")
    assert moved.status_code == 200, moved.text
    assert moved.json()["card"]["stage"] == "development"
    assert moved.json()["card"]["state"] == "in_progress"
    game.spend(6, "development", 3)
    game.move(6, "testing")
    game.spend(6, "testing", 2)
    done = game.move(6, "done")
    assert done.json()["card"]["stage"] == "done"
    assert done.json()["card"]["state"] is None


def test_move_is_refused_when_work_is_left_or_a_stage_is_skipped(game: Game):
    unfinished = game.move(6, "development")
    assert unfinished.status_code == 422
    assert "Finish the work in Analysis first" in unfinished.json()["error"]["message"]
    skipped = game.move(1, "development")
    assert skipped.status_code == 422
    assert "Next stage is Analysis" in skipped.json()["error"]["message"]
    backwards = game.move(6, "backlog")
    assert backwards.status_code == 422
    assert "forward only" in backwards.json()["error"]["message"]
    assert game.card(6)["stage"] == "analysis"


def test_a_repeated_move_request_is_not_applied_twice(game: Game, dice: list[int]):
    dice.append(6)
    game.roll("analysis")
    game.spend(6, "analysis", 2)
    request_id = str(uuid.uuid4())
    first = game.move(6, "development", request_id)
    second = game.move(6, "development", request_id)
    assert first.json()["replayed"] is False
    assert second.status_code == 200
    assert second.json()["replayed"] is True
    assert game.card(6)["stage"] == "development"


def test_wip_limit_applies_from_day_five(game: Game):
    # Day 1: five cards sit in Analysis although the limit is 2, because there is no limit yet.
    assert game.board()["wip"][0] == {"stage": "analysis", "count": 5, "limit": 2}
    for _ in range(4):
        game.next_day()
    assert game.board()["wip_limits_enabled"] is True
    pulled = game.move(1, "analysis")
    assert pulled.status_code == 422
    assert "WIP limit Analysis 5/2" in pulled.json()["error"]["message"]


def test_a_move_into_a_free_column_is_allowed_with_limits_on(game: Game, dice: list[int]):
    for _ in range(4):
        game.next_day()  # day 5: limits are on
    dice.append(6)
    game.roll("analysis")
    game.spend(6, "analysis", 2)
    moved = game.move(6, "development")  # Development is empty, its limit is 3
    assert moved.status_code == 200, moved.text


# --------------------------------------------------------------------------- reading


def test_board_is_private_to_the_team_and_its_facilitator(client: TestClient, game: Game):
    other = register_facilitator(client, "other@x.com")
    assert client.get(f"/v1/teams/{game.team_id}/board", headers=other).status_code == 403
    assert client.get(f"/v1/teams/{game.team_id}/board").status_code == 401
    assert (
        client.get(f"/v1/teams/{game.team_id}/board", headers=game.facilitator).status_code == 200
    )
    unknown = client.get(f"/v1/teams/{uuid.uuid4()}/board", headers=game.facilitator)
    assert unknown.status_code == 404


def test_results_and_flow_report_money_and_lead_time(
    client: TestClient, game: Game, dice: list[int]
):
    dice.extend([6, 6, 6])
    for stage in ("analysis", "development", "testing"):
        game.roll(stage)
    game.spend(6, "analysis", 2)
    game.move(6, "development")
    game.spend(6, "development", 3)
    game.move(6, "testing")
    game.spend(6, "testing", 2)
    game.move(6, "done")

    results = client.get(f"/v1/sessions/{game.session_id}/results", headers=game.facilitator)
    assert results.status_code == 200
    [row] = results.json()
    assert row["team_name"] == "Alpha"
    assert row["done_cards"] == 1
    assert float(row["money_earned"]) == 60.0
    assert float(row["avg_lead_time_days"]) == 1.0  # pulled and finished on day 1, inclusive
    assert row["money_rank"] == 1

    flow = client.get(f"/v1/teams/{game.team_id}/flow", headers=game.player).json()
    done = next(c for c in flow if c["card_number"] == 6)
    assert (done["pulled_day"], done["done_day"], done["lead_time_days"]) == (1, 1, 1)
    waiting = next(c for c in flow if c["card_number"] == 1)
    assert waiting["pulled_day"] is None
    assert waiting["lead_time_days"] is None


def test_results_are_for_the_facilitator_of_the_session(client: TestClient, game: Game):
    other = register_facilitator(client, "other@x.com")
    assert client.get(f"/v1/sessions/{game.session_id}/results", headers=other).status_code == 403
    assert (
        client.get(f"/v1/sessions/{game.session_id}/results", headers=game.player).status_code
        == 403
    )


def test_unknown_card_is_not_found(game: Game):
    response = game.post(
        f"/v1/teams/{game.team_id}/cards/{uuid.uuid4()}/move",
        {"to_stage": "analysis", "request_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_the_movement_log_keeps_every_pull(db: Session, game: Game):
    count = db.scalar(sa.text("SELECT count(*) FROM card_movements"))
    assert count == 5  # the five cards pulled on day 1
