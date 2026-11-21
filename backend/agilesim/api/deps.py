"""FastAPI dependencies: database session, services and the authenticated caller."""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from agilesim.config import Settings, get_settings
from agilesim.core.constants import ROLE_FACILITATOR, ROLE_PARTICIPANT
from agilesim.core.errors import ForbiddenError, UnauthorizedError
from agilesim.core.security import decode_access_token
from agilesim.db.session import get_session
from agilesim.services.auth import AuthService
from agilesim.services.events import EventService
from agilesim.services.game import GameService
from agilesim.services.sessions import SessionService

bearer_scheme = HTTPBearer(
    auto_error=False, description="Access token from /v1/auth/login or /v1/join"
)

DbSession = Annotated[Session, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True, slots=True)
class Principal:
    """Who is calling: the id of a facilitator or of a participant, and the role."""

    id: uuid.UUID
    role: str


def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: AppSettings,
) -> Principal:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")
    subject, role = decode_access_token(credentials.credentials, secret=settings.jwt_secret)
    return Principal(id=subject, role=role)


def require_facilitator(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
    if principal.role != ROLE_FACILITATOR:
        raise ForbiddenError("Only a facilitator can do this")
    return principal


def require_participant(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
    if principal.role != ROLE_PARTICIPANT:
        raise ForbiddenError("Only a player can do this")
    return principal


def get_auth_service(session: DbSession, settings: AppSettings) -> AuthService:
    return AuthService(session, settings)


def get_session_service(session: DbSession, settings: AppSettings) -> SessionService:
    return SessionService(session, settings)


def get_game_service(session: DbSession) -> GameService:
    return GameService(session)


def get_event_service(session: DbSession) -> EventService:
    return EventService(session)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
CurrentFacilitator = Annotated[Principal, Depends(require_facilitator)]
CurrentParticipant = Annotated[Principal, Depends(require_participant)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
GameServiceDep = Annotated[GameService, Depends(get_game_service)]
EventServiceDep = Annotated[EventService, Depends(get_event_service)]
