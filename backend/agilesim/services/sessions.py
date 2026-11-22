"""Use cases of game sessions: create, add teams, join as a player."""

import secrets
import string
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agilesim.config import Settings
from agilesim.core import security
from agilesim.core.constants import JOIN_CODE_LENGTH, ROLE_PARTICIPANT
from agilesim.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RuleViolationError,
)
from agilesim.db.enums import SessionStatus
from agilesim.db.models import GameSession, Participant, Team
from agilesim.repositories.sessions import (
    ParticipantRepository,
    SessionRepository,
    TeamRepository,
)
from agilesim.schemas.sessions import JoinRequest, JoinResponse, ParticipantOut

SCENARIO_CODE = "startup-flow"
JOIN_CODE_ALPHABET = string.ascii_uppercase + string.digits
JOIN_CODE_ATTEMPTS = 10


class SessionService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._games = SessionRepository(session)
        self._teams = TeamRepository(session)
        self._participants = ParticipantRepository(session)

    # ------------------------------------------------------------------ facilitator use cases

    def create(self, facilitator_id: uuid.UUID, name: str) -> GameSession:
        scenario = self._games.latest_scenario(SCENARIO_CODE)
        if scenario is None:
            msg = f"Scenario {SCENARIO_CODE!r} is not loaded"
            raise NotFoundError(msg)
        for _ in range(JOIN_CODE_ATTEMPTS):
            join_code = self.new_join_code()
            if self._games.join_code_exists(join_code):
                continue
            try:
                game = self._games.add(facilitator_id, scenario.id, name, join_code)
                self._session.commit()
            except IntegrityError:  # another request took the code between check and insert
                self._session.rollback()
                continue
            return game
        msg = "Could not generate a free join code"
        raise ConflictError(msg)

    def list_for_facilitator(self, facilitator_id: uuid.UUID) -> list[GameSession]:
        return self._games.list_for_facilitator(facilitator_id)

    def owned(self, session_id: uuid.UUID, facilitator_id: uuid.UUID) -> GameSession:
        """The session, provided that this facilitator runs it."""
        game = self.get(session_id)
        if game.facilitator_id != facilitator_id:
            raise ForbiddenError("This session belongs to another facilitator")
        return game

    def get(self, session_id: uuid.UUID) -> GameSession:
        game = self._games.get(session_id)
        if game is None:
            raise NotFoundError("Session not found")
        return game

    def add_team(self, session_id: uuid.UUID, facilitator_id: uuid.UUID, name: str) -> Team:
        game = self.owned(session_id, facilitator_id)
        if game.status is SessionStatus.FINISHED:
            raise ConflictError("The session is finished")
        if self._teams.name_exists(game.id, name):
            raise ConflictError("A team with this name already exists in the session")
        try:
            team = self._teams.add(game.id, name)
            self._session.commit()
        except IntegrityError as exc:  # the same name was added between check and insert
            self._session.rollback()
            raise ConflictError("A team with this name already exists in the session") from exc
        return team

    def list_teams(self, session_id: uuid.UUID) -> list[Team]:
        return self._teams.list_for_session(self.get(session_id).id)

    # ------------------------------------------------------------------ player use cases

    def join(self, request: JoinRequest) -> JoinResponse:
        if not request.consent:
            raise RuleViolationError("Consent to the processing of game data is required")
        game = self._games.get_by_join_code(request.join_code.upper())
        if game is None:
            raise NotFoundError("No session with this join code")
        if game.status is SessionStatus.FINISHED:
            raise ConflictError("The session is finished")
        if request.team_id is not None:
            team = self._teams.get(request.team_id)
            if team is None or team.session_id != game.id:
                raise NotFoundError("Team not found in this session")
        if self._participants.name_exists(game.id, request.display_name):
            raise ConflictError("This name is already taken in the session")

        token, token_hash = security.new_join_token()
        try:
            participant = self._participants.add(
                game.id, request.team_id, request.display_name, token_hash
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("This name is already taken in the session") from exc
        return self._join_response(participant, token)

    def rejoin(self, rejoin_token: str) -> JoinResponse:
        participant = self._participants.get_by_token_hash(security.hash_join_token(rejoin_token))
        if participant is None:
            raise NotFoundError("Unknown rejoin token")
        return self._join_response(participant, rejoin_token)

    def participant_session_id(self, participant_id: uuid.UUID) -> uuid.UUID | None:
        participant = self._participants.get(participant_id)
        return participant.session_id if participant else None

    def teams_by_join_code(self, join_code: str) -> list[Team]:
        game = self._games.get_by_join_code(join_code.upper())
        if game is None:
            raise NotFoundError("No session with this join code")
        return self._teams.list_for_session(game.id)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def new_join_code() -> str:
        return "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))

    def _join_response(self, participant: Participant, rejoin_token: str) -> JoinResponse:
        access_token = security.create_access_token(
            participant.id,
            ROLE_PARTICIPANT,
            secret=self._settings.jwt_secret,
            ttl=self._settings.access_token_ttl,
        )
        return JoinResponse(
            access_token=access_token,
            rejoin_token=rejoin_token,
            participant=ParticipantOut.model_validate(participant),
        )
