"""Request and response bodies of the game endpoints (board, dice, points, moves, results)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from agilesim.db.enums import CardColumnState

WorkStageCode = Literal["analysis", "development", "testing"]
TargetStageCode = Literal["backlog", "analysis", "development", "testing", "done"]


class CardOut(BaseModel):
    id: uuid.UUID
    number: int
    title: str
    value: float
    is_emergency: bool
    stage: str
    state: CardColumnState | None
    is_blocked: bool
    squares_left: dict[str, int]


class WipCounter(BaseModel):
    stage: str
    count: int
    limit: int | None


class DiceOut(BaseModel):
    stage: str
    day: int
    value: int
    points_left: int


class BoardOut(BaseModel):
    team_id: uuid.UUID
    day: int
    wip_limits_enabled: bool
    cards: list[CardOut]
    wip: list[WipCounter]
    dice: list[DiceOut]


class MoveRequest(BaseModel):
    to_stage: TargetStageCode
    request_id: uuid.UUID = Field(description="Client-made id: a repeated request changes nothing")


class MoveOut(BaseModel):
    card: CardOut
    replayed: bool = Field(description="True when this request id was already accepted")


class DiceRequest(BaseModel):
    stage: WorkStageCode


class SpendRequest(BaseModel):
    card_id: uuid.UUID
    source_stage: WorkStageCode = Field(description="The stage whose die points are spent")
    points: int = Field(ge=1, le=6)
    request_id: uuid.UUID


class SpendOut(BaseModel):
    card: CardOut
    points_spent: int
    squares_crossed: int
    points_lost_to_rounding: int
    points_left: int
    replayed: bool = False


class TeamResultOut(BaseModel):
    team_id: uuid.UUID
    team_name: str
    done_cards: int
    money_earned: float
    avg_lead_time_days: float | None
    money_rank: int


class CardFlowOut(BaseModel):
    card_number: int
    title: str
    value: float
    pulled_day: int | None
    done_day: int | None
    lead_time_days: int | None
