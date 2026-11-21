"""Scenario events: proposed on their day, applied by the facilitator, with their effect."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from agilesim.core.constants import (
    ROLE_FACILITATOR,
    STAGE_ANALYSIS,
    STAGE_BACKLOG,
    STAGE_DEVELOPMENT,
)
from agilesim.core.errors import ConflictError, ForbiddenError, NotFoundError, RuleViolationError
from agilesim.db.enums import (
    CardColumnState,
    EventEffect,
    EventSource,
    EventStatus,
    SessionStatus,
)
from agilesim.db.models import GameEvent, GameSession, ScenarioEvent
from agilesim.repositories.events import EventRepository
from agilesim.repositories.game import GameRepository
from agilesim.repositories.sessions import (
    ParticipantRepository,
    SessionRepository,
    TeamRepository,
)
from agilesim.schemas.game import EventCreate, EventOut
from agilesim.services.board import Layout, build_layout, log_move


def propose_events(session: Session, game: GameSession, day: int) -> None:
    """Put the scenario's events of ``day`` on the session's list, waiting for the facilitator."""
    repo = EventRepository(session)
    for template in repo.scenario_events_for_day(game.scenario_id, day):
        if repo.has_scenario_event(game.id, template.id):
            continue
        repo.add(
            session_id=game.id,
            scenario_event_id=template.id,
            day=day,
            title=template.title,
            description=template.description,
            source=EventSource.TEMPLATE,
            status=EventStatus.PROPOSED,
        )


class EventService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._events = EventRepository(session)
        self._repo = GameRepository(session)
        self._games = SessionRepository(session)
        self._teams = TeamRepository(session)
        self._participants = ParticipantRepository(session)

    # ------------------------------------------------------------------ reading

    def list_events(self, session_id: uuid.UUID, caller_id: uuid.UUID, role: str) -> list[EventOut]:
        game = self._game(session_id)
        if role == ROLE_FACILITATOR:
            self._require_owner(game, caller_id)
        else:
            participant = self._participants.get(caller_id)
            if participant is None or participant.session_id != game.id:
                raise ForbiddenError("You are not a player of this session")
        return [
            self._out(event, template) for event, template in self._events.list_for_session(game.id)
        ]

    # ------------------------------------------------------------------ facilitator actions

    def create_manual(
        self, session_id: uuid.UUID, facilitator_id: uuid.UUID, body: EventCreate
    ) -> EventOut:
        """An event the facilitator invents on the spot; it has no mechanical effect."""
        game = self._owned_running(session_id, facilitator_id)
        event = self._events.add(
            session_id=game.id,
            scenario_event_id=None,
            day=game.current_day,
            title=body.title,
            description=body.description,
            source=EventSource.MANUAL,
            status=EventStatus.PROPOSED,
        )
        self._session.commit()
        return self._out(event, None)

    def apply(
        self, session_id: uuid.UUID, event_id: uuid.UUID, facilitator_id: uuid.UUID
    ) -> EventOut:
        game = self._owned_running(session_id, facilitator_id)
        event, template = self._pending_event(game, event_id)
        if template is not None:
            self._run_effect(game, template)
        now = datetime.now(UTC)
        event.status = EventStatus.APPLIED
        event.confirmed_by = facilitator_id
        event.confirmed_at = now
        event.applied_at = now
        self._session.commit()
        return self._out(event, template)

    def dismiss(
        self, session_id: uuid.UUID, event_id: uuid.UUID, facilitator_id: uuid.UUID
    ) -> EventOut:
        game = self._owned_running(session_id, facilitator_id)
        event, template = self._pending_event(game, event_id)
        event.status = EventStatus.DISMISSED
        self._session.commit()
        return self._out(event, template)

    # ------------------------------------------------------------------ effects

    def _run_effect(self, game: GameSession, template: ScenarioEvent) -> None:
        layout = build_layout(self._repo, game)
        match template.effect:
            case EventEffect.PULL_CARDS:
                self._pull_cards(game, layout, template.effect_amount or 0)
            case EventEffect.BLOCK_TOP_CARD:
                self._block_top_card(game, layout)
            case EventEffect.EMERGENCY_CARD:
                self._add_emergency_card(game, layout)
            case _:
                # NONE and DEV_ROLL_BONUS only inform the players; the facilitator and the team
                # handle them at the table (the refactoring bonus is not enforced by the system).
                return

    def _pull_cards(self, game: GameSession, layout: Layout, amount: int) -> None:
        """Every team pulls its ``amount`` most valuable backlog cards, whatever the WIP limit."""
        backlog = layout.by_code[STAGE_BACKLOG]
        analysis = layout.by_code[STAGE_ANALYSIS]
        for team in self._teams.list_for_session(game.id):
            for card, _ in self._repo.backlog_cards(team.id, backlog.id)[:amount]:
                log_move(self._repo, card, game.current_day, analysis, CardColumnState.IN_PROGRESS)

    def _block_top_card(self, game: GameSession, layout: Layout) -> None:
        """The most valuable card in Development of every team gets BLOCKED."""
        development = layout.by_code[STAGE_DEVELOPMENT]
        for team in self._teams.list_for_session(game.id):
            card = self._repo.top_card_in_stage(team.id, development.id)
            if card is not None:
                card.is_blocked = True
                self._session.flush()
                self._repo.refresh(card)  # reads updated_at, the moment the block started

    def _add_emergency_card(self, game: GameSession, layout: Layout) -> None:
        """Every team gets the $0 emergency card in Analysis, outside the WIP limits."""
        emergency = self._repo.emergency_scenario_card(game.scenario_id)
        if emergency is None:
            raise RuleViolationError("The scenario has no emergency card")
        work = [
            item
            for item in self._repo.scenario_work(game.scenario_id)
            if item.scenario_card_id == emergency.id
        ]
        backlog = layout.by_code[STAGE_BACKLOG]
        analysis = layout.by_code[STAGE_ANALYSIS]
        for team in self._teams.list_for_session(game.id):
            self._repo.add_cards(team.id, [emergency], work, backlog.id)
            card = next(
                c for c, sc in self._repo.cards_with_scenario(team.id) if sc.id == emergency.id
            )
            log_move(self._repo, card, game.current_day, analysis, CardColumnState.IN_PROGRESS)

    # ------------------------------------------------------------------ helpers

    def _game(self, session_id: uuid.UUID) -> GameSession:
        game = self._games.get(session_id)
        if game is None:
            raise NotFoundError("Session not found")
        return game

    @staticmethod
    def _require_owner(game: GameSession, facilitator_id: uuid.UUID) -> None:
        if game.facilitator_id != facilitator_id:
            raise ForbiddenError("This session belongs to another facilitator")

    def _owned_running(self, session_id: uuid.UUID, facilitator_id: uuid.UUID) -> GameSession:
        game = self._game(session_id)
        self._require_owner(game, facilitator_id)
        if game.status is not SessionStatus.RUNNING:
            raise ConflictError("The game is not running")
        return game

    def _pending_event(
        self, game: GameSession, event_id: uuid.UUID
    ) -> tuple[GameEvent, ScenarioEvent | None]:
        found = self._events.get(game.id, event_id)
        if found is None:
            raise NotFoundError("Event not found")
        event, _ = found
        if event.status not in (EventStatus.PROPOSED, EventStatus.CONFIRMED):
            raise ConflictError(f"The event is already {event.status.value}")
        return found

    @staticmethod
    def _out(event: GameEvent, template: ScenarioEvent | None) -> EventOut:
        return EventOut(
            id=event.id,
            day=event.day,
            title=event.title,
            description=event.description,
            source=event.source,
            status=event.status,
            effect=template.effect if template else None,
            effect_amount=template.effect_amount if template else None,
            applied_at=event.applied_at,
        )
