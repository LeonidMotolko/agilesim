"""Data access for facilitator accounts."""

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from agilesim.db.models import Facilitator


class FacilitatorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, facilitator_id: uuid.UUID) -> Facilitator | None:
        return self._session.get(Facilitator, facilitator_id)

    def get_by_email(self, email: str) -> Facilitator | None:
        return self._session.scalars(
            sa.select(Facilitator).where(Facilitator.email == email)
        ).one_or_none()

    def add(self, email: str, display_name: str, password_hash: str) -> Facilitator:
        facilitator = Facilitator(
            email=email, display_name=display_name, password_hash=password_hash
        )
        self._session.add(facilitator)
        self._session.flush()
        return facilitator
