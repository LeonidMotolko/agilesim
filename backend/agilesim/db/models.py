"""ORM models of the AgileSim schema (PostgreSQL, third normal form).

Layout of the schema:

* scenario catalogue (reference data, managed by administrators):
  ``scenarios``, ``scenario_stages``, ``scenario_cards``, ``scenario_card_work``,
  ``scenario_events``;
* accounts and game sessions: ``facilitators``, ``game_sessions``, ``session_stage_limits``,
  ``teams``, ``participants``;
* game state: ``cards``, ``card_work``, ``game_events``, ``survey_responses``, ``ai_drafts``;
* append-only logs: ``card_movements``, ``dice_rolls``, ``point_spends``.

Functions, triggers, views and role grants live in the migrations (they are not mapped).
The data dictionary is in ``docs/database.md``.
"""

import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from agilesim.db.base import Base, bigint_pk, created_at, enum_check, enum_type, uuid_pk
from agilesim.db.enums import (
    AiDraftKind,
    AiDraftStatus,
    CardColumnState,
    EventEffect,
    EventSource,
    EventStatus,
    LeadTimeConvention,
    ParticipantRole,
    ScenarioKind,
    SessionStatus,
    StageKind,
    SurveyPhase,
)

# Password hashes must look like Argon2 or bcrypt output; plain text is rejected by the database.
HASH_FORMAT_REGEX = r"^\$(argon2(id|i|d)|2[aby])\$"


def _updated_at() -> Mapped[datetime]:
    return mapped_column(server_default=sa.func.now())


# --------------------------------------------------------------------------- scenario catalogue


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        sa.UniqueConstraint("code", "version", name="uq_scenarios_code_version"),
        enum_check("kind", ScenarioKind),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(sa.String(40))
    version: Mapped[int] = mapped_column(sa.SmallInteger(), server_default="1")
    kind: Mapped[ScenarioKind] = mapped_column(enum_type(ScenarioKind))
    name: Mapped[str] = mapped_column(sa.String(120))
    created_at: Mapped[datetime] = created_at()


class ScenarioStage(Base):
    """A board column of a scenario (Backlog, Analysis, Development, Testing, Done)."""

    __tablename__ = "scenario_stages"
    __table_args__ = (
        sa.UniqueConstraint("scenario_id", "code", name="uq_scenario_stages_code"),
        sa.UniqueConstraint("scenario_id", "position", name="uq_scenario_stages_position"),
        sa.UniqueConstraint("id", "scenario_id", name="uq_scenario_stages_id_scenario"),
        enum_check("kind", StageKind),
        sa.CheckConstraint("position >= 0", name="position_non_negative"),
        sa.CheckConstraint(
            "default_wip_limit IS NULL OR default_wip_limit >= 1", name="wip_limit_positive"
        ),
        sa.CheckConstraint(
            "kind = 'work' OR default_wip_limit IS NULL", name="wip_limit_only_for_work"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(sa.String(32))
    name: Mapped[str] = mapped_column(sa.String(60))
    kind: Mapped[StageKind] = mapped_column(enum_type(StageKind))
    position: Mapped[int] = mapped_column(sa.SmallInteger())
    default_wip_limit: Mapped[int | None] = mapped_column(sa.SmallInteger())


class ScenarioCard(Base):
    """A ticket of the scenario backlog: id, business value in dollars."""

    __tablename__ = "scenario_cards"
    __table_args__ = (
        sa.UniqueConstraint("scenario_id", "number", name="uq_scenario_cards_number"),
        sa.UniqueConstraint("id", "scenario_id", name="uq_scenario_cards_id_scenario"),
        sa.CheckConstraint("number >= 0", name="number_non_negative"),
        sa.CheckConstraint("value >= 0", name="value_non_negative"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    number: Mapped[int] = mapped_column(sa.SmallInteger())
    title: Mapped[str] = mapped_column(sa.String(200))
    value: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2))
    is_emergency: Mapped[bool] = mapped_column(server_default=sa.false())


class ScenarioCardWork(Base):
    """Work squares a scenario card needs on one stage (a card has one row per work stage)."""

    __tablename__ = "scenario_card_work"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["scenario_card_id", "scenario_id"],
            ["scenario_cards.id", "scenario_cards.scenario_id"],
            name="fk_scenario_card_work_card",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stage_id", "scenario_id"],
            ["scenario_stages.id", "scenario_stages.scenario_id"],
            name="fk_scenario_card_work_stage",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("squares >= 1", name="squares_positive"),
    )

    scenario_card_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stage_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # Repeats the scenario only so that both composite foreign keys can guarantee that the card
    # and the stage belong to the same scenario without a trigger.
    scenario_id: Mapped[uuid.UUID] = mapped_column()
    squares: Mapped[int] = mapped_column(sa.SmallInteger())


class ScenarioEvent(Base):
    """An event card of the scenario (day 2, 3, 6, 7 of Startup Flow)."""

    __tablename__ = "scenario_events"
    __table_args__ = (
        sa.UniqueConstraint("scenario_id", "code", name="uq_scenario_events_code"),
        sa.UniqueConstraint("id", "scenario_id", name="uq_scenario_events_id_scenario"),
        enum_check("effect", EventEffect),
        sa.CheckConstraint("day >= 1", name="day_positive"),
        sa.CheckConstraint("effect_amount IS NULL OR effect_amount >= 0", name="amount_valid"),
        sa.Index("ix_scenario_events_scenario_id_day", "scenario_id", "day"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(sa.String(40))
    day: Mapped[int] = mapped_column(sa.SmallInteger())
    title: Mapped[str] = mapped_column(sa.String(120))
    description: Mapped[str] = mapped_column(sa.Text())
    effect: Mapped[EventEffect] = mapped_column(enum_type(EventEffect))
    effect_amount: Mapped[int | None] = mapped_column(sa.SmallInteger())


# --------------------------------------------------------------------------- accounts, sessions


class Facilitator(Base):
    __tablename__ = "facilitators"
    __table_args__ = (
        sa.UniqueConstraint("email", name="uq_facilitators_email"),
        sa.CheckConstraint("email = lower(email)", name="email_lowercase"),
        sa.CheckConstraint("position('@' IN email) > 1", name="email_has_at"),
        sa.CheckConstraint(f"password_hash ~ '{HASH_FORMAT_REGEX}'", name="password_hashed"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(sa.String(254))
    display_name: Mapped[str] = mapped_column(sa.String(80))
    password_hash: Mapped[str] = mapped_column(sa.String(255))
    is_active: Mapped[bool] = mapped_column(server_default=sa.true())
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = _updated_at()


class GameSession(Base):
    __tablename__ = "game_sessions"
    __table_args__ = (
        sa.UniqueConstraint("join_code", name="uq_game_sessions_join_code"),
        enum_check("status", SessionStatus),
        enum_check("lead_time_convention", LeadTimeConvention),
        sa.CheckConstraint("join_code ~ '^[A-Z0-9]{6}$'", name="join_code_format"),
        sa.CheckConstraint("current_day >= 0", name="current_day_non_negative"),
        sa.CheckConstraint(
            "finished_at IS NULL OR started_at IS NOT NULL", name="finished_after_started"
        ),
        sa.Index("ix_game_sessions_facilitator_id", "facilitator_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    facilitator_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("facilitators.id", ondelete="RESTRICT")
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenarios.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(sa.String(120))
    join_code: Mapped[str] = mapped_column(sa.String(6))
    status: Mapped[SessionStatus] = mapped_column(
        enum_type(SessionStatus), server_default=SessionStatus.LOBBY.value
    )
    current_day: Mapped[int] = mapped_column(sa.SmallInteger(), server_default="0")
    wip_limits_enabled: Mapped[bool] = mapped_column(server_default=sa.false())
    lead_time_convention: Mapped[LeadTimeConvention] = mapped_column(
        enum_type(LeadTimeConvention), server_default=LeadTimeConvention.INCLUSIVE.value
    )
    started_at: Mapped[datetime | None] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = _updated_at()


class SessionStageLimit(Base):
    """WIP limit chosen for one stage of one session (overrides the scenario default)."""

    __tablename__ = "session_stage_limits"
    __table_args__ = (sa.CheckConstraint("wip_limit >= 1", name="wip_limit_positive"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenario_stages.id", ondelete="RESTRICT"), primary_key=True
    )
    wip_limit: Mapped[int] = mapped_column(sa.SmallInteger())


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        sa.UniqueConstraint("session_id", "name", name="uq_teams_session_name"),
        sa.UniqueConstraint("id", "session_id", name="uq_teams_id_session"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("game_sessions.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(sa.String(60))
    created_at: Mapped[datetime] = created_at()


class Participant(Base):
    """A player. No account: a display name, a hashed join token and the consent timestamp."""

    __tablename__ = "participants"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["team_id", "session_id"],
            ["teams.id", "teams.session_id"],
            name="fk_participants_team_id_teams",
        ),
        sa.UniqueConstraint("session_id", "display_name", name="uq_participants_session_name"),
        sa.UniqueConstraint("token_hash", name="uq_participants_token_hash"),
        enum_check("role", ParticipantRole),
        sa.CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="token_hash_sha256"),
        sa.CheckConstraint("length(trim(display_name)) >= 1", name="display_name_not_blank"),
        sa.Index("ix_participants_team_id", "team_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("game_sessions.id", ondelete="CASCADE")
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column()
    display_name: Mapped[str] = mapped_column(sa.String(60))
    role: Mapped[ParticipantRole] = mapped_column(
        enum_type(ParticipantRole), server_default=ParticipantRole.PLAYER.value
    )
    token_hash: Mapped[str] = mapped_column(sa.String(64))
    consent_given_at: Mapped[datetime] = mapped_column()
    joined_at: Mapped[datetime] = created_at()


# --------------------------------------------------------------------------- game state


class Card(Base):
    """A team's copy of a scenario card and its *current* position on the board.

    Title, value and work requirements are not repeated here: they are read from the scenario
    card (third normal form). The position is kept in sync with ``card_movements`` by a trigger.
    """

    __tablename__ = "cards"
    __table_args__ = (
        sa.UniqueConstraint("team_id", "scenario_card_id", name="uq_cards_team_scenario_card"),
        sa.UniqueConstraint("id", "team_id", name="uq_cards_id_team"),
        enum_check("stage_state", CardColumnState),
        sa.Index("ix_cards_team_id_stage_id", "team_id", "stage_id"),
        sa.Index("ix_cards_scenario_card_id", "scenario_card_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    team_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("teams.id", ondelete="CASCADE"))
    scenario_card_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenario_cards.id", ondelete="RESTRICT")
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenario_stages.id", ondelete="RESTRICT")
    )
    stage_state: Mapped[CardColumnState | None] = mapped_column(enum_type(CardColumnState))
    is_blocked: Mapped[bool] = mapped_column(server_default=sa.false())
    updated_at: Mapped[datetime] = _updated_at()


class CardWork(Base):
    """Work squares still open for a card on one stage."""

    __tablename__ = "card_work"
    __table_args__ = (sa.CheckConstraint("squares_left >= 0", name="squares_left_non_negative"),)

    card_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenario_stages.id", ondelete="RESTRICT"), primary_key=True
    )
    squares_left: Mapped[int] = mapped_column(sa.SmallInteger())


class GameEvent(Base):
    """An event of a session: taken from the scenario, drafted by the AI, or entered by hand."""

    __tablename__ = "game_events"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["scenario_event_id"],
            ["scenario_events.id"],
            name="fk_game_events_scenario_event_id_scenario_events",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "session_id", "scenario_event_id", name="uq_game_events_session_scenario_event"
        ),
        enum_check("source", EventSource),
        enum_check("status", EventStatus),
        sa.CheckConstraint("day >= 1", name="day_positive"),
        sa.CheckConstraint(
            "status NOT IN ('confirmed', 'applied') OR confirmed_at IS NOT NULL",
            name="confirmed_has_timestamp",
        ),
        sa.CheckConstraint(
            "status <> 'applied' OR applied_at IS NOT NULL", name="applied_has_timestamp"
        ),
        sa.CheckConstraint(
            "source <> 'template' OR scenario_event_id IS NOT NULL",
            name="template_event_has_origin",
        ),
        sa.Index("ix_game_events_session_id_day", "session_id", "day"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("game_sessions.id", ondelete="CASCADE")
    )
    scenario_event_id: Mapped[uuid.UUID | None] = mapped_column()
    day: Mapped[int] = mapped_column(sa.SmallInteger())
    title: Mapped[str] = mapped_column(sa.String(120))
    description: Mapped[str] = mapped_column(sa.Text())
    source: Mapped[EventSource] = mapped_column(enum_type(EventSource))
    status: Mapped[EventStatus] = mapped_column(
        enum_type(EventStatus), server_default=EventStatus.PROPOSED.value
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("facilitators.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column()
    applied_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = created_at()


class SurveyResponse(Base):
    """Confidence survey (1-5) answered before and after the game."""

    __tablename__ = "survey_responses"
    __table_args__ = (
        sa.UniqueConstraint("participant_id", "phase", name="uq_survey_responses_phase"),
        enum_check("phase", SurveyPhase),
        sa.CheckConstraint("confidence BETWEEN 1 AND 5", name="confidence_range"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    participant_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("participants.id", ondelete="CASCADE")
    )
    phase: Mapped[SurveyPhase] = mapped_column(enum_type(SurveyPhase))
    confidence: Mapped[int] = mapped_column(sa.SmallInteger())
    submitted_at: Mapped[datetime] = created_at()


class AiDraft(Base):
    """Text drafted by the AI assistant; nothing is shown to players before it is approved."""

    __tablename__ = "ai_drafts"
    __table_args__ = (
        enum_check("kind", AiDraftKind),
        enum_check("status", AiDraftStatus),
        sa.CheckConstraint(
            "status = 'draft' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="reviewed_has_reviewer",
        ),
        sa.Index("ix_ai_drafts_session_id_kind", "session_id", "kind"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("game_sessions.id", ondelete="CASCADE")
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("teams.id", ondelete="SET NULL")
    )
    kind: Mapped[AiDraftKind] = mapped_column(enum_type(AiDraftKind))
    prompt: Mapped[str] = mapped_column(sa.Text())
    content: Mapped[str] = mapped_column(sa.Text())
    model: Mapped[str] = mapped_column(sa.String(64))
    status: Mapped[AiDraftStatus] = mapped_column(
        enum_type(AiDraftStatus), server_default=AiDraftStatus.DRAFT.value
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("facilitators.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = created_at()


# --------------------------------------------------------------------------- append-only logs


class CardMovement(Base):
    """One row per card move. The authoritative history; metrics are computed from it."""

    __tablename__ = "card_movements"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["card_id", "team_id"],
            ["cards.id", "cards.team_id"],
            name="fk_card_movements_card_id_cards",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("team_id", "request_id", name="uq_card_movements_request"),
        enum_check("from_state", CardColumnState),
        enum_check("to_state", CardColumnState),
        sa.CheckConstraint("day >= 1", name="day_positive"),
        sa.CheckConstraint(
            "num_nonnulls(actor_participant_id, actor_facilitator_id) <= 1",
            name="single_actor",
        ),
        sa.CheckConstraint(
            "NOT is_manual OR (comment IS NOT NULL AND actor_facilitator_id IS NOT NULL)",
            name="manual_needs_comment_and_facilitator",
        ),
        sa.Index("ix_card_movements_card_id_day", "card_id", "day"),
        sa.Index("ix_card_movements_team_id_day", "team_id", "day"),
    )

    id: Mapped[int] = bigint_pk()
    team_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("teams.id", ondelete="CASCADE"))
    card_id: Mapped[uuid.UUID] = mapped_column()
    day: Mapped[int] = mapped_column(sa.SmallInteger())
    from_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("scenario_stages.id", ondelete="RESTRICT")
    )
    from_state: Mapped[CardColumnState | None] = mapped_column(enum_type(CardColumnState))
    to_stage_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenario_stages.id", ondelete="RESTRICT")
    )
    to_state: Mapped[CardColumnState | None] = mapped_column(enum_type(CardColumnState))
    actor_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("participants.id", ondelete="SET NULL")
    )
    actor_facilitator_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("facilitators.id", ondelete="SET NULL")
    )
    request_id: Mapped[uuid.UUID] = mapped_column()
    is_manual: Mapped[bool] = mapped_column(server_default=sa.false())
    comment: Mapped[str | None] = mapped_column(sa.Text())
    occurred_at: Mapped[datetime] = created_at()


class DiceRoll(Base):
    """A die roll: once per team, stage and day (enforced by a unique constraint)."""

    __tablename__ = "dice_rolls"
    __table_args__ = (
        sa.UniqueConstraint("team_id", "stage_id", "day", name="uq_dice_rolls_team_stage_day"),
        sa.UniqueConstraint("team_id", "request_id", name="uq_dice_rolls_request"),
        sa.CheckConstraint("value BETWEEN 1 AND 6", name="value_range"),
        sa.CheckConstraint("day >= 1", name="day_positive"),
    )

    id: Mapped[int] = bigint_pk()
    team_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("teams.id", ondelete="CASCADE"))
    stage_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenario_stages.id", ondelete="RESTRICT")
    )
    day: Mapped[int] = mapped_column(sa.SmallInteger())
    value: Mapped[int] = mapped_column(sa.SmallInteger())
    rolled_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("participants.id", ondelete="SET NULL")
    )
    request_id: Mapped[uuid.UUID] = mapped_column()
    occurred_at: Mapped[datetime] = created_at()


class PointSpend(Base):
    """Dice points spent on a card. Help from another stage counts half, rounded down."""

    __tablename__ = "point_spends"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["card_id", "team_id"],
            ["cards.id", "cards.team_id"],
            name="fk_point_spends_card_id_cards",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("team_id", "request_id", name="uq_point_spends_request"),
        sa.CheckConstraint("day >= 1", name="day_positive"),
        sa.CheckConstraint("points_spent >= 1", name="points_positive"),
        sa.CheckConstraint(
            "squares_crossed = CASE WHEN source_stage_id = target_stage_id "
            "THEN points_spent ELSE points_spent / 2 END",
            name="half_value_rule",
        ),
        sa.Index("ix_point_spends_card_id", "card_id"),
        sa.Index("ix_point_spends_team_id_day", "team_id", "day"),
    )

    id: Mapped[int] = bigint_pk()
    team_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("teams.id", ondelete="CASCADE"))
    card_id: Mapped[uuid.UUID] = mapped_column()
    day: Mapped[int] = mapped_column(sa.SmallInteger())
    source_stage_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenario_stages.id", ondelete="RESTRICT")
    )
    target_stage_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("scenario_stages.id", ondelete="RESTRICT")
    )
    points_spent: Mapped[int] = mapped_column(sa.SmallInteger())
    squares_crossed: Mapped[int] = mapped_column(sa.SmallInteger())
    actor_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("participants.id", ondelete="SET NULL")
    )
    request_id: Mapped[uuid.UUID] = mapped_column()
    occurred_at: Mapped[datetime] = created_at()
