"""Use cases of a running Startup Flow game: start, next day, dice, points, moves, results."""

import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agilesim.core.constants import (
    BLOCK_RELEASE_POINTS,
    DAY_ONE_PULL,
    DICE_MAX,
    DICE_MIN,
    FIRST_ROUND_LAST_DAY,
    GAME_DAYS,
    HELP_DIVISOR,
    ROLE_FACILITATOR,
    ROLE_PARTICIPANT,
    STAGE_ANALYSIS,
    STAGE_BACKLOG,
    STAGE_DEVELOPMENT,
)
from agilesim.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RuleViolationError,
)
from agilesim.db.enums import CardColumnState, SessionStatus, StageKind
from agilesim.db.models import (
    Card,
    GameSession,
    Participant,
    PointSpend,
    ScenarioCard,
    ScenarioStage,
    Team,
)
from agilesim.repositories.game import GameRepository
from agilesim.repositories.sessions import (
    ParticipantRepository,
    SessionRepository,
    TeamRepository,
)
from agilesim.rules.startup_flow import check_move, check_spend
from agilesim.schemas.game import (
    BoardOut,
    CardFlowOut,
    CardOut,
    DiceOut,
    DiceRequest,
    MoveOut,
    MoveRequest,
    SpendOut,
    SpendRequest,
    TeamResultOut,
    WipCounter,
)
from agilesim.services.board import Layout, build_layout, log_move
from agilesim.services.events import propose_events

RollDie = Callable[[], int]


def default_roll_die() -> int:
    """A fair die; ``secrets`` so that a player cannot predict the next value."""
    return secrets.randbelow(DICE_MAX - DICE_MIN + 1) + DICE_MIN


@dataclass(slots=True)
class PlayContext:
    team: Team
    game: GameSession
    participant: Participant
    layout: Layout


class GameService:
    def __init__(self, session: Session, roll_die: RollDie = default_roll_die) -> None:
        self._session = session
        self._roll_die = roll_die
        self._repo = GameRepository(session)
        self._games = SessionRepository(session)
        self._teams = TeamRepository(session)
        self._participants = ParticipantRepository(session)

    # ------------------------------------------------------------------ facilitator: day control

    def start(self, session_id: uuid.UUID, facilitator_id: uuid.UUID) -> GameSession:
        """Deal the cards to every team, pull the first five (day 1) and open the game."""
        # Locked: a second start waits here and then sees that the game is running.
        game = self._owned_game(session_id, facilitator_id, lock=True)
        if game.status is not SessionStatus.LOBBY:
            raise ConflictError("The game has already started")
        teams = self._teams.list_for_session(game.id)
        if not teams:
            raise RuleViolationError("Add at least one team before starting")
        layout = self._layout(game)
        playable = self._repo.playable_scenario_cards(game.scenario_id)
        if len(playable) < DAY_ONE_PULL:
            raise RuleViolationError(f"The scenario needs at least {DAY_ONE_PULL} backlog cards")
        work = self._repo.scenario_work(game.scenario_id)
        backlog = layout.by_code[STAGE_BACKLOG]
        analysis = layout.by_code[STAGE_ANALYSIS]

        for team in teams:
            self._repo.add_cards(team.id, playable, work, backlog.id)
            rows = self._repo.cards_with_scenario(team.id)
            best_first = sorted(rows, key=lambda row: (-row[1].value, row[1].number))
            for card, _ in best_first[:DAY_ONE_PULL]:
                self._log_move(card, 1, analysis, CardColumnState.IN_PROGRESS)

        game.status = SessionStatus.RUNNING
        game.current_day = 1
        game.started_at = datetime.now(UTC)
        propose_events(self._session, game, game.current_day)
        self._session.commit()
        return game

    def next_day(self, session_id: uuid.UUID, facilitator_id: uuid.UUID) -> GameSession:
        """Close the day. From day 5 the WIP limits apply; after the last day the game ends."""
        # Locked: concurrent calls see each other's day instead of proposing the same events
        # twice (unique key violation) or overwriting the day.
        game = self._owned_game(session_id, facilitator_id, lock=True)
        if game.status is not SessionStatus.RUNNING:
            raise ConflictError("The game is not running")
        if game.current_day >= GAME_DAYS:
            game.status = SessionStatus.FINISHED
            game.finished_at = datetime.now(UTC)
        else:
            game.current_day += 1
            if game.current_day > FIRST_ROUND_LAST_DAY:
                game.wip_limits_enabled = True
            propose_events(self._session, game, game.current_day)
        self._session.commit()
        return game

    # ------------------------------------------------------------------ reading

    def board(self, team_id: uuid.UUID, caller_id: uuid.UUID, role: str) -> BoardOut:
        team, game = self._team_and_game(team_id)
        self._authorize_view(team, game, caller_id, role)
        layout = self._layout(game)
        cards = [
            self._card_out(card, scenario_card, layout)
            for card, scenario_card in self._repo.cards_with_scenario(team.id)
        ]
        wip = [
            WipCounter(
                stage=stage.code,
                count=self._repo.count_in_stage(team.id, stage.id),
                limit=layout.limits.get(stage.id),
            )
            for stage in layout.work_stages()
        ]
        dice = self._dice_today(team, game, layout)
        return BoardOut(
            team_id=team.id,
            day=game.current_day,
            wip_limits_enabled=game.wip_limits_enabled,
            cards=cards,
            wip=wip,
            dice=dice,
        )

    def results(self, session_id: uuid.UUID, facilitator_id: uuid.UUID) -> list[TeamResultOut]:
        game = self._owned_game(session_id, facilitator_id)
        return [TeamResultOut(**row) for row in self._repo.team_results(game.id)]

    def flow(self, team_id: uuid.UUID, caller_id: uuid.UUID, role: str) -> list[CardFlowOut]:
        team, game = self._team_and_game(team_id)
        self._authorize_view(team, game, caller_id, role)
        return [CardFlowOut(**row) for row in self._repo.card_flow(team.id)]

    # ------------------------------------------------------------------ players: dice

    def roll(self, team_id: uuid.UUID, caller_id: uuid.UUID, body: DiceRequest) -> DiceOut:
        ctx = self._play_context(team_id, caller_id)
        stage = ctx.layout.by_code[body.stage]
        day = ctx.game.current_day
        if self._repo.get_roll(ctx.team.id, stage.id, day) is not None:
            raise ConflictError(f"The {stage.name} die was already rolled today")
        value = self._roll_die()
        try:
            self._repo.add_roll(
                team_id=ctx.team.id,
                stage_id=stage.id,
                day=day,
                value=value,
                rolled_by=ctx.participant.id,
                request_id=uuid.uuid4(),
            )
            self._session.commit()
        except IntegrityError as exc:  # two players rolled at the same moment
            self._session.rollback()
            raise ConflictError(f"The {stage.name} die was already rolled today") from exc
        return DiceOut(stage=stage.code, day=day, value=value, points_left=value)

    # ------------------------------------------------------------------ players: points

    def spend(self, team_id: uuid.UUID, caller_id: uuid.UUID, body: SpendRequest) -> SpendOut:
        ctx = self._play_context(team_id, caller_id)
        previous = self._repo.find_spend(ctx.team.id, body.request_id)
        if previous is not None:
            return self._replayed_spend(ctx, previous)

        found = self._repo.get_card(ctx.team.id, body.card_id, lock=True)
        if found is None:
            raise NotFoundError("Card not found in this team")
        card, _ = found
        target = ctx.layout.by_id[card.stage_id]
        if target.kind is not StageKind.WORK:
            raise RuleViolationError("Points can only be spent on a card in a work stage")
        source = ctx.layout.by_code[body.source_stage]
        day = ctx.game.current_day
        self._repo.lock_team(ctx.team.id)
        roll = self._repo.get_roll(ctx.team.id, source.id, day)
        if roll is None:
            raise RuleViolationError(f"Roll the {source.name} die first")
        points_left = roll.value - self._repo.points_spent(ctx.team.id, source.id, day)
        if card.is_blocked:
            return self._spend_on_block(ctx, found, source, target, body, points_left)
        squares = self._repo.squares_left(card.id)
        left_here = squares.get(target.id, 0)

        crossed = check_spend(
            points=body.points,
            points_left=points_left,
            same_stage=source.id == target.id,
            squares_left=left_here,
            blocked=card.is_blocked,
            target_name=target.name,
        )
        try:
            self._repo.add_spend(
                team_id=ctx.team.id,
                card_id=card.id,
                day=day,
                source_stage_id=source.id,
                target_stage_id=target.id,
                points_spent=body.points,
                squares_crossed=crossed,
                actor_participant_id=ctx.participant.id,
                request_id=body.request_id,
            )
            self._repo.set_squares_left(card.id, target.id, left_here - crossed)
            if left_here - crossed == 0:
                self._log_move(card, day, target, CardColumnState.READY)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("This request could not be saved, please try again") from exc
        lost = 0 if source.id == target.id else body.points - crossed * HELP_DIVISOR
        return SpendOut(
            card=self._card_out(card, found[1], ctx.layout),
            points_spent=body.points,
            squares_crossed=crossed,
            points_lost_to_rounding=lost,
            points_left=points_left - body.points,
        )

    # ------------------------------------------------------------------ players: moves

    def move(
        self, team_id: uuid.UUID, card_id: uuid.UUID, caller_id: uuid.UUID, body: MoveRequest
    ) -> MoveOut:
        ctx = self._play_context(team_id, caller_id)
        previous = self._repo.find_movement(ctx.team.id, body.request_id)
        if previous is not None:
            found = self._repo.get_card(ctx.team.id, previous.card_id)
            if found is None:  # cannot happen: movements reference existing cards
                raise NotFoundError("Card not found in this team")
            return MoveOut(card=self._card_out(found[0], found[1], ctx.layout), replayed=True)

        found = self._repo.get_card(ctx.team.id, card_id, lock=True)
        if found is None:
            raise NotFoundError("Card not found in this team")
        card, scenario_card = found
        current = ctx.layout.by_id[card.stage_id]
        target = ctx.layout.by_code[body.to_stage]
        if card.is_blocked:
            raise RuleViolationError("Card blocked")
        # Two players moving different cards into the same column must not both pass the WIP
        # check: the team lock makes their counts and inserts run one after the other.
        self._repo.lock_team(ctx.team.id)
        squares = self._repo.squares_left(card.id)
        next_stage = ctx.layout.next_after(current)
        check_move(
            current=ctx.layout.info(current),
            target=ctx.layout.info(target),
            work_left_in_current=squares.get(current.id, 0),
            wip_enabled=ctx.game.wip_limits_enabled,
            cards_in_target=self._repo.count_in_stage(ctx.team.id, target.id),
            is_emergency=scenario_card.is_emergency,
            next_stage_name=next_stage.name if next_stage else None,
        )
        state = None
        if target.kind is StageKind.WORK:
            nothing_to_do = squares.get(target.id, 0) == 0
            state = CardColumnState.READY if nothing_to_do else CardColumnState.IN_PROGRESS
        try:
            self._log_move(
                card,
                ctx.game.current_day,
                target,
                state,
                actor_participant_id=ctx.participant.id,
                request_id=body.request_id,
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("The card was moved by someone else, reload the board") from exc
        return MoveOut(card=self._card_out(card, scenario_card, ctx.layout), replayed=False)

    # ------------------------------------------------------------------ helpers

    def _owned_game(
        self, session_id: uuid.UUID, facilitator_id: uuid.UUID, *, lock: bool = False
    ) -> GameSession:
        game = self._games.get_for_update(session_id) if lock else self._games.get(session_id)
        if game is None:
            raise NotFoundError("Session not found")
        if game.facilitator_id != facilitator_id:
            raise ForbiddenError("This session belongs to another facilitator")
        return game

    def _team_and_game(self, team_id: uuid.UUID) -> tuple[Team, GameSession]:
        team = self._teams.get(team_id)
        game = self._games.get(team.session_id) if team else None
        if team is None or game is None:
            raise NotFoundError("Team not found")
        return team, game

    def _authorize_view(
        self, team: Team, game: GameSession, caller_id: uuid.UUID, role: str
    ) -> None:
        if role == ROLE_FACILITATOR:
            if game.facilitator_id != caller_id:
                raise ForbiddenError("This session belongs to another facilitator")
            return
        participant = self._participants.get(caller_id) if role == ROLE_PARTICIPANT else None
        if participant is None or participant.team_id != team.id:
            raise ForbiddenError("You are not a player of this team")

    def _play_context(self, team_id: uuid.UUID, caller_id: uuid.UUID) -> PlayContext:
        team, game = self._team_and_game(team_id)
        participant = self._participants.get(caller_id)
        if participant is None or participant.team_id != team.id:
            raise ForbiddenError("You are not a player of this team")
        if game.status is not SessionStatus.RUNNING:
            raise ConflictError("The game is not running")
        return PlayContext(team=team, game=game, participant=participant, layout=self._layout(game))

    def _layout(self, game: GameSession) -> Layout:
        return build_layout(self._repo, game)

    def _log_move(
        self,
        card: Card,
        day: int,
        target: ScenarioStage,
        state: CardColumnState | None,
        **fields: Any,
    ) -> None:
        log_move(self._repo, card, day, target, state, **fields)

    def _card_out(self, card: Card, scenario_card: ScenarioCard, layout: Layout) -> CardOut:
        squares = self._repo.squares_left(card.id)
        return CardOut(
            id=card.id,
            number=scenario_card.number,
            title=scenario_card.title,
            value=float(scenario_card.value),
            is_emergency=scenario_card.is_emergency,
            stage=layout.by_id[card.stage_id].code,
            state=card.stage_state,
            is_blocked=card.is_blocked,
            squares_left={layout.by_id[stage_id].code: left for stage_id, left in squares.items()},
        )

    def _dice_today(self, team: Team, game: GameSession, layout: Layout) -> list[DiceOut]:
        dice: list[DiceOut] = []
        for stage in layout.work_stages():
            roll = self._repo.get_roll(team.id, stage.id, game.current_day)
            if roll is None:
                continue
            spent = self._repo.points_spent(team.id, stage.id, game.current_day)
            dice.append(
                DiceOut(
                    stage=stage.code,
                    day=roll.day,
                    value=roll.value,
                    points_left=roll.value - spent,
                )
            )
        return dice

    def _spend_on_block(
        self,
        ctx: PlayContext,
        found: tuple[Card, ScenarioCard],
        source: ScenarioStage,
        target: ScenarioStage,
        body: SpendRequest,
        points_left: int,
    ) -> SpendOut:
        """Points on a BLOCKED card only remove the block (3 full Development points)."""
        card, scenario_card = found
        if source.code != STAGE_DEVELOPMENT or target.code != STAGE_DEVELOPMENT:
            raise RuleViolationError("Card blocked: only Development points can unblock it")
        if body.points > points_left:
            noun = "point" if points_left == 1 else "points"
            raise RuleViolationError(f"Only {points_left} {noun} left")
        done = self._repo.unblock_progress(card.id, target.id, card.updated_at)
        needed = BLOCK_RELEASE_POINTS - done
        if body.points > needed:
            noun = "point is" if needed == 1 else "points are"
            raise RuleViolationError(f"Only {needed} more {noun} needed to unblock the card")
        try:
            # The log row says "points spent in Development"; no square is crossed out, the
            # points went to the block, which is why the response reports zero squares.
            self._repo.add_spend(
                team_id=ctx.team.id,
                card_id=card.id,
                day=ctx.game.current_day,
                source_stage_id=source.id,
                target_stage_id=target.id,
                points_spent=body.points,
                squares_crossed=body.points,
                actor_participant_id=ctx.participant.id,
                request_id=body.request_id,
            )
            if body.points == needed:
                card.is_blocked = False
                self._session.flush()
                self._repo.refresh(card)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("This request could not be saved, please try again") from exc
        return SpendOut(
            card=self._card_out(card, scenario_card, ctx.layout),
            points_spent=body.points,
            squares_crossed=0,
            points_lost_to_rounding=0,
            points_left=points_left - body.points,
        )

    def _replayed_spend(self, ctx: PlayContext, spend: PointSpend) -> SpendOut:
        found = self._repo.get_card(ctx.team.id, spend.card_id)
        if found is None:
            raise NotFoundError("Card not found in this team")
        roll = self._repo.get_roll(ctx.team.id, spend.source_stage_id, spend.day)
        left = (
            roll.value - self._repo.points_spent(ctx.team.id, spend.source_stage_id, spend.day)
            if roll
            else 0
        )
        same = spend.source_stage_id == spend.target_stage_id
        return SpendOut(
            card=self._card_out(found[0], found[1], ctx.layout),
            points_spent=spend.points_spent,
            squares_crossed=spend.squares_crossed,
            points_lost_to_rounding=0
            if same
            else spend.points_spent - spend.squares_crossed * HELP_DIVISOR,
            points_left=left,
            replayed=True,
        )
