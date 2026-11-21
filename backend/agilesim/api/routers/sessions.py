"""Sessions, teams and joining: the lobby part of the game."""

import uuid

from fastapi import APIRouter, status

from agilesim.api.deps import (
    CurrentFacilitator,
    CurrentPrincipal,
    SessionServiceDep,
)
from agilesim.core.constants import ROLE_FACILITATOR
from agilesim.core.errors import ForbiddenError
from agilesim.schemas.sessions import (
    JoinRequest,
    JoinResponse,
    RejoinRequest,
    SessionCreate,
    SessionOut,
    TeamCreate,
    TeamOut,
)

router = APIRouter(tags=["sessions"])


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(
    body: SessionCreate, facilitator: CurrentFacilitator, service: SessionServiceDep
) -> SessionOut:
    """Create a Startup Flow session; the response carries the join code for the players."""
    return SessionOut.model_validate(service.create(facilitator.id, body.name))


@router.get("/sessions")
def list_sessions(facilitator: CurrentFacilitator, service: SessionServiceDep) -> list[SessionOut]:
    """The sessions of the calling facilitator, newest first."""
    return [SessionOut.model_validate(g) for g in service.list_for_facilitator(facilitator.id)]


@router.get("/sessions/{session_id}")
def get_session(
    session_id: uuid.UUID, caller: CurrentPrincipal, service: SessionServiceDep
) -> SessionOut:
    """One session; visible to its facilitator and to its players."""
    if caller.role == ROLE_FACILITATOR:
        return SessionOut.model_validate(service.owned(session_id, caller.id))
    if service.participant_session_id(caller.id) != session_id:
        raise ForbiddenError("You are not a player of this session")
    return SessionOut.model_validate(service.get(session_id))


@router.post("/sessions/{session_id}/teams", status_code=status.HTTP_201_CREATED)
def create_team(
    session_id: uuid.UUID,
    body: TeamCreate,
    facilitator: CurrentFacilitator,
    service: SessionServiceDep,
) -> TeamOut:
    """Add a team to a session."""
    return TeamOut.model_validate(service.add_team(session_id, facilitator.id, body.name))


@router.get("/sessions/{session_id}/teams")
def list_teams(
    session_id: uuid.UUID, caller: CurrentPrincipal, service: SessionServiceDep
) -> list[TeamOut]:
    """Teams of a session; visible to its facilitator and to its players."""
    if caller.role == ROLE_FACILITATOR:
        service.owned(session_id, caller.id)
    elif service.participant_session_id(caller.id) != session_id:
        raise ForbiddenError("You are not a player of this session")
    return [TeamOut.model_validate(t) for t in service.list_teams(session_id)]


@router.get("/join/{join_code}/teams")
def teams_by_join_code(join_code: str, service: SessionServiceDep) -> list[TeamOut]:
    """Teams a player can choose from before joining (public, needs only the join code)."""
    return [TeamOut.model_validate(t) for t in service.teams_by_join_code(join_code)]


@router.post("/join", status_code=status.HTTP_201_CREATED)
def join(body: JoinRequest, service: SessionServiceDep) -> JoinResponse:
    """Join a session with its code; returns an access token and a rejoin token."""
    return service.join(body)


@router.post("/rejoin")
def rejoin(body: RejoinRequest, service: SessionServiceDep) -> JoinResponse:
    """Get a new access token with the rejoin token, for example after a page reload."""
    return service.rejoin(body.rejoin_token)
