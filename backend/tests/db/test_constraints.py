"""Integrity rules enforced by the schema itself (keys, CHECK and UNIQUE constraints)."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from agilesim.db.enums import CardColumnState, EventSource, EventStatus
from agilesim.db.models import (
    AiDraft,
    CardWork,
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
    SessionStageLimit,
    SurveyResponse,
    Team,
)
from tests.db import factories as f
from tests.db.conftest import failing

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


@pytest.mark.parametrize(
    "password",
    [
        "secret123",
        "",
        "5f4dcc3b5aa765d61d8327deb882cf99",  # MD5
        "5baa61e4c9b93f3f0682250b6cf8331b7ee68fd8",  # SHA-1
        "$2b$secret123",  # a bcrypt prefix in front of plain text
        "$argon2id$secret123",
    ],
)
def test_plain_text_or_md5_password_is_rejected(db: Session, password: str) -> None:
    db.add(Facilitator(email="a@example.com", display_name="A", password_hash=password))

    with failing(db, IntegrityError, match="password_hashed"):
        db.flush()


def test_bcrypt_hash_is_accepted(db: Session) -> None:
    hashed = "$2b$12$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ01234"
    db.add(Facilitator(email="b@example.com", display_name="B", password_hash=hashed))

    db.flush()


def test_email_must_be_lowercase_and_unique(db: Session) -> None:
    f.make_facilitator(db, "anna@example.com")
    db.add(Facilitator(email="Anna2@Example.com", display_name="A", password_hash=f.ARGON2_SAMPLE))
    with failing(db, IntegrityError, match="email_lowercase"):
        db.flush()
    db.expunge_all()

    db.add(Facilitator(email="anna@example.com", display_name="A", password_hash=f.ARGON2_SAMPLE))
    with failing(db, IntegrityError, match="uq_facilitators_email"):
        db.flush()


@pytest.mark.parametrize("code", ["abc123", "ABC12", "AB-123", "ABC 12"])
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

    with failing(db, IntegrityError, match="join_code_format"):
        db.flush()


def test_join_code_is_unique(db: Session) -> None:
    f.make_session(db, join_code="ABC123")

    with failing(db, IntegrityError, match="uq_game_sessions_join_code"):
        f.make_session(db, join_code="ABC123")


def test_session_status_is_restricted(db: Session) -> None:
    with failing(db, StatementError):
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

    with failing(db, IntegrityError, match="consent_given_at"):
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

    with failing(db, IntegrityError, match="fk_participants_team_id_teams"):
        db.flush()


def test_team_names_are_unique_per_session(db: Session) -> None:
    session = f.make_session(db)
    f.make_team(db, session, "Alpha")
    f.make_team(db, f.make_session(db), "Alpha")

    with failing(db, IntegrityError, match="uq_teams_session_name"):
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

    with failing(db, IntegrityError, match="fk_scenario_card_work_stage"):
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

    with failing(db, IntegrityError, match="wip_limit_only_for_work"):
        db.flush()


def test_dice_value_is_between_one_and_six(db: Session) -> None:
    team = f.make_team(db)
    stage = f.stages(db)["development"]
    db.add(DiceRoll(team_id=team.id, stage_id=stage.id, day=3, value=7, request_id=uuid.uuid4()))

    with failing(db, IntegrityError, match="value_range"):
        db.flush()


def test_a_stage_is_rolled_once_per_team_and_day(db: Session) -> None:
    team = f.make_team(db)
    stage = f.stages(db)["development"]
    db.add(DiceRoll(team_id=team.id, stage_id=stage.id, day=3, value=5, request_id=uuid.uuid4()))
    db.flush()
    db.add(DiceRoll(team_id=team.id, stage_id=stage.id, day=3, value=2, request_id=uuid.uuid4()))

    with failing(db, IntegrityError, match="uq_dice_rolls_team_stage_day"):
        db.flush()


def test_the_same_request_id_cannot_log_two_movements(db: Session) -> None:
    team = f.make_team(db)
    card = f.make_card(db, team, 104, 100)
    request_id = uuid.uuid4()
    f.move(db, card, "analysis", day=1, state=CardColumnState.READY, request_id=request_id)

    with failing(db, IntegrityError, match="uq_card_movements_request"):
        f.move(
            db, card, "analysis", day=1, state=CardColumnState.IN_PROGRESS, request_id=request_id
        )


def test_manual_movement_needs_a_comment_and_a_facilitator(db: Session) -> None:
    team = f.make_team(db)
    card = f.make_card(db, team, 104, 100)

    with failing(db, IntegrityError, match="manual_needs_comment_and_facilitator"):
        f.move(db, card, "analysis", day=1, state=CardColumnState.READY, is_manual=True)


def test_a_movement_has_at_most_one_actor(db: Session) -> None:
    team = f.make_team(db)
    card = f.make_card(db, team, 104, 100)
    participant = f.make_participant(db, team)
    facilitator = f.make_facilitator(db)

    with failing(db, IntegrityError, match="single_actor"):
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

    with failing(db, IntegrityError, match="fk_card_movements_card_id_cards"):
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
        with failing(db, IntegrityError, match="half_value_rule"):
            db.flush()


def test_survey_confidence_is_one_to_five_once_per_phase(db: Session) -> None:
    participant = f.make_participant(db, f.make_team(db))
    db.add(SurveyResponse(participant_id=participant.id, phase="pre", confidence=6))
    with failing(db, IntegrityError, match="confidence_range"):
        db.flush()
    db.expunge_all()

    db.add(SurveyResponse(participant_id=participant.id, phase="pre", confidence=3))
    db.flush()
    db.add(SurveyResponse(participant_id=participant.id, phase="pre", confidence=4))
    with failing(db, IntegrityError, match="uq_survey_responses_phase"):
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

    with failing(db, IntegrityError, match="reviewed_has_reviewer"):
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

    with failing(db, IntegrityError, match="has_timestamp"):
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

    with failing(db, IntegrityError, match="uq_game_events_session_scenario_event"):
        db.flush()


def test_deleting_a_team_that_has_participants_is_refused(db: Session) -> None:
    team = f.make_team(db)
    f.make_participant(db, team)

    with failing(db, IntegrityError, match="fk_participants_team_id_teams"):
        db.execute(sa.delete(Team).where(Team.id == team.id))


# ------------------------------------------------------------------ every CHECK constraint

_MOVE = (
    "INSERT INTO card_movements (team_id, card_id, day, from_state, to_stage_id, to_state, "
    "request_id) SELECT team_id, id, {day}, {from_state}, stage_id, {to_state}, "
    "gen_random_uuid() FROM cards"
)
_SPEND = (
    "INSERT INTO point_spends (team_id, card_id, day, source_stage_id, target_stage_id, "
    "points_spent, squares_crossed, request_id) "
    "SELECT team_id, id, {day}, stage_id, stage_id, {points}, {points}, gen_random_uuid() "
    "FROM cards"
)

# One invalid statement per constraint that the tests above do not already exercise.
INVALID_STATEMENTS = [
    ("ck_scenarios_kind_valid", "UPDATE scenarios SET kind = 'x'"),
    ("ck_scenarios_version_positive", "UPDATE scenarios SET version = 0"),
    ("ck_scenario_stages_kind_valid", "UPDATE scenario_stages SET kind = 'x' WHERE kind = 'done'"),
    ("ck_scenario_stages_position_non_negative", "UPDATE scenario_stages SET position = -1"),
    (
        "ck_scenario_stages_wip_limit_positive",
        "UPDATE scenario_stages SET default_wip_limit = 0 WHERE kind = 'work'",
    ),
    ("ck_scenario_cards_number_non_negative", "UPDATE scenario_cards SET number = -1"),
    ("ck_scenario_cards_value_non_negative", "UPDATE scenario_cards SET value = -0.01"),
    ("ck_scenario_card_work_squares_positive", "UPDATE scenario_card_work SET squares = 0"),
    ("ck_scenario_events_day_positive", "UPDATE scenario_events SET day = 0"),
    ("ck_scenario_events_effect_valid", "UPDATE scenario_events SET effect = 'x'"),
    ("ck_scenario_events_amount_valid", "UPDATE scenario_events SET effect_amount = -1"),
    ("ck_facilitators_email_has_at", "UPDATE facilitators SET email = 'no-at-sign'"),
    ("ck_game_sessions_status_valid", "UPDATE game_sessions SET status = 'x'"),
    (
        "ck_game_sessions_lead_time_convention_valid",
        "UPDATE game_sessions SET lead_time_convention = 'x'",
    ),
    ("ck_game_sessions_current_day_non_negative", "UPDATE game_sessions SET current_day = -1"),
    (
        "ck_game_sessions_finished_after_started",
        "UPDATE game_sessions SET started_at = NULL, finished_at = now()",
    ),
    ("ck_session_stage_limits_wip_limit_positive", "UPDATE session_stage_limits SET wip_limit = 0"),
    ("ck_participants_role_valid", "UPDATE participants SET role = 'x'"),
    ("ck_participants_token_hash_sha256", "UPDATE participants SET token_hash = 'not-a-hash'"),
    ("ck_participants_display_name_not_blank", "UPDATE participants SET display_name = '   '"),
    (
        "uq_participants_token_hash",
        "INSERT INTO participants (session_id, display_name, token_hash, consent_given_at) "
        "SELECT session_id, 'Someone else', token_hash, now() FROM participants",
    ),
    ("ck_cards_stage_state_valid", "UPDATE cards SET stage_state = 'x'"),
    (
        "uq_cards_team_scenario_card",
        "INSERT INTO cards (team_id, scenario_card_id, stage_id) "
        "SELECT team_id, scenario_card_id, stage_id FROM cards",
    ),
    ("ck_card_work_squares_left_non_negative", "UPDATE card_work SET squares_left = -1"),
    ("ck_game_events_day_positive", "UPDATE game_events SET day = 0"),
    ("ck_game_events_source_valid", "UPDATE game_events SET source = 'x'"),
    ("ck_game_events_status_valid", "UPDATE game_events SET status = 'x'"),
    ("ck_game_events_confirmed_has_timestamp", "UPDATE game_events SET status = 'confirmed'"),
    (
        "ck_game_events_applied_has_timestamp",
        "UPDATE game_events SET status = 'applied', confirmed_at = now()",
    ),
    ("ck_game_events_template_event_has_origin", "UPDATE game_events SET source = 'template'"),
    ("ck_survey_responses_phase_valid", "UPDATE survey_responses SET phase = 'x'"),
    ("ck_ai_drafts_kind_valid", "UPDATE ai_drafts SET kind = 'x'"),
    (
        "ck_ai_drafts_status_valid",
        "UPDATE ai_drafts SET status = 'x', reviewed_at = now(), "
        "reviewed_by = (SELECT id FROM facilitators LIMIT 1)",
    ),
    (
        "ck_card_movements_day_positive",
        _MOVE.format(day=0, from_state="NULL", to_state="NULL"),
    ),
    (
        "ck_card_movements_from_state_valid",
        _MOVE.format(day=1, from_state="'x'", to_state="NULL"),
    ),
    (
        "ck_card_movements_to_state_valid",
        _MOVE.format(day=1, from_state="NULL", to_state="'x'"),
    ),
    (
        "ck_dice_rolls_day_positive",
        "INSERT INTO dice_rolls (team_id, stage_id, day, value, request_id) "
        "SELECT team_id, stage_id, 0, 3, gen_random_uuid() FROM cards",
    ),
    ("ck_point_spends_day_positive", _SPEND.format(day=0, points=2)),
    ("ck_point_spends_points_positive", _SPEND.format(day=1, points=0)),
]


@pytest.fixture
def one_row_of_each(db: Session) -> None:
    """A valid row in every table, so that each statement below has something to break."""
    team = f.make_team(db)
    participant = f.make_participant(db, team)
    card = f.make_card(db, team, 104, 100)
    analysis = f.stages(db)["analysis"]
    db.add_all(
        [
            ScenarioCardWork(
                scenario_card_id=card.scenario_card_id,
                stage_id=analysis.id,
                scenario_id=analysis.scenario_id,
                squares=3,
            ),
            CardWork(card_id=card.id, stage_id=analysis.id, squares_left=3),
            SessionStageLimit(session_id=team.session_id, stage_id=analysis.id, wip_limit=2),
            GameEvent(
                session_id=team.session_id,
                day=2,
                title="Manual event",
                description="d",
                source=EventSource.MANUAL,
            ),
            SurveyResponse(participant_id=participant.id, phase="pre", confidence=3),
            AiDraft(session_id=team.session_id, kind="event", prompt="p", content="c", model="m"),
        ]
    )
    db.flush()


@pytest.mark.usefixtures("one_row_of_each")
@pytest.mark.parametrize(
    ("constraint", "statement"), INVALID_STATEMENTS, ids=[c for c, _ in INVALID_STATEMENTS]
)
def test_every_constraint_rejects_an_invalid_row(
    db: Session, constraint: str, statement: str
) -> None:
    with failing(db, IntegrityError, match=constraint):
        db.execute(sa.text(statement))


def test_every_check_constraint_has_a_test(db: Session) -> None:
    """A new CHECK constraint needs a test in this file (matched by full or short name)."""
    rows = db.execute(
        sa.text(
            "SELECT c.conname, CAST(CAST(c.conrelid AS regclass) AS text) AS table_name "
            "FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
            "WHERE n.nspname = 'public' AND c.contype = 'c'"
        )
    ).all()
    source = Path(__file__).read_text(encoding="utf-8")

    assert len(rows) >= 47
    untested = [
        row.conname
        for row in rows
        if f'"{row.conname}"' not in source
        and f'"{row.conname.removeprefix(f"ck_{row.table_name}_")}"' not in source
    ]
    assert untested == []
