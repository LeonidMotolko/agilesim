"""Request and response bodies of the session, team and participant endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from agilesim.core.constants import JOIN_CODE_LENGTH
from agilesim.db.enums import LeadTimeConvention, ParticipantRole, SessionStatus
from agilesim.schemas.auth import DisplayName


class SessionCreate(BaseModel):
    name: DisplayName


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    join_code: str
    status: SessionStatus
    current_day: int
    wip_limits_enabled: bool
    lead_time_convention: LeadTimeConvention
    started_at: datetime | None
    finished_at: datetime | None


class TeamCreate(BaseModel):
    name: DisplayName


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    name: str


class JoinRequest(BaseModel):
    join_code: str = Field(
        min_length=JOIN_CODE_LENGTH, max_length=JOIN_CODE_LENGTH, pattern=r"^[A-Za-z0-9]+$"
    )
    display_name: DisplayName
    team_id: uuid.UUID | None = None
    consent: bool = Field(description="The player agreed to the processing of the game data")


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    team_id: uuid.UUID | None
    display_name: str
    role: ParticipantRole


class JoinResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    rejoin_token: str = Field(description="Shown once: lets the player return after a reload")
    participant: ParticipantOut


class RejoinRequest(BaseModel):
    rejoin_token: str = Field(min_length=16, max_length=128)
