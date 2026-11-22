"""Data access for the game state: cards, work squares, logs, WIP limits and metrics."""

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from agilesim.db.models import (
    Card,
    CardMovement,
    CardWork,
    DiceRoll,
    PointSpend,
    ScenarioCard,
    ScenarioCardWork,
    ScenarioStage,
    SessionStageLimit,
    Team,
)


class GameRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ catalogue

    def stages(self, scenario_id: uuid.UUID) -> list[ScenarioStage]:
        return list(
            self._session.scalars(
                sa.select(ScenarioStage)
                .where(ScenarioStage.scenario_id == scenario_id)
                .order_by(ScenarioStage.position)
            )
        )

    def playable_scenario_cards(self, scenario_id: uuid.UUID) -> list[ScenarioCard]:
        """Backlog cards of the scenario, most valuable first (not the emergency card)."""
        return list(
            self._session.scalars(
                sa.select(ScenarioCard)
                .where(
                    ScenarioCard.scenario_id == scenario_id, ScenarioCard.is_emergency.is_(False)
                )
                .order_by(ScenarioCard.value.desc(), ScenarioCard.number)
            )
        )

    def scenario_work(self, scenario_id: uuid.UUID) -> list[ScenarioCardWork]:
        return list(
            self._session.scalars(
                sa.select(ScenarioCardWork).where(ScenarioCardWork.scenario_id == scenario_id)
            )
        )

    # ------------------------------------------------------------------ cards

    def add_cards(
        self,
        team_id: uuid.UUID,
        scenario_cards: list[ScenarioCard],
        work: list[ScenarioCardWork],
        backlog_stage_id: uuid.UUID,
    ) -> None:
        """Give a team its own copy of every card, waiting in the backlog."""
        work_by_card: dict[uuid.UUID, list[ScenarioCardWork]] = {}
        for item in work:
            work_by_card.setdefault(item.scenario_card_id, []).append(item)
        for scenario_card in scenario_cards:
            card = Card(
                team_id=team_id, scenario_card_id=scenario_card.id, stage_id=backlog_stage_id
            )
            self._session.add(card)
            self._session.flush()
            for item in work_by_card.get(scenario_card.id, []):
                self._session.add(
                    CardWork(card_id=card.id, stage_id=item.stage_id, squares_left=item.squares)
                )
        self._session.flush()

    def team_has_cards(self, team_id: uuid.UUID) -> bool:
        return (
            self._session.scalars(sa.select(Card.id).where(Card.team_id == team_id)).first()
            is not None
        )

    def cards_with_scenario(self, team_id: uuid.UUID) -> list[tuple[Card, ScenarioCard]]:
        rows = self._session.execute(
            sa.select(Card, ScenarioCard)
            .join(ScenarioCard, ScenarioCard.id == Card.scenario_card_id)
            .where(Card.team_id == team_id)
            .order_by(ScenarioCard.number)
        )
        return [(card, scenario_card) for card, scenario_card in rows]

    def get_card(
        self, team_id: uuid.UUID, card_id: uuid.UUID, *, lock: bool = False
    ) -> tuple[Card, ScenarioCard] | None:
        """One card with its scenario data; ``lock`` holds the card row until the commit."""
        query = (
            sa.select(Card, ScenarioCard)
            .join(ScenarioCard, ScenarioCard.id == Card.scenario_card_id)
            .where(Card.team_id == team_id, Card.id == card_id)
        )
        if lock:
            query = query.with_for_update(of=Card)
        row = self._session.execute(query).first()
        return (row[0], row[1]) if row else None

    def squares_left(self, card_id: uuid.UUID) -> dict[uuid.UUID, int]:
        rows = self._session.execute(
            sa.select(CardWork.stage_id, CardWork.squares_left).where(CardWork.card_id == card_id)
        )
        return dict(rows.tuples().all())

    def set_squares_left(self, card_id: uuid.UUID, stage_id: uuid.UUID, value: int) -> None:
        work = self._session.get(CardWork, (card_id, stage_id))
        if work is not None:
            work.squares_left = value
            self._session.flush()

    def count_in_stage(self, team_id: uuid.UUID, stage_id: uuid.UUID) -> int:
        """Cards in a column that count against its WIP limit (the emergency card does not)."""
        return int(
            self._session.scalar(
                sa.select(sa.func.count())
                .select_from(Card)
                .join(ScenarioCard, ScenarioCard.id == Card.scenario_card_id)
                .where(
                    Card.team_id == team_id,
                    Card.stage_id == stage_id,
                    ScenarioCard.is_emergency.is_(False),
                )
            )
            or 0
        )

    def refresh(self, card: Card) -> None:
        """Reload a card after the database trigger moved it."""
        self._session.refresh(card)

    # ------------------------------------------------------------------ logs

    def find_movement(self, team_id: uuid.UUID, request_id: uuid.UUID) -> CardMovement | None:
        return self._session.scalars(
            sa.select(CardMovement).where(
                CardMovement.team_id == team_id, CardMovement.request_id == request_id
            )
        ).one_or_none()

    def add_movement(self, **fields: Any) -> CardMovement:
        movement = CardMovement(**fields)
        self._session.add(movement)
        self._session.flush()
        return movement

    def get_roll(self, team_id: uuid.UUID, stage_id: uuid.UUID, day: int) -> DiceRoll | None:
        return self._session.scalars(
            sa.select(DiceRoll).where(
                DiceRoll.team_id == team_id, DiceRoll.stage_id == stage_id, DiceRoll.day == day
            )
        ).one_or_none()

    def lock_team(self, team_id: uuid.UUID) -> None:
        """Hold the team row until the commit, so a team's spends from one die run one by one.

        The roll itself cannot be locked: ``dice_rolls`` is an append-only log and the
        application role has no UPDATE right on it, which ``SELECT ... FOR UPDATE`` needs.
        """
        self._session.execute(
            sa.select(Team.id).where(Team.id == team_id).with_for_update(key_share=True)
        )

    def add_roll(self, **fields: Any) -> DiceRoll:
        roll = DiceRoll(**fields)
        self._session.add(roll)
        self._session.flush()
        return roll

    def points_spent(self, team_id: uuid.UUID, stage_id: uuid.UUID, day: int) -> int:
        return int(
            self._session.scalar(
                sa.select(sa.func.coalesce(sa.func.sum(PointSpend.points_spent), 0)).where(
                    PointSpend.team_id == team_id,
                    PointSpend.source_stage_id == stage_id,
                    PointSpend.day == day,
                )
            )
            or 0
        )

    def find_spend(self, team_id: uuid.UUID, request_id: uuid.UUID) -> PointSpend | None:
        return self._session.scalars(
            sa.select(PointSpend).where(
                PointSpend.team_id == team_id, PointSpend.request_id == request_id
            )
        ).one_or_none()

    def add_spend(self, **fields: Any) -> PointSpend:
        # The database clock, like the trigger that stamps cards.updated_at: unblocking progress
        # compares the two, so both must come from the same clock (and not from now(), which is
        # frozen for the whole transaction).
        spend = PointSpend(occurred_at=sa.func.clock_timestamp(), **fields)
        self._session.add(spend)
        self._session.flush()
        return spend

    # ------------------------------------------------------------------ session settings

    def stage_limits(self, session_id: uuid.UUID) -> dict[uuid.UUID, int]:
        rows = self._session.execute(
            sa.select(SessionStageLimit.stage_id, SessionStageLimit.wip_limit).where(
                SessionStageLimit.session_id == session_id
            )
        )
        return dict(rows.tuples().all())

    def set_stage_limit(self, session_id: uuid.UUID, stage_id: uuid.UUID, limit: int) -> None:
        existing = self._session.get(SessionStageLimit, (session_id, stage_id))
        if existing is None:
            self._session.add(
                SessionStageLimit(session_id=session_id, stage_id=stage_id, wip_limit=limit)
            )
        else:
            existing.wip_limit = limit
        self._session.flush()

    # ------------------------------------------------------------------ metrics (views)

    def team_results(self, session_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = self._session.execute(
            sa.text(
                "SELECT team_id, team_name, done_cards, money_earned, "
                "avg_lead_time_days, money_rank "
                "FROM team_results WHERE session_id = :session_id ORDER BY money_rank, team_name"
            ),
            {"session_id": session_id},
        )
        return [dict(row._mapping) for row in rows]

    def card_flow(self, team_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = self._session.execute(
            sa.text(
                "SELECT card_number, title, value, pulled_day, done_day, lead_time_days "
                "FROM card_flow WHERE team_id = :team_id ORDER BY card_number"
            ),
            {"team_id": team_id},
        )
        return [dict(row._mapping) for row in rows]

    # ------------------------------------------------------------------ events and blocks

    def backlog_cards(
        self, team_id: uuid.UUID, backlog_stage_id: uuid.UUID
    ) -> list[tuple[Card, ScenarioCard]]:
        """The team's cards still in the backlog, most valuable first (no emergency card)."""
        rows = self._session.execute(
            sa.select(Card, ScenarioCard)
            .join(ScenarioCard, ScenarioCard.id == Card.scenario_card_id)
            .where(
                Card.team_id == team_id,
                Card.stage_id == backlog_stage_id,
                ScenarioCard.is_emergency.is_(False),
            )
            .order_by(ScenarioCard.value.desc(), ScenarioCard.number)
        )
        return [(card, scenario_card) for card, scenario_card in rows]

    def top_card_in_stage(self, team_id: uuid.UUID, stage_id: uuid.UUID) -> Card | None:
        """The most valuable card of a column that is not blocked yet."""
        return self._session.scalars(
            sa.select(Card)
            .join(ScenarioCard, ScenarioCard.id == Card.scenario_card_id)
            .where(Card.team_id == team_id, Card.stage_id == stage_id, Card.is_blocked.is_(False))
            .order_by(ScenarioCard.value.desc(), ScenarioCard.number)
            .limit(1)
        ).one_or_none()

    def emergency_scenario_card(self, scenario_id: uuid.UUID) -> ScenarioCard | None:
        return self._session.scalars(
            sa.select(ScenarioCard)
            .where(ScenarioCard.scenario_id == scenario_id, ScenarioCard.is_emergency.is_(True))
            .limit(1)
        ).one_or_none()

    def unblock_progress(self, card_id: uuid.UUID, stage_id: uuid.UUID, since: Any) -> int:
        """Development points spent on a blocked card since it was blocked."""
        return int(
            self._session.scalar(
                sa.select(sa.func.coalesce(sa.func.sum(PointSpend.points_spent), 0)).where(
                    PointSpend.card_id == card_id,
                    PointSpend.source_stage_id == stage_id,
                    PointSpend.target_stage_id == stage_id,
                    PointSpend.occurred_at >= since,
                )
            )
            or 0
        )
