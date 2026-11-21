"""Use cases of facilitator accounts: register and log in."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agilesim.config import Settings
from agilesim.core import security
from agilesim.core.constants import ROLE_FACILITATOR
from agilesim.core.errors import ConflictError, UnauthorizedError
from agilesim.repositories.accounts import FacilitatorRepository
from agilesim.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

# Verified against when the e-mail is unknown, so that the response time does not reveal
# whether an account exists.
_DUMMY_HASH = security.hash_password("dummy password for timing")


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._facilitators = FacilitatorRepository(session)

    def register(self, request: RegisterRequest) -> TokenResponse:
        if self._facilitators.get_by_email(request.email) is not None:
            raise ConflictError("An account with this e-mail already exists")
        try:
            facilitator = self._facilitators.add(
                request.email, request.display_name, security.hash_password(request.password)
            )
            self._session.commit()
        except IntegrityError as exc:  # two registrations raced; the unique key decided
            self._session.rollback()
            raise ConflictError("An account with this e-mail already exists") from exc
        return self._token(facilitator.id)

    def login(self, request: LoginRequest) -> TokenResponse:
        facilitator = self._facilitators.get_by_email(request.email)
        password_hash = facilitator.password_hash if facilitator else _DUMMY_HASH
        valid = security.verify_password(request.password, password_hash)
        if facilitator is None or not valid or not facilitator.is_active:
            raise UnauthorizedError("Wrong e-mail or password")
        return self._token(facilitator.id)

    def _token(self, facilitator_id: uuid.UUID) -> TokenResponse:
        token = security.create_access_token(
            facilitator_id,
            ROLE_FACILITATOR,
            secret=self._settings.jwt_secret,
            ttl=self._settings.access_token_ttl,
        )
        return TokenResponse(access_token=token, role=ROLE_FACILITATOR)
