"""The pure rules of Startup Flow: points, help from another stage, moves and WIP limits."""

import pytest

from agilesim.core.errors import RuleViolationError
from agilesim.db.enums import StageKind
from agilesim.rules.startup_flow import StageInfo, check_move, check_spend, squares_for

BACKLOG = StageInfo("backlog", "Backlog", StageKind.BACKLOG, 0, None)
ANALYSIS = StageInfo("analysis", "Analysis", StageKind.WORK, 1, 2)
DEVELOPMENT = StageInfo("development", "Development", StageKind.WORK, 2, 3)
TESTING = StageInfo("testing", "Testing", StageKind.WORK, 3, 2)
DONE = StageInfo("done", "Done", StageKind.DONE, 4, None)


def spend(**overrides: object) -> int:
    values: dict[str, object] = {
        "points": 3,
        "points_left": 6,
        "same_stage": True,
        "squares_left": 5,
        "blocked": False,
        "target_name": "Development",
    }
    return check_spend(**(values | overrides))  # type: ignore[arg-type]


def move(current: StageInfo, target: StageInfo, **overrides: object) -> None:
    values: dict[str, object] = {
        "current": current,
        "target": target,
        "work_left_in_current": 0,
        "wip_enabled": False,
        "cards_in_target": 0,
        "is_emergency": False,
        "next_stage_name": None,
    }
    check_move(**(values | overrides))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("points", "same_stage", "expected"),
    [(3, True, 3), (1, True, 1), (2, False, 1), (3, False, 1), (5, False, 2), (6, False, 3)],
)
def test_squares_for_halves_help_rounding_down(points: int, same_stage: bool, expected: int):
    assert squares_for(points, same_stage=same_stage) == expected


def test_spend_in_own_stage_crosses_one_square_per_point():
    assert spend(points=4, squares_left=5) == 4


def test_help_from_another_stage_counts_half():
    assert spend(points=5, same_stage=False) == 2


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"blocked": True}, "Card blocked"),
        ({"points": 4, "points_left": 3}, "Only 3 points left"),
        ({"points": 1, "same_stage": False}, "at least 2 points"),
        ({"squares_left": 0}, "No work left in Development"),
        ({"points": 4, "squares_left": 3}, "only 3 squares left"),
        ({"points": 6, "same_stage": False, "squares_left": 2}, "only 2 squares left"),
    ],
)
def test_spend_rejects_what_the_rules_forbid(overrides: dict[str, object], message: str):
    with pytest.raises(RuleViolationError, match=message):
        spend(**overrides)


def test_card_moves_one_stage_forward_when_the_work_is_done():
    move(ANALYSIS, DEVELOPMENT)
    move(TESTING, DONE)
    move(BACKLOG, ANALYSIS)  # a pull needs no finished work


def test_card_cannot_move_backwards_or_stay():
    with pytest.raises(RuleViolationError, match="forward only"):
        move(DEVELOPMENT, ANALYSIS)
    with pytest.raises(RuleViolationError, match="forward only"):
        move(DEVELOPMENT, DEVELOPMENT)


def test_card_cannot_skip_a_stage():
    with pytest.raises(RuleViolationError, match="Next stage is Analysis"):
        move(BACKLOG, DEVELOPMENT, next_stage_name="Analysis")


def test_card_cannot_leave_a_stage_with_work_left():
    with pytest.raises(RuleViolationError, match="Finish the work in Analysis first"):
        move(ANALYSIS, DEVELOPMENT, work_left_in_current=1)


def test_wip_limit_blocks_a_full_column_only_when_enabled():
    move(BACKLOG, ANALYSIS, wip_enabled=False, cards_in_target=5)
    move(BACKLOG, ANALYSIS, wip_enabled=True, cards_in_target=1)
    with pytest.raises(RuleViolationError, match=r"WIP limit Analysis 2/2"):
        move(BACKLOG, ANALYSIS, wip_enabled=True, cards_in_target=2)


def test_emergency_card_ignores_the_wip_limit():
    move(BACKLOG, ANALYSIS, wip_enabled=True, cards_in_target=2, is_emergency=True)


def test_done_column_has_no_wip_limit():
    move(TESTING, DONE, wip_enabled=True, cards_in_target=50)
