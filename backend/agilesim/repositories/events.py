"""Data access for the events of a session."""

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from agilesim.db.models import GameEvent, ScenarioEvent


class EventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def scenario_events_for_day(self, scenario_id: uuid.UUID, day: int) -> list[ScenarioEvent]:
        return list(
            self._session.scalars(
                sa.select(ScenarioEvent)
                .where(ScenarioEvent.scenario_id == scenario_id, ScenarioEvent.day == day)
                .order_by(ScenarioEvent.code)
            )
        )

    def has_scenario_event(self, session_id: uuid.UUID, scenario_event_id: uuid.UUID) -> bool:
        return (
            self._session.scalars(
                sa.select(GameEvent.id).where(
                    GameEvent.session_id == session_id,
                    GameEvent.scenario_event_id == scenario_event_id,
                )
            ).first()
            is not None
        )

    def add(self, **fields: Any) -> GameEvent:
        event = GameEvent(**fields)
        self._session.add(event)
        self._session.flush()
        return event

    def list_for_session(
        self, session_id: uuid.UUID
    ) -> list[tuple[GameEvent, ScenarioEvent | None]]:
        rows = self._session.execute(
            sa.select(GameEvent, ScenarioEvent)
            .outerjoin(ScenarioEvent, ScenarioEvent.id == GameEvent.scenario_event_id)
            .where(GameEvent.session_id == session_id)
            .order_by(GameEvent.day, GameEvent.created_at, GameEvent.title)
        )
        return [(event, template) for event, template in rows]

    def get(
        self, session_id: uuid.UUID, event_id: uuid.UUID
    ) -> tuple[GameEvent, ScenarioEvent | None] | None:
        row = self._session.execute(
            sa.select(GameEvent, ScenarioEvent)
            .outerjoin(ScenarioEvent, ScenarioEvent.id == GameEvent.scenario_event_id)
            .where(GameEvent.session_id == session_id, GameEvent.id == event_id)
            .with_for_update(of=GameEvent)
        ).first()
        return (row[0], row[1]) if row else None
