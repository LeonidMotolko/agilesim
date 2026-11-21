"""Rules of the Startup Flow (Kanban) simulation as small pure functions.

No database and no HTTP here: every function receives plain values and raises a
``RuleViolationError`` with the message the player sees. That keeps the rules easy to test.
"""

from dataclasses import dataclass

from agilesim.core.constants import HELP_DIVISOR
from agilesim.core.errors import RuleViolationError
from agilesim.db.enums import StageKind


@dataclass(frozen=True, slots=True)
class StageInfo:
    """A board column as the rules see it."""

    code: str
    name: str
    kind: StageKind
    position: int
    wip_limit: int | None


def squares_for(points: int, *, same_stage: bool) -> int:
    """Squares crossed out by ``points``: help from another stage counts half, rounded down."""
    return points if same_stage else points // HELP_DIVISOR


def check_spend(
    *,
    points: int,
    points_left: int,
    same_stage: bool,
    squares_left: int,
    blocked: bool,
    target_name: str,
) -> int:
    """Validate spending ``points`` on a card and return the squares it crosses out."""
    if blocked:
        raise RuleViolationError("Card blocked")
    if points > points_left:
        raise RuleViolationError(f"Only {points_left} points left")
    if not same_stage and points < HELP_DIVISOR:
        raise RuleViolationError("Help from another stage needs at least 2 points")
    if squares_left <= 0:
        raise RuleViolationError(f"No work left in {target_name} on this card")
    crossed = squares_for(points, same_stage=same_stage)
    if crossed > squares_left:
        raise RuleViolationError(f"{target_name} has only {squares_left} squares left on this card")
    return crossed


def check_move(
    *,
    current: StageInfo,
    target: StageInfo,
    work_left_in_current: int,
    wip_enabled: bool,
    cards_in_target: int,
    is_emergency: bool,
    next_stage_name: str | None,
) -> None:
    """Validate a move of a card to ``target``; raise when a rule forbids it."""
    if target.position <= current.position:
        raise RuleViolationError("Cards move forward only (left to right)")
    if target.position != current.position + 1:
        raise RuleViolationError(f"Next stage is {next_stage_name or target.name}")
    if current.kind is StageKind.WORK and work_left_in_current > 0:
        raise RuleViolationError(f"Finish the work in {current.name} first")
    if (
        wip_enabled
        and not is_emergency
        and target.kind is StageKind.WORK
        and target.wip_limit is not None
        and cards_in_target >= target.wip_limit
    ):
        raise RuleViolationError(f"WIP limit {target.name} {cards_in_target}/{target.wip_limit}")
