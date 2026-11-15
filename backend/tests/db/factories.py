"""Helpers that build valid rows for the tests."""

import uuid
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from agilesim.db.enums import CardColumnState
from agilesim.db.models import (
    Card,
    CardMovement,
    Facilitator,
    GameSession,
    Participant,
    Scenario,
    ScenarioCard,
    ScenarioStage,
    Team,
)

ARGON2_SAMPLE = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$aGFzaGhhc2hoYXNoaGFzaA"


def new_code() -> str:
    return uuid.uuid4().hex[:6].upper()


def startup_flow(db: Session) -> Scenario:
    return db.scalars(sa.select(Scenario).where(Scenario.code == "startup-flow")).one()


def stages(db: Session, scenario: Scenario | None = None) -> dict[str, ScenarioStage]:
    scenario = scenario or startup_flow(db)
    rows = db.scalars(sa.select(ScenarioStage).where(ScenarioStage.scenario_id == scenario.id))
    return {stage.code: stage for stage in rows}


def make_facilitator(db: Session, email: str | None = None) -> Facilitator:
    facilitator = Facilitator(
        email=email or f"{uuid.uuid4().hex[:8]}@example.com",
        display_name="Katsiaryna",
        password_hash=ARGON2_SAMPLE,
    )
    db.add(facilitator)
    db.flush()
    return facilitator


def make_session(db: Session, facilitator: Facilitator | None = None, **fields: Any) -> GameSession:
    facilitator = facilitator or make_facilitator(db)
    values: dict[str, Any] = {"name": "Group 1", "join_code": new_code()} | fields
    session = GameSession(
        facilitator_id=facilitator.id,
        scenario_id=startup_flow(db).id,
        **values,
    )
    db.add(session)
    db.flush()
    return session


def make_team(db: Session, session: GameSession | None = None, name: str = "Alpha") -> Team:
    session = session or make_session(db)
    team = Team(session_id=session.id, name=name)
    db.add(team)
    db.flush()
    return team


def make_participant(db: Session, team: Team, name: str = "Anna") -> Participant:
    participant = Participant(
        session_id=team.session_id,
        team_id=team.id,
        display_name=name,
        token_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        consent_given_at=sa.func.now(),
    )
    db.add(participant)
    db.flush()
    return participant


def make_card(db: Session, team: Team, number: int, value: int | str) -> Card:
    """A scenario card of the team's scenario plus the team's copy, waiting in the backlog."""
    scenario = startup_flow(db)
    scenario_card = db.scalars(
        sa.select(ScenarioCard).where(
            ScenarioCard.scenario_id == scenario.id, ScenarioCard.number == number
        )
    ).one_or_none()
    if scenario_card is None:
        scenario_card = ScenarioCard(
            scenario_id=scenario.id, number=number, title=f"Card {number}", value=Decimal(value)
        )
        db.add(scenario_card)
        db.flush()
    card = Card(
        team_id=team.id, scenario_card_id=scenario_card.id, stage_id=stages(db)["backlog"].id
    )
    db.add(card)
    db.flush()
    return card


def move(
    db: Session,
    card: Card,
    to: str,
    *,
    day: int,
    state: CardColumnState | None = None,
    **fields: Any,
) -> CardMovement:
    """Log a move from the card's current position and let the trigger update the card."""
    values: dict[str, Any] = {
        "team_id": card.team_id,
        "card_id": card.id,
        "day": day,
        "from_stage_id": card.stage_id,
        "from_state": card.stage_state,
        "to_stage_id": stages(db)[to].id,
        "to_state": state,
        "request_id": uuid.uuid4(),
    } | fields
    movement = CardMovement(**values)
    db.add(movement)
    db.flush()
    db.refresh(card)
    return movement


def play_to_done(db: Session, card: Card, *, pulled: int, done: int) -> None:
    """Pull a card on day ``pulled`` and finish it on day ``done`` (reference-set shortcut)."""
    move(db, card, "analysis", day=pulled, state=CardColumnState.IN_PROGRESS)
    move(db, card, "done", day=done)
