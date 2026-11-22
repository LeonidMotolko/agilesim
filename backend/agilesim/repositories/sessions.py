"""Data access for scenarios, game sessions, teams and participants."""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from agilesim.db.enums import ParticipantRole
from agilesim.db.models import GameSession, Participant, Scenario, Team


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest_scenario(self, code: str) -> Scenario | None:
        return self._session.scalars(
            sa.select(Scenario)
            .where(Scenario.code == code)
            .order_by(Scenario.version.desc())
            .limit(1)
        ).one_or_none()

    def get(self, session_id: uuid.UUID) -> GameSession | None:
        return self._session.get(GameSession, session_id)

    def get_for_update(self, session_id: uuid.UUID) -> GameSession | None:
        """The session row, locked until the commit, so day changes of a session run one by one.

        ``FOR NO KEY UPDATE`` needs the UPDATE right, which ``app_write`` has on
        ``game_sessions``; it does not block the foreign-key checks of inserted child rows.
        """
        return self._session.scalars(
            sa.select(GameSession)
            .where(GameSession.id == session_id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        ).one_or_none()

    def get_by_join_code(self, join_code: str) -> GameSession | None:
        return self._session.scalars(
            sa.select(GameSession).where(GameSession.join_code == join_code)
        ).one_or_none()

    def join_code_exists(self, join_code: str) -> bool:
        return self.get_by_join_code(join_code) is not None

    def list_for_facilitator(self, facilitator_id: uuid.UUID) -> list[GameSession]:
        return list(
            self._session.scalars(
                sa.select(GameSession)
                .where(GameSession.facilitator_id == facilitator_id)
                .order_by(GameSession.created_at.desc())
            )
        )

    def add(
        self, facilitator_id: uuid.UUID, scenario_id: uuid.UUID, name: str, join_code: str
    ) -> GameSession:
        game = GameSession(
            facilitator_id=facilitator_id, scenario_id=scenario_id, name=name, join_code=join_code
        )
        self._session.add(game)
        self._session.flush()
        return game


class TeamRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, team_id: uuid.UUID) -> Team | None:
        return self._session.get(Team, team_id)

    def list_for_session(self, session_id: uuid.UUID) -> list[Team]:
        return list(
            self._session.scalars(
                sa.select(Team)
                .where(Team.session_id == session_id)
                .order_by(Team.created_at, Team.name)
            )
        )

    def name_exists(self, session_id: uuid.UUID, name: str) -> bool:
        return (
            self._session.scalars(
                sa.select(Team.id).where(Team.session_id == session_id, Team.name == name)
            ).first()
            is not None
        )

    def add(self, session_id: uuid.UUID, name: str) -> Team:
        team = Team(session_id=session_id, name=name)
        self._session.add(team)
        self._session.flush()
        return team


class ParticipantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, participant_id: uuid.UUID) -> Participant | None:
        return self._session.get(Participant, participant_id)

    def get_by_token_hash(self, token_hash: str) -> Participant | None:
        return self._session.scalars(
            sa.select(Participant).where(Participant.token_hash == token_hash)
        ).one_or_none()

    def name_exists(self, session_id: uuid.UUID, display_name: str) -> bool:
        return (
            self._session.scalars(
                sa.select(Participant.id).where(
                    Participant.session_id == session_id, Participant.display_name == display_name
                )
            ).first()
            is not None
        )

    def add(
        self,
        session_id: uuid.UUID,
        team_id: uuid.UUID | None,
        display_name: str,
        token_hash: str,
        role: ParticipantRole = ParticipantRole.PLAYER,
    ) -> Participant:
        participant = Participant(
            session_id=session_id,
            team_id=team_id,
            display_name=display_name,
            role=role,
            token_hash=token_hash,
            consent_given_at=datetime.now(UTC),
        )
        self._session.add(participant)
        self._session.flush()
        return participant
