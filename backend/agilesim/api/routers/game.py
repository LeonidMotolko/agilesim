"""The game itself: day control, board, dice, points, moves and results."""

import uuid

from fastapi import APIRouter

from agilesim.api.deps import (
    CurrentFacilitator,
    CurrentParticipant,
    CurrentPrincipal,
    GameServiceDep,
)
from agilesim.schemas.game import (
    BoardOut,
    CardFlowOut,
    DiceOut,
    DiceRequest,
    MoveOut,
    MoveRequest,
    SpendOut,
    SpendRequest,
    TeamResultOut,
)
from agilesim.schemas.sessions import SessionOut

router = APIRouter(tags=["game"])


@router.post("/sessions/{session_id}/start")
def start_game(
    session_id: uuid.UUID, facilitator: CurrentFacilitator, service: GameServiceDep
) -> SessionOut:
    """Deal the cards, pull the five most valuable ones for every team and open day 1."""
    return SessionOut.model_validate(service.start(session_id, facilitator.id))


@router.post("/sessions/{session_id}/next-day")
def next_day(
    session_id: uuid.UUID, facilitator: CurrentFacilitator, service: GameServiceDep
) -> SessionOut:
    """Close the current day; closing the last day finishes the game."""
    return SessionOut.model_validate(service.next_day(session_id, facilitator.id))


@router.get("/sessions/{session_id}/results")
def session_results(
    session_id: uuid.UUID, facilitator: CurrentFacilitator, service: GameServiceDep
) -> list[TeamResultOut]:
    """Cards done, money earned, average Lead Time and rank of every team."""
    return service.results(session_id, facilitator.id)


@router.get("/teams/{team_id}/board")
def get_board(team_id: uuid.UUID, caller: CurrentPrincipal, service: GameServiceDep) -> BoardOut:
    """The board of a team: cards, WIP counters and today's dice."""
    return service.board(team_id, caller.id, caller.role)


@router.get("/teams/{team_id}/flow")
def get_flow(
    team_id: uuid.UUID, caller: CurrentPrincipal, service: GameServiceDep
) -> list[CardFlowOut]:
    """Pull day, Done day and Lead Time of every card of a team."""
    return service.flow(team_id, caller.id, caller.role)


@router.post("/teams/{team_id}/dice")
def roll_die(
    team_id: uuid.UUID, body: DiceRequest, player: CurrentParticipant, service: GameServiceDep
) -> DiceOut:
    """Roll the die of a stage; once per stage and day."""
    return service.roll(team_id, player.id, body)


@router.post("/teams/{team_id}/spend")
def spend_points(
    team_id: uuid.UUID, body: SpendRequest, player: CurrentParticipant, service: GameServiceDep
) -> SpendOut:
    """Spend die points on a card; help from another stage counts half, rounded down."""
    return service.spend(team_id, player.id, body)


@router.post("/teams/{team_id}/cards/{card_id}/move")
def move_card(
    team_id: uuid.UUID,
    card_id: uuid.UUID,
    body: MoveRequest,
    player: CurrentParticipant,
    service: GameServiceDep,
) -> MoveOut:
    """Move a card to the next stage; a repeated request id changes nothing."""
    return service.move(team_id, card_id, player.id, body)
