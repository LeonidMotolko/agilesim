"""Closed vocabularies stored as text columns guarded by CHECK constraints."""

from enum import StrEnum


class ScenarioKind(StrEnum):
    KANBAN = "kanban"
    SCRUM = "scrum"


class StageKind(StrEnum):
    BACKLOG = "backlog"
    WORK = "work"
    DONE = "done"


class EventEffect(StrEnum):
    """Mechanical effect of a scenario event; applied by the rule engine, not by the database."""

    NONE = "none"
    PULL_CARDS = "pull_cards"
    BLOCK_TOP_CARD = "block_top_card"
    DEV_ROLL_BONUS = "dev_roll_bonus"
    EMERGENCY_CARD = "emergency_card"


class LeadTimeConvention(StrEnum):
    INCLUSIVE = "inclusive"  # Done day - pull day + 1 (default, Q17)
    DIFFERENCE = "difference"  # Done day - pull day


class SessionStatus(StrEnum):
    LOBBY = "lobby"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


class ParticipantRole(StrEnum):
    PLAYER = "player"
    SCRUM_MASTER = "scrum_master"


class CardColumnState(StrEnum):
    """Sub-state of a card inside a board column."""

    IN_PROGRESS = "in_progress"
    READY = "ready"


class EventSource(StrEnum):
    TEMPLATE = "template"
    AI = "ai"
    MANUAL = "manual"


class EventStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class SurveyPhase(StrEnum):
    PRE = "pre"
    POST = "post"


class AiDraftKind(StrEnum):
    EVENT = "event"
    RETRO_FEEDBACK = "retro_feedback"


class AiDraftStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
