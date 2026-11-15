"""Engine behaviour is tested with throwaway rules defined here, not real simulation rules."""

from dataclasses import dataclass

from agilesim.rules import Action, RuleEngine, Violation


@dataclass(frozen=True)
class _Board:
    in_progress: int
    limit: int


class _LimitRule:
    rule_id = "TEST_LIMIT"

    def check(self, state: _Board, action: Action) -> list[Violation]:
        if action.kind == "start" and state.in_progress >= state.limit:
            return [Violation(self.rule_id, "limit reached")]
        return []


class _AlwaysFailsRule:
    rule_id = "TEST_ALWAYS_FAILS"

    def check(self, state: _Board, action: Action) -> list[Violation]:
        return [Violation(self.rule_id, "nope")]


def test_engine_without_rules_allows_everything() -> None:
    engine = RuleEngine[_Board]([])

    assert engine.is_allowed(_Board(in_progress=99, limit=1), Action("start"))


def test_engine_reports_violation_from_rule() -> None:
    engine = RuleEngine([_LimitRule()])

    violations = engine.validate(_Board(in_progress=2, limit=2), Action("start"))

    assert violations == [Violation("TEST_LIMIT", "limit reached")]


def test_engine_allows_action_within_limit() -> None:
    engine = RuleEngine([_LimitRule()])

    assert engine.is_allowed(_Board(in_progress=1, limit=2), Action("start"))


def test_engine_collects_violations_from_all_rules() -> None:
    engine = RuleEngine([_LimitRule(), _AlwaysFailsRule()])

    violations = engine.validate(_Board(in_progress=2, limit=2), Action("start"))

    assert [v.rule_id for v in violations] == ["TEST_LIMIT", "TEST_ALWAYS_FAILS"]


def test_engine_exposes_rule_ids_in_order() -> None:
    engine = RuleEngine([_LimitRule(), _AlwaysFailsRule()])

    assert engine.rule_ids == ("TEST_LIMIT", "TEST_ALWAYS_FAILS")


def test_validate_does_not_mutate_state() -> None:
    board = _Board(in_progress=2, limit=2)
    engine = RuleEngine([_LimitRule()])

    engine.validate(board, Action("start"))

    assert board == _Board(in_progress=2, limit=2)
