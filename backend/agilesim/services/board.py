"""Pieces of the board shared by the game and the event services."""

import uuid
from dataclasses import dataclass
from typing import Any

from agilesim.db.enums import CardColumnState, StageKind
from agilesim.db.models import Card, GameSession, ScenarioStage
from agilesim.repositories.game import GameRepository
from agilesim.rules.startup_flow import StageInfo


@dataclass(slots=True)
class Layout:
    """The board columns of a session's scenario, with the WIP limits that apply to it."""

    by_id: dict[uuid.UUID, ScenarioStage]
    by_code: dict[str, ScenarioStage]
    limits: dict[uuid.UUID, int | None]

    def info(self, stage: ScenarioStage) -> StageInfo:
        return StageInfo(
            code=stage.code,
            name=stage.name,
            kind=stage.kind,
            position=stage.position,
            wip_limit=self.limits.get(stage.id),
        )

    def next_after(self, stage: ScenarioStage) -> ScenarioStage | None:
        following = [s for s in self.by_id.values() if s.position == stage.position + 1]
        return following[0] if following else None

    def work_stages(self) -> list[ScenarioStage]:
        stages = [s for s in self.by_id.values() if s.kind is StageKind.WORK]
        return sorted(stages, key=lambda s: s.position)


def build_layout(repo: GameRepository, game: GameSession) -> Layout:
    stages = repo.stages(game.scenario_id)
    overrides = repo.stage_limits(game.id)
    limits = {s.id: overrides.get(s.id, s.default_wip_limit) for s in stages}
    return Layout(
        by_id={s.id: s for s in stages}, by_code={s.code: s for s in stages}, limits=limits
    )


def log_move(
    repo: GameRepository,
    card: Card,
    day: int,
    target: ScenarioStage,
    state: CardColumnState | None,
    **fields: Any,
) -> None:
    """Append a movement; the database trigger updates the card, which is then reloaded."""
    values: dict[str, Any] = {
        "team_id": card.team_id,
        "card_id": card.id,
        "day": day,
        "from_stage_id": card.stage_id,
        "from_state": card.stage_state,
        "to_stage_id": target.id,
        "to_state": state,
        "request_id": uuid.uuid4(),
    } | fields
    repo.add_movement(**values)
    repo.refresh(card)
