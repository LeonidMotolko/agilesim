"""Create the AgileSim tables.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HASH_FORMAT_REGEX = r"^\$(argon2(id|i|d)|2[aby])\$"
NOW = sa.text("now()")
NEW_UUID = sa.text("gen_random_uuid()")


def _pk(table: str, *columns: str) -> sa.PrimaryKeyConstraint:
    return sa.PrimaryKeyConstraint(*columns, name=op.f(f"pk_{table}"))


def _fk(
    table: str,
    columns: list[str],
    ref_table: str,
    ref_columns: list[str],
    ondelete: str | None = None,
    name: str | None = None,
) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        columns,
        [f"{ref_table}.{column}" for column in ref_columns],
        name=op.f(name or f"fk_{table}_{columns[0]}_{ref_table}"),
        ondelete=ondelete,
    )


def _uq(name: str, *columns: str) -> sa.UniqueConstraint:
    return sa.UniqueConstraint(*columns, name=op.f(name))


def _ck(table: str, name: str, expression: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(expression, name=op.f(f"ck_{table}_{name}"))


def _enum_ck(table: str, column: str, *values: str) -> sa.CheckConstraint:
    listed = ", ".join(f"'{value}'" for value in values)
    return _ck(table, f"{column}_valid", f"{column} IN ({listed})")


def _uuid_pk_column() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=NEW_UUID, nullable=False)


def _created_at(name: str = "created_at") -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=NOW, nullable=False)


STATES = ("in_progress", "ready")


def upgrade() -> None:
    # ------------------------------------------------------------------ scenario catalogue
    op.create_table(
        "scenarios",
        _uuid_pk_column(),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("version", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("kind", sa.String(6), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        _created_at(),
        _pk("scenarios", "id"),
        _uq("uq_scenarios_code_version", "code", "version"),
        _enum_ck("scenarios", "kind", "kanban", "scrum"),
        _ck("scenarios", "version_positive", "version >= 1"),
    )
    op.create_table(
        "scenario_stages",
        _uuid_pk_column(),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("kind", sa.String(7), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("default_wip_limit", sa.SmallInteger(), nullable=True),
        _pk("scenario_stages", "id"),
        _fk("scenario_stages", ["scenario_id"], "scenarios", ["id"], "CASCADE"),
        _uq("uq_scenario_stages_code", "scenario_id", "code"),
        _uq("uq_scenario_stages_position", "scenario_id", "position"),
        _uq("uq_scenario_stages_id_scenario", "id", "scenario_id"),
        _enum_ck("scenario_stages", "kind", "backlog", "work", "done"),
        _ck("scenario_stages", "position_non_negative", "position >= 0"),
        _ck(
            "scenario_stages",
            "wip_limit_positive",
            "default_wip_limit IS NULL OR default_wip_limit >= 1",
        ),
        _ck(
            "scenario_stages",
            "wip_limit_only_for_work",
            "kind = 'work' OR default_wip_limit IS NULL",
        ),
    )
    op.create_table(
        "scenario_cards",
        _uuid_pk_column(),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("value", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_emergency", sa.Boolean(), server_default=sa.false(), nullable=False),
        _pk("scenario_cards", "id"),
        _fk("scenario_cards", ["scenario_id"], "scenarios", ["id"], "CASCADE"),
        _uq("uq_scenario_cards_number", "scenario_id", "number"),
        _uq("uq_scenario_cards_id_scenario", "id", "scenario_id"),
        _ck("scenario_cards", "number_non_negative", "number >= 0"),
        _ck("scenario_cards", "value_non_negative", "value >= 0"),
    )
    op.create_table(
        "scenario_card_work",
        sa.Column("scenario_card_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("squares", sa.SmallInteger(), nullable=False),
        _pk("scenario_card_work", "scenario_card_id", "stage_id"),
        _fk(
            "scenario_card_work",
            ["scenario_card_id", "scenario_id"],
            "scenario_cards",
            ["id", "scenario_id"],
            "CASCADE",
            name="fk_scenario_card_work_card",
        ),
        _fk(
            "scenario_card_work",
            ["stage_id", "scenario_id"],
            "scenario_stages",
            ["id", "scenario_id"],
            "CASCADE",
            name="fk_scenario_card_work_stage",
        ),
        _ck("scenario_card_work", "squares_positive", "squares >= 1"),
    )
    op.create_table(
        "scenario_events",
        _uuid_pk_column(),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("day", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("effect", sa.String(14), nullable=False),
        sa.Column("effect_amount", sa.SmallInteger(), nullable=True),
        _pk("scenario_events", "id"),
        _fk("scenario_events", ["scenario_id"], "scenarios", ["id"], "CASCADE"),
        _uq("uq_scenario_events_code", "scenario_id", "code"),
        _uq("uq_scenario_events_id_scenario", "id", "scenario_id"),
        _enum_ck(
            "scenario_events",
            "effect",
            "none",
            "pull_cards",
            "block_top_card",
            "dev_roll_bonus",
            "emergency_card",
        ),
        _ck("scenario_events", "day_positive", "day >= 1"),
        _ck("scenario_events", "amount_valid", "effect_amount IS NULL OR effect_amount >= 0"),
    )
    op.create_index("ix_scenario_events_scenario_id_day", "scenario_events", ["scenario_id", "day"])

    # ------------------------------------------------------------------ accounts and sessions
    op.create_table(
        "facilitators",
        _uuid_pk_column(),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        _created_at(),
        _created_at("updated_at"),
        _pk("facilitators", "id"),
        _uq("uq_facilitators_email", "email"),
        _ck("facilitators", "email_lowercase", "email = lower(email)"),
        _ck("facilitators", "email_has_at", "position('@' IN email) > 1"),
        _ck("facilitators", "password_hashed", f"password_hash ~ '{HASH_FORMAT_REGEX}'"),
    )
    op.create_table(
        "game_sessions",
        _uuid_pk_column(),
        sa.Column("facilitator_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("join_code", sa.String(6), nullable=False),
        sa.Column("status", sa.String(8), server_default="lobby", nullable=False),
        sa.Column("current_day", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("wip_limits_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "lead_time_convention", sa.String(10), server_default="inclusive", nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _created_at("updated_at"),
        _pk("game_sessions", "id"),
        _fk("game_sessions", ["facilitator_id"], "facilitators", ["id"], "RESTRICT"),
        _fk("game_sessions", ["scenario_id"], "scenarios", ["id"], "RESTRICT"),
        _uq("uq_game_sessions_join_code", "join_code"),
        _enum_ck("game_sessions", "status", "lobby", "running", "paused", "finished"),
        _enum_ck("game_sessions", "lead_time_convention", "inclusive", "difference"),
        _ck("game_sessions", "join_code_format", "join_code ~ '^[A-Z0-9]{6}$'"),
        _ck("game_sessions", "current_day_non_negative", "current_day >= 0"),
        _ck(
            "game_sessions",
            "finished_after_started",
            "finished_at IS NULL OR started_at IS NOT NULL",
        ),
    )
    op.create_index("ix_game_sessions_facilitator_id", "game_sessions", ["facilitator_id"])
    op.create_table(
        "session_stage_limits",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        sa.Column("wip_limit", sa.SmallInteger(), nullable=False),
        _pk("session_stage_limits", "session_id", "stage_id"),
        _fk("session_stage_limits", ["session_id"], "game_sessions", ["id"], "CASCADE"),
        _fk("session_stage_limits", ["stage_id"], "scenario_stages", ["id"], "RESTRICT"),
        _ck("session_stage_limits", "wip_limit_positive", "wip_limit >= 1"),
    )
    op.create_table(
        "teams",
        _uuid_pk_column(),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        _created_at(),
        _pk("teams", "id"),
        _fk("teams", ["session_id"], "game_sessions", ["id"], "CASCADE"),
        _uq("uq_teams_session_name", "session_id", "name"),
        _uq("uq_teams_id_session", "id", "session_id"),
    )
    op.create_table(
        "participants",
        _uuid_pk_column(),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("display_name", sa.String(60), nullable=False),
        sa.Column("role", sa.String(12), server_default="player", nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("consent_given_at", sa.DateTime(timezone=True), nullable=False),
        _created_at("joined_at"),
        _pk("participants", "id"),
        _fk("participants", ["session_id"], "game_sessions", ["id"], "CASCADE"),
        _fk(
            "participants",
            ["team_id", "session_id"],
            "teams",
            ["id", "session_id"],
            name="fk_participants_team_id_teams",
        ),
        _uq("uq_participants_session_name", "session_id", "display_name"),
        _uq("uq_participants_token_hash", "token_hash"),
        _enum_ck("participants", "role", "player", "scrum_master"),
        _ck("participants", "token_hash_sha256", "token_hash ~ '^[0-9a-f]{64}$'"),
        _ck("participants", "display_name_not_blank", "length(trim(display_name)) >= 1"),
    )
    op.create_index("ix_participants_team_id", "participants", ["team_id"])

    # ------------------------------------------------------------------ game state
    op.create_table(
        "cards",
        _uuid_pk_column(),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_card_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        sa.Column("stage_state", sa.String(11), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), server_default=sa.false(), nullable=False),
        _created_at("updated_at"),
        _pk("cards", "id"),
        _fk("cards", ["team_id"], "teams", ["id"], "CASCADE"),
        _fk("cards", ["scenario_card_id"], "scenario_cards", ["id"], "RESTRICT"),
        _fk("cards", ["stage_id"], "scenario_stages", ["id"], "RESTRICT"),
        _uq("uq_cards_team_scenario_card", "team_id", "scenario_card_id"),
        _uq("uq_cards_id_team", "id", "team_id"),
        _enum_ck("cards", "stage_state", *STATES),
    )
    op.create_index("ix_cards_team_id_stage_id", "cards", ["team_id", "stage_id"])
    op.create_index("ix_cards_scenario_card_id", "cards", ["scenario_card_id"])
    op.create_table(
        "card_work",
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        sa.Column("squares_left", sa.SmallInteger(), nullable=False),
        _pk("card_work", "card_id", "stage_id"),
        _fk("card_work", ["card_id"], "cards", ["id"], "CASCADE"),
        _fk("card_work", ["stage_id"], "scenario_stages", ["id"], "RESTRICT"),
        _ck("card_work", "squares_left_non_negative", "squares_left >= 0"),
    )
    op.create_table(
        "game_events",
        _uuid_pk_column(),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_event_id", sa.Uuid(), nullable=True),
        sa.Column("day", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("status", sa.String(9), server_default="proposed", nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _pk("game_events", "id"),
        _fk("game_events", ["session_id"], "game_sessions", ["id"], "CASCADE"),
        _fk(
            "game_events",
            ["scenario_event_id"],
            "scenario_events",
            ["id"],
            "RESTRICT",
            name="fk_game_events_scenario_event_id_scenario_events",
        ),
        _fk("game_events", ["confirmed_by"], "facilitators", ["id"], "SET NULL"),
        _uq("uq_game_events_session_scenario_event", "session_id", "scenario_event_id"),
        _enum_ck("game_events", "source", "template", "ai", "manual"),
        _enum_ck("game_events", "status", "proposed", "confirmed", "applied", "dismissed"),
        _ck("game_events", "day_positive", "day >= 1"),
        _ck(
            "game_events",
            "confirmed_has_timestamp",
            "status NOT IN ('confirmed', 'applied') OR confirmed_at IS NOT NULL",
        ),
        _ck(
            "game_events",
            "applied_has_timestamp",
            "status <> 'applied' OR applied_at IS NOT NULL",
        ),
        _ck(
            "game_events",
            "template_event_has_origin",
            "source <> 'template' OR scenario_event_id IS NOT NULL",
        ),
    )
    op.create_index("ix_game_events_session_id_day", "game_events", ["session_id", "day"])
    op.create_table(
        "survey_responses",
        _uuid_pk_column(),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.String(4), nullable=False),
        sa.Column("confidence", sa.SmallInteger(), nullable=False),
        _created_at("submitted_at"),
        _pk("survey_responses", "id"),
        _fk("survey_responses", ["participant_id"], "participants", ["id"], "CASCADE"),
        _uq("uq_survey_responses_phase", "participant_id", "phase"),
        _enum_ck("survey_responses", "phase", "pre", "post"),
        _ck("survey_responses", "confidence_range", "confidence BETWEEN 1 AND 5"),
    )
    op.create_table(
        "ai_drafts",
        _uuid_pk_column(),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(14), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("status", sa.String(8), server_default="draft", nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _pk("ai_drafts", "id"),
        _fk("ai_drafts", ["session_id"], "game_sessions", ["id"], "CASCADE"),
        _fk("ai_drafts", ["team_id"], "teams", ["id"], "SET NULL"),
        _fk("ai_drafts", ["reviewed_by"], "facilitators", ["id"], "SET NULL"),
        _enum_ck("ai_drafts", "kind", "event", "retro_feedback"),
        _enum_ck("ai_drafts", "status", "draft", "approved", "rejected"),
        _ck(
            "ai_drafts",
            "reviewed_has_reviewer",
            "status = 'draft' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
        ),
    )
    op.create_index("ix_ai_drafts_session_id_kind", "ai_drafts", ["session_id", "kind"])

    # ------------------------------------------------------------------ append-only logs
    identity = sa.Identity(always=True)
    op.create_table(
        "card_movements",
        sa.Column("id", sa.BigInteger(), identity, nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.SmallInteger(), nullable=False),
        sa.Column("from_stage_id", sa.Uuid(), nullable=True),
        sa.Column("from_state", sa.String(11), nullable=True),
        sa.Column("to_stage_id", sa.Uuid(), nullable=False),
        sa.Column("to_state", sa.String(11), nullable=True),
        sa.Column("actor_participant_id", sa.Uuid(), nullable=True),
        sa.Column("actor_facilitator_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("is_manual", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        _created_at("occurred_at"),
        _pk("card_movements", "id"),
        _fk("card_movements", ["team_id"], "teams", ["id"], "CASCADE"),
        _fk(
            "card_movements",
            ["card_id", "team_id"],
            "cards",
            ["id", "team_id"],
            "CASCADE",
            name="fk_card_movements_card_id_cards",
        ),
        _fk("card_movements", ["from_stage_id"], "scenario_stages", ["id"], "RESTRICT"),
        _fk("card_movements", ["to_stage_id"], "scenario_stages", ["id"], "RESTRICT"),
        _fk("card_movements", ["actor_participant_id"], "participants", ["id"], "SET NULL"),
        _fk("card_movements", ["actor_facilitator_id"], "facilitators", ["id"], "SET NULL"),
        _uq("uq_card_movements_request", "team_id", "request_id"),
        _enum_ck("card_movements", "from_state", *STATES),
        _enum_ck("card_movements", "to_state", *STATES),
        _ck("card_movements", "day_positive", "day >= 1"),
        _ck(
            "card_movements",
            "single_actor",
            "num_nonnulls(actor_participant_id, actor_facilitator_id) <= 1",
        ),
        _ck(
            "card_movements",
            "manual_needs_comment_and_facilitator",
            "NOT is_manual OR (comment IS NOT NULL AND actor_facilitator_id IS NOT NULL)",
        ),
    )
    op.create_index("ix_card_movements_card_id_day", "card_movements", ["card_id", "day"])
    op.create_index("ix_card_movements_team_id_day", "card_movements", ["team_id", "day"])
    op.create_table(
        "dice_rolls",
        sa.Column("id", sa.BigInteger(), identity, nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.SmallInteger(), nullable=False),
        sa.Column("value", sa.SmallInteger(), nullable=False),
        sa.Column("rolled_by", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        _created_at("occurred_at"),
        _pk("dice_rolls", "id"),
        _fk("dice_rolls", ["team_id"], "teams", ["id"], "CASCADE"),
        _fk("dice_rolls", ["stage_id"], "scenario_stages", ["id"], "RESTRICT"),
        _fk("dice_rolls", ["rolled_by"], "participants", ["id"], "SET NULL"),
        _uq("uq_dice_rolls_team_stage_day", "team_id", "stage_id", "day"),
        _uq("uq_dice_rolls_request", "team_id", "request_id"),
        _ck("dice_rolls", "value_range", "value BETWEEN 1 AND 6"),
        _ck("dice_rolls", "day_positive", "day >= 1"),
    )
    op.create_table(
        "point_spends",
        sa.Column("id", sa.BigInteger(), identity, nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.SmallInteger(), nullable=False),
        sa.Column("source_stage_id", sa.Uuid(), nullable=False),
        sa.Column("target_stage_id", sa.Uuid(), nullable=False),
        sa.Column("points_spent", sa.SmallInteger(), nullable=False),
        sa.Column("squares_crossed", sa.SmallInteger(), nullable=False),
        sa.Column("actor_participant_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        _created_at("occurred_at"),
        _pk("point_spends", "id"),
        _fk("point_spends", ["team_id"], "teams", ["id"], "CASCADE"),
        _fk(
            "point_spends",
            ["card_id", "team_id"],
            "cards",
            ["id", "team_id"],
            "CASCADE",
            name="fk_point_spends_card_id_cards",
        ),
        _fk("point_spends", ["source_stage_id"], "scenario_stages", ["id"], "RESTRICT"),
        _fk("point_spends", ["target_stage_id"], "scenario_stages", ["id"], "RESTRICT"),
        _fk("point_spends", ["actor_participant_id"], "participants", ["id"], "SET NULL"),
        _uq("uq_point_spends_request", "team_id", "request_id"),
        _ck("point_spends", "day_positive", "day >= 1"),
        _ck("point_spends", "points_positive", "points_spent >= 1"),
        _ck(
            "point_spends",
            "half_value_rule",
            "squares_crossed = CASE WHEN source_stage_id = target_stage_id "
            "THEN points_spent ELSE points_spent / 2 END",
        ),
    )
    op.create_index("ix_point_spends_card_id", "point_spends", ["card_id"])
    op.create_index("ix_point_spends_team_id_day", "point_spends", ["team_id", "day"])


def downgrade() -> None:
    for table in (
        "point_spends",
        "dice_rolls",
        "card_movements",
        "ai_drafts",
        "survey_responses",
        "game_events",
        "card_work",
        "cards",
        "participants",
        "teams",
        "session_stage_limits",
        "game_sessions",
        "facilitators",
        "scenario_events",
        "scenario_card_work",
        "scenario_cards",
        "scenario_stages",
        "scenarios",
    ):
        op.drop_table(table)
