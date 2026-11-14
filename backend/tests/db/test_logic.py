"""Business logic in the database: append-only logs, triggers, masking, views and roles."""

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from agilesim.db.enums import CardColumnState
from agilesim.db.models import CardMovement, DiceRoll, GameSession, Participant, Team
from tests.db import factories as f
from tests.db.conftest import as_role, failing

pytestmark = pytest.mark.db

READY = CardColumnState.READY
IN_PROGRESS = CardColumnState.IN_PROGRESS


# ------------------------------------------------------------------ append-only logs


def test_a_logged_movement_cannot_be_updated(db: Session) -> None:
    card = f.make_card(db, f.make_team(db), 104, 100)
    movement = f.move(db, card, "analysis", day=1, state=READY)

    with failing(db, IntegrityError, match="append-only"):
        db.execute(sa.update(CardMovement).where(CardMovement.id == movement.id).values(day=2))


def test_a_logged_movement_cannot_be_deleted(db: Session) -> None:
    card = f.make_card(db, f.make_team(db), 104, 100)
    movement = f.move(db, card, "analysis", day=1, state=READY)

    with failing(db, IntegrityError, match="append-only"):
        db.execute(sa.delete(CardMovement).where(CardMovement.id == movement.id))


def test_a_dice_roll_cannot_be_changed(db: Session) -> None:
    team = f.make_team(db)
    stage = f.stages(db)["development"]
    roll = DiceRoll(team_id=team.id, stage_id=stage.id, day=3, value=5, request_id=uuid.uuid4())
    db.add(roll)
    db.flush()

    with failing(db, IntegrityError, match="append-only"):
        db.execute(sa.update(DiceRoll).where(DiceRoll.id == roll.id).values(value=6))


def test_deleting_a_session_removes_its_logs(db: Session) -> None:
    session = f.make_session(db)
    team = f.make_team(db, session)
    card = f.make_card(db, team, 104, 100)
    f.move(db, card, "analysis", day=1, state=READY)

    db.execute(sa.delete(GameSession).where(GameSession.id == session.id))

    assert db.scalar(sa.select(sa.func.count()).select_from(CardMovement)) == 0


def test_removing_a_participant_anonymises_the_log(db: Session) -> None:
    team = f.make_team(db)
    participant = f.make_participant(db, team)
    card = f.make_card(db, team, 104, 100)
    movement = f.move(db, card, "analysis", day=1, state=READY, actor_participant_id=participant.id)

    db.execute(sa.delete(Participant).where(Participant.id == participant.id))
    db.refresh(movement)

    assert movement.actor_participant_id is None


# ------------------------------------------------------------------ triggers


def test_a_movement_updates_the_cards_position(db: Session) -> None:
    card = f.make_card(db, f.make_team(db), 104, 100)
    stages = f.stages(db)
    assert card.stage_id == stages["backlog"].id

    f.move(db, card, "analysis", day=1, state=IN_PROGRESS)

    assert (card.stage_id, card.stage_state) == (stages["analysis"].id, IN_PROGRESS)


def test_a_movement_from_the_wrong_position_is_refused(db: Session) -> None:
    card = f.make_card(db, f.make_team(db), 104, 100)
    stages = f.stages(db)
    stale = CardMovement(
        team_id=card.team_id,
        card_id=card.id,
        day=1,
        from_stage_id=stages["development"].id,
        to_stage_id=stages["testing"].id,
        request_id=uuid.uuid4(),
    )
    db.add(stale)

    with failing(db, IntegrityError, match="not where the movement says"):
        db.flush()


def test_a_card_can_enter_the_board_without_a_source_stage(db: Session) -> None:
    card = f.make_card(db, f.make_team(db), 0, 0)
    stages = f.stages(db)
    db.add(
        CardMovement(
            team_id=card.team_id,
            card_id=card.id,
            day=7,
            from_stage_id=None,
            to_stage_id=stages["analysis"].id,
            to_state=READY,
            request_id=uuid.uuid4(),
        )
    )
    db.flush()
    db.refresh(card)

    assert (card.stage_id, card.stage_state) == (stages["analysis"].id, READY)


def test_updated_at_is_maintained_by_a_trigger(db: Session) -> None:
    facilitator = f.make_facilitator(db)

    facilitator.display_name = "Renamed"
    db.flush()
    db.refresh(facilitator)

    assert facilitator.updated_at > facilitator.created_at


# ------------------------------------------------------------------ masking


def test_mask_email_keeps_the_first_letter_and_the_domain(db: Session) -> None:
    assert db.scalar(sa.text("SELECT mask_email('anna.k@example.com')")) == "a***@example.com"
    assert db.scalar(sa.text("SELECT mask_email(NULL)")) is None


def test_masked_view_hides_the_address(db: Session) -> None:
    f.make_facilitator(db, "anna.k@example.com")

    rows = db.execute(sa.text("SELECT email_masked FROM facilitators_masked")).scalars().all()

    assert rows == ["a***@example.com"]


# ------------------------------------------------------------------ metrics views


def reference_team(db: Session) -> tuple[GameSession, Team]:
    """Reference cards of the analysis: ID-104 (1->5), 105 (1->3), 115 (1->8), 102 (1->2)."""
    session = f.make_session(db)
    team = f.make_team(db, session)
    for number, value, pulled, done in [
        (104, 100, 1, 5),
        (105, 80, 1, 3),
        (115, 110, 1, 8),
        (102, 40, 1, 2),
    ]:
        f.play_to_done(db, f.make_card(db, team, number, value), pulled=pulled, done=done)
    return session, team


def lead_times(db: Session, team_id: uuid.UUID) -> dict[int, int | None]:
    rows = db.execute(
        sa.text("SELECT card_number, lead_time_days FROM card_flow WHERE team_id = :t"),
        {"t": team_id},
    )
    return {row.card_number: row.lead_time_days for row in rows}


def test_lead_time_is_inclusive_by_default(db: Session) -> None:
    _, team = reference_team(db)

    assert lead_times(db, team.id) == {104: 5, 105: 3, 115: 8, 102: 2}


def test_lead_time_can_count_the_difference_instead(db: Session) -> None:
    session, team = reference_team(db)

    db.execute(
        sa.update(GameSession)
        .where(GameSession.id == session.id)
        .values(lead_time_convention="difference")
    )

    assert lead_times(db, team.id) == {104: 4, 105: 2, 115: 7, 102: 1}


def test_money_counts_only_cards_in_done(db: Session) -> None:
    _, team = reference_team(db)
    unfinished = f.make_card(db, team, 106, 90)
    f.move(db, unfinished, "analysis", day=2, state=IN_PROGRESS)

    row = db.execute(
        sa.text(
            "SELECT done_cards, money_earned, avg_lead_time_days FROM team_results "
            "WHERE team_id = :t"
        ),
        {"t": team.id},
    ).one()

    assert row.done_cards == 4
    assert row.money_earned == Decimal(330)
    assert row.avg_lead_time_days == Decimal("4.5")
    assert lead_times(db, team.id)[106] is None


def test_cards_that_were_never_pulled_have_no_dates(db: Session) -> None:
    team = f.make_team(db)
    f.make_card(db, team, 113, 70)

    row = db.execute(
        sa.text("SELECT pulled_day, done_day, lead_time_days FROM card_flow WHERE team_id = :t"),
        {"t": team.id},
    ).one()

    assert tuple(row) == (None, None, None)


def test_teams_are_ranked_by_money(db: Session) -> None:
    session = f.make_session(db)
    alpha, beta = f.make_team(db, session, "Alpha"), f.make_team(db, session, "Beta")
    f.play_to_done(db, f.make_card(db, alpha, 115, 110), pulled=1, done=8)
    f.play_to_done(db, f.make_card(db, alpha, 104, 100), pulled=1, done=5)
    f.play_to_done(db, f.make_card(db, beta, 104, 100), pulled=1, done=6)

    rows = db.execute(
        sa.text(
            "SELECT team_name, money_earned, money_rank FROM team_results "
            "WHERE session_id = :s ORDER BY money_rank"
        ),
        {"s": session.id},
    ).all()

    assert [(r.team_name, r.money_earned, r.money_rank) for r in rows] == [
        ("Alpha", Decimal(210), 1),
        ("Beta", Decimal(100), 2),
    ]


def daily_states(db: Session, card_id: uuid.UUID) -> list[tuple[int, str, str | None]]:
    rows = db.execute(
        sa.text(
            "SELECT day, stage_code, stage_state FROM card_daily_state "
            "WHERE card_id = :c ORDER BY day"
        ),
        {"c": card_id},
    )
    return [(row.day, row.stage_code, row.stage_state) for row in rows]


def test_daily_state_has_no_gap_between_the_pull_and_done(db: Session) -> None:
    card = f.make_card(db, f.make_team(db), 104, 100)
    f.move(db, card, "analysis", day=1, state=READY)
    f.move(db, card, "analysis", day=2, state=IN_PROGRESS)
    f.move(db, card, "development", day=3, state=READY)
    f.move(db, card, "development", day=4, state=IN_PROGRESS)
    f.move(db, card, "done", day=5)

    assert daily_states(db, card.id) == [
        (1, "analysis", "ready"),
        (2, "analysis", "in_progress"),
        (3, "development", "ready"),
        (4, "development", "in_progress"),
        (5, "done", None),
    ]


def test_daily_state_of_an_unfinished_card_runs_to_the_current_day(db: Session) -> None:
    session = f.make_session(db)
    card = f.make_card(db, f.make_team(db, session), 106, 90)
    f.move(db, card, "analysis", day=3, state=IN_PROGRESS)
    db.execute(sa.update(GameSession).where(GameSession.id == session.id).values(current_day=5))

    assert daily_states(db, card.id) == [
        (3, "analysis", "in_progress"),
        (4, "analysis", "in_progress"),
        (5, "analysis", "in_progress"),
    ]


# ------------------------------------------------------------------ roles and privileges


def test_application_roles_are_not_superusers(db: Session) -> None:
    rows = db.execute(
        sa.text(
            "SELECT rolname, rolsuper, rolcanlogin, rolcreaterole FROM pg_roles "
            "WHERE rolname IN ('app_read', 'app_write', 'app_admin')"
        )
    ).all()

    assert {row.rolname for row in rows} == {"app_read", "app_write", "app_admin"}
    assert not any(row.rolsuper or row.rolcanlogin or row.rolcreaterole for row in rows)
    assert db.scalar(sa.text("SELECT pg_has_role('app_write', 'app_read', 'member')"))


def test_every_table_and_view_is_readable_by_app_read(db: Session) -> None:
    names = db.scalars(
        sa.text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' "
            "AND table_name NOT IN ('alembic_version', 'facilitators')"
        )
    ).all()

    assert len(names) >= 21  # 17 tables without facilitators + 4 views
    for name in names:
        granted = db.scalar(
            sa.text("SELECT has_table_privilege('app_read', :n, 'SELECT')"), {"n": f"public.{name}"}
        )
        assert granted, f"app_read cannot read {name}: add the grant to a migration"


def test_app_read_sees_no_personal_columns_of_facilitators(db: Session) -> None:
    def can_read(column: str) -> bool:
        return bool(
            db.scalar(
                sa.text("SELECT has_column_privilege('app_read', 'facilitators', :c, 'SELECT')"),
                {"c": column},
            )
        )

    assert can_read("display_name")
    assert not can_read("email")
    assert not can_read("password_hash")


def test_app_read_cannot_select_the_email_column(db: Session) -> None:
    f.make_facilitator(db)

    with as_role(db, "app_read"):
        with failing(db, DBAPIError, match="permission denied"):
            db.execute(sa.text("SELECT email FROM facilitators"))
        masked = db.execute(sa.text("SELECT email_masked FROM facilitators_masked")).all()

    assert len(masked) == 1


def test_app_read_cannot_write(db: Session) -> None:
    session = f.make_session(db)

    with as_role(db, "app_read"):
        with failing(db, DBAPIError, match="permission denied"):
            db.execute(sa.text("UPDATE game_sessions SET name = 'x'"))
        assert db.scalar(sa.text("SELECT name FROM game_sessions")) == session.name


def test_app_write_plays_the_game_but_cannot_rewrite_history(db: Session) -> None:
    card = f.make_card(db, f.make_team(db), 104, 100)

    with as_role(db, "app_write"):
        f.move(db, card, "analysis", day=1, state=READY)
        with failing(db, DBAPIError, match="permission denied"):
            db.execute(sa.text("UPDATE card_movements SET day = 9"))
        with failing(db, DBAPIError, match="permission denied"):
            db.execute(sa.text("DELETE FROM card_movements"))


def test_app_write_cannot_change_the_scenario_catalogue(db: Session) -> None:
    f.startup_flow(db)

    with as_role(db, "app_write"):
        with failing(db, DBAPIError, match="permission denied"):
            db.execute(sa.text("UPDATE scenario_stages SET default_wip_limit = 9"))
        with failing(db, DBAPIError, match="permission denied"):
            db.execute(sa.text("DELETE FROM scenarios"))


def test_app_admin_can_change_the_scenario_catalogue(db: Session) -> None:
    with as_role(db, "app_admin"):
        db.execute(
            sa.text("UPDATE scenario_stages SET default_wip_limit = 4 WHERE code = 'testing'")
        )
        limit = db.scalar(
            sa.text("SELECT default_wip_limit FROM scenario_stages WHERE code = 'testing'")
        )

    assert limit == 4
