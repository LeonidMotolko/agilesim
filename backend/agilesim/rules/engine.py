"""Generic rule engine skeleton.

The engine knows nothing about FastAPI, the database or a concrete simulation. A simulation
(Startup Flow, LegoScrum, ...) provides its own state type and a list of rules; the engine only
asks every rule whether an action is allowed and collects the violations.

Concrete rules are added in follow-up changes, one user story at a time.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Action:
    """Something a player or the facilitator tries to do, e.g. moving a card."""

    kind: str
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Violation:
    """A rule that an action would break."""

    rule_id: str
    message: str


class Rule[S](Protocol):
    """A single, independently testable simulation rule over a state of type ``S``."""

    @property
    def rule_id(self) -> str: ...

    def check(self, state: S, action: Action) -> Sequence[Violation]:
        """Return the violations caused by ``action`` in ``state`` (empty when allowed)."""
        ...


class RuleEngine[S]:
    """Runs all configured rules against an action. Never mutates the state."""

    def __init__(self, rules: Sequence[Rule[S]]) -> None:
        self._rules = tuple(rules)

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.rule_id for rule in self._rules)

    def validate(self, state: S, action: Action) -> list[Violation]:
        return [violation for rule in self._rules for violation in rule.check(state, action)]

    def is_allowed(self, state: S, action: Action) -> bool:
        return not self.validate(state, action)
