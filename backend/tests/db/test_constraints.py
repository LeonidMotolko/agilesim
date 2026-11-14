"""Integrity rules enforced by the schema itself (keys, CHECK and UNIQUE constraints)."""

import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from agilesim.db.enums import CardColumnState, EventSource, EventStatus
from agilesim.db.models import (
    AiDraft,
    DiceRoll,
    Facilitator,
    GameEvent,
    GameSession,
    Participant,
    PointSpend,
    Scenario,
    ScenarioCardWork,
    ScenarioEvent,
    ScenarioStage,
    SurveyResponse,
    Team,
)
from tests.db import factories as f

pytestmark = pytest.mark.db


def test_seed_defines_the_startup_flow_board(db: Session) -> None:
    rows = db.scalars(
        sa.select(ScenarioStage)
        .where(ScenarioStage.scenario_id == f.startup_flow(db).id)
        .order_by(ScenarioStage.position)
    ).all()

    assert [(s.code, s.kind.value, s.default_wip_limit) for s in rows] == [
        ("backlog", "backlog", None),
        ("analysis", "work", 2),
        ("development", "work", 3),
        ("testing", "work", 2),
        ("done", "done", None),
    ]


def test_seed_defines_the_event_days(db: Session) -> None:
    rows = db.scalars(
        sa.select(ScenarioEvent)
        .where(ScenarioEvent.scenario_id == f.startup_flow(db).id)
        .order_by(ScenarioEvent.day)
    ).all()

    assert [(e.day, e.effect.value, e.effect_amount) for e in rows] == [
        (2, "pull_cards", 3),
        (3, "block_top_card", 3),
        (4, "none", None),
        (6, "dev_roll_bonus", 1),
        (7, "emergency_card", 0),
    ]


@pytest.mark.parametrize("password", ["secret123", "5f4dcc3b5aa765d61d8327deb882cf99", ""])
def test_plain_text_or_md5_password_is_rejected(db: Session, password: str) -> None:
    db.add(Facilitator(email="a@example.com", display_name="A", password_hash=password))

    with pytest.raises(IntegrityError, match="password_hashed"), db.begin_nested():
        db.flush()


def test_bcrypt_hash_is_accepted(db: Session) -> None:
    hashed = "$2b$12$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ01234"
    db.add(Facilitator(email="b@example.com", display_name="B", password_hash=hashed))

    db.flush()


def test_email_must_be_lowercase_and_unique(db: Session) -> None:
    f.make_facilitator(db, "anna@example.com")
    db.add(Facilitator(email="Anna2@Example.com", display_name="A", password_hash=f.ARGON2_SAMPLE))
    with pytest.raises(IntegrityError, match="email_lowercase"), db.begin_nested():
        db.flush()
    db.expunge_all()

    db.add(Facilitator(email="anna@example.com", display_name="A", password_hash=f.ARGON2_SAMPLE))
    with pytest.raises(IntegrityError, match="uq_facilitators_email"), db.begin_nested():
        db.flush()


@pytest.mark.parametrize("code", ["abc123", "ABC12", "ABC1234", "AB-123"])
def test_join_code_must_be_six_uppercase_alphanumerics(db: Session, code: str) -> None:
    facilitator = f.make_facilitator(db)
    db.add(
        GameSession(
            facilitator_id=facilitator.id,
            scenario_id=f.startup_flow(db).id,
            name="x",
            join_code=code,
        )
    )

    with pytest.raises(IntegrityError, match="join_code_format"), db.begin_nested():
        db.flush()


def test_join_code_is_unique(db: Session) -> None:
    f.make_session(db, join_code="ABC123")

    with pytest.raises(IntegrityError, match="uq_game_sessions_join_code"), db.begin_nested():
        f.make_session(db, join_code="ABC123")


def test_session_status_is_restricted(db: Session) -> None:
    with pytest.raises(StatementError), db.begin_nested():
        f.make_session(db, status="archived")


def test_participant_needs_consent(db: Session) -> None:
    team = f.make_team(db)
    db.add(
        Participant(
            session_id=team.session_id,
            team_id=team.id,
            display_name="Anna",
            token_hash=uuid.uuid4().hex * 2,
        )
    )

    with pytest.raises(IntegrityError, match="consent_given_at"), db.begin_nested():
        db.flush()


def test_participant_cannot_join_a_team_of_another_session(db: Session) -> None:
    team_a = f.make_team(db, f.make_session(db), "A")
    other_session = f.make_session(db)
    db.add(
        Participant(
            session_id=other_session.id,
            team_id=team_a.id,
            display_name="Anna",
            token_hash=uuid.uuid4().hex * 2,
            consent_given_at=datetime.now(UTC),
        )
    )

    with pytest.raises(IntegrityError, match="fk_participants_team_id_teams"), db.begin_nested():
        db.flush()


def test_team_names_are_unique_per_session(db: Session) -> None:
    session = f.make_session(db)
    f.make_team(db, session, "Alpha")
    f.make_team(db, f.make_session(db), "Alpha")

    with pytest.raises(IntegrityError, match="uq_teams_session_name"), db.begin_nested():
        f.make_team(db, session, "Alpha")


def test_card_work_stage_must_belong_to_the_cards_scenario(db: Session) -> None:
    flow = f.startup_flow(db)
    other = Scenario(code="other", version=1, kind="kanban", name="Other")
    db.add(other)
    db.flush()
    foreign_stage = ScenarioStage(scenario_id=other.id, code="x", name="X", kind="work", position=1)
    db.add(foreign_stage)
    team = f.make_team(db)
    card = f.make_card(db, team, 104, 100)
    db.flush()

    db.add(
        ScenarioCardWork(
            scenario_card_id=card.scenario_card_id,
            stage_id=foreign_stage.id,
            scenario_id=flow.id,
            squares=3,
        )
    )

    with pytest.raises(IntegrityError, match="fk_scenario_card_work_stage"), db.begin_nested():
        db.flush()


def test_wip_limit_only_for_work_stages(db: Session) -> None:
    db.add(
        ScenarioStage(
            scenario_id=f.startup_flow(db).id,
            code="parking",
            name="Parking",
            kind="done",
            position=9,
            default_wip_limit=2,
        )
    )

    with pytest.raises(IntegrityError, match="wip_limit_only_for_work"), db.begin_nested():
        db.flush()


def test_dice_value_is_between_one_and_six(db: Session) -> None:
    team = f.make_team(db)
    stage = f.stages(db)["development"]
    db.add(DiceRoll(team_id=team.id, stage_id=stage.id, day=3, value=7, request_id=uuid.uuid4()))

    with pytest.raises(IntegrityError, match="value_range"), db.begin_nested():
        db.flush()


def test_a_stage_is_rolled_once_per_team_and_day(db: Session) -> None:
    team = f.make_team(db)
    stage = f.stages(db)["development"]
    db.add(DiceRoll(team_id=team.id, stage_id=stage.id, day=3, value=5, request_id=uuid.uuid4()))
    db.flush()
    db.add(DiceRoll(team_id=team.id, stage_id=stage.id, day=3, value=2, request_id=uuid.uuid4()))

    with pytest.raises(IntegrityError, match="uq_dice_rolls_team_stage_day"), db.begin_nested():
        db.flush()


def test_the_same_request_id_cannot_log_two_movements(db: Session) -> None:
    team = f.make_team(db)
    card = f.make_card(db, team, 104, 100)
    request_id = uuid.uuid4()
    f.move(db, card, "analysis", day=1, state=CardColumnState.READY, request_id=request_id)

    with pytest.raises(IntegrityError, match="uq_card_movements_request"), db.begin_nested():
        f.move(
            db, card, "analysis", day=1, state=CardColumnState.IN_PROGRESS, request_id=request_id
        )


def test_manual_movement_needs_a_comment_and_a_facilitator(db: Session) -> None:
    team = f.make_team(db)
    card = f.make_card(db, team, 104, 100)

    with pytest.raises(IntegrityError, match="manual_needs_comment"), db.begin_nested():
        f.move(db, card, "analysis", day=1, state=CardColumnState.READY, is_manual=True)


def test_a_movement_has_at_most_one_actor(db: Session) -> None:
    team = f.make_team(db)
    card = f.make_card(db, team, 104, 100)
    participant = f.make_participant(db, team)
    facilitator = f.make_facilitator(db)

    with pytest.raises(IntegrityError, match="single_actor"), db.begin_nested():
        f.move(
            db,
            card,
            "analysis",
            day=1,
            state=CardColumnState.READY,
            actor_participant_id=participant.id,
            actor_facilitator_id=facilitator.id,
        )


def test_movement_card_must_belong_to_the_team(db: Session) -> None:
    team = f.make_team(db, name="Alpha")
    other_team = f.make_team(db, name="Beta")
    card = f.make_card(db, other_team, 104, 100)

    with pytest.raises(IntegrityError, match="fk_card_movements_card_id_cards"), db.begin_nested():
        f.move(db, card, "analysis", day=1, state=CardColumnState.READY, team_id=team.id)


@pytest.mark.parametrize(
    ("source", "target", "points", "squares", "valid"),
    [
        ("development", "development", 3, 3, True),
        ("development", "testing", 4, 2, True),
        ("development", "testing", 5, 2, True),
        ("development", "testing", 5, 3, False),
        ("development", "development", 3, 1, False),
    ],
)
def test_help_counts_half_value_rounded_down(
    db: Session, source: str, target: str, points: int, squares: int, valid: bool
) -> None:
    team = f.make_team(db)
    card = f.make_card(db, team, 104, 100)
    stages = f.stages(db)
    spend = PointSpend(
        team_id=team.id,
        card_id=card.id,
        day=3,
        source_stage_id=stages[source].id,
        target_stage_id=stages[target].id,
        points_spent=points,
        squares_crossed=squares,
        request_id=uuid.uuid4(),
    )
    db.add(spend)

    if valid:
        db.flush()
    else:
        with pytest.raises(IntegrityError, match="half_value_rule"), db.begin_nested():
            db.flush()


def test_survey_confidence_is_one_to_five_once_per_phase(db: Session) -> None:
    participant = f.make_participant(db, f.make_team(db))
    db.add(SurveyResponse(participant_id=participant.id, phase="pre", confidence=6))
    with pytest.raises(IntegrityError, match="confidence_range"), db.begin_nested():
        db.flush()
    db.expunge_all()

    db.add(SurveyResponse(participant_id=participant.id, phase="pre", confidence=3))
    db.flush()
    db.add(SurveyResponse(participant_id=participant.id, phase="pre", confidence=4))
    with pytest.raises(IntegrityError, match="uq_survey_responses_phase"), db.begin_nested():
        db.flush()


def test_ai_draft_must_be_reviewed_by_someone_to_leave_draft_state(db: Session) -> None:
    session = f.make_session(db)
    db.add(
        AiDraft(
            session_id=session.id,
            kind="retro_feedback",
            prompt="p",
            content="c",
            model="claude",
            status="approved",
        )
    )

    with pytest.raises(IntegrityError, match="reviewed_has_reviewer"), db.begin_nested():
        db.flush()


def test_applied_event_needs_confirmation_and_timestamps(db: Session) -> None:
    session = f.make_session(db)
    db.add(
        GameEvent(
            session_id=session.id,
            day=2,
            title="Marketing push",
            description="d",
            source=EventSource.MANUAL,
            status=EventStatus.APPLIED,
        )
    )

    with pytest.raises(IntegrityError, match="has_timestamp"), db.begin_nested():
        db.flush()


def test_a_scenario_event_is_instantiated_once_per_session(db: Session) -> None:
    session = f.make_session(db)
    event = db.scalars(
        sa.select(ScenarioEvent).where(ScenarioEvent.scenario_id == f.startup_flow(db).id)
    ).first()
    assert event is not None

    def instance() -> GameEvent:
        return GameEvent(
            session_id=session.id,
            scenario_event_id=event.id,
            day=event.day,
            title=event.title,
            description=event.description,
            source=EventSource.TEMPLATE,
        )

    db.add(instance())
    db.flush()
    db.add(instance())

    with (
        pytest.raises(IntegrityError, match="uq_game_events_session_scenario_event"),
        db.begin_nested(),
    ):
        db.flush()


def test_deleting_a_team_that_has_participants_is_refused(db: Session) -> None:
    team = f.make_team(db)
    f.make_participant(db, team)

    with pytest.raises(IntegrityError, match="fk_participants_team_id_teams"), db.begin_nested():
        db.execute(sa.delete(Team).where(Team.id == team.id))
