"""Events of a session: listed for everyone in it, applied or dismissed by the facilitator."""

import uuid

from fastapi import APIRouter, status

from agilesim.api.deps import CurrentFacilitator, CurrentPrincipal, EventServiceDep
from agilesim.schemas.game import EventCreate, EventOut

router = APIRouter(tags=["events"])


@router.get("/sessions/{session_id}/events")
def list_events(
    session_id: uuid.UUID, caller: CurrentPrincipal, service: EventServiceDep
) -> list[EventOut]:
    """The events of a session in order of days; the scenario's events appear on their day."""
    return service.list_events(session_id, caller.id, caller.role)


@router.post("/sessions/{session_id}/events", status_code=status.HTTP_201_CREATED)
def create_event(
    session_id: uuid.UUID,
    body: EventCreate,
    facilitator: CurrentFacilitator,
    service: EventServiceDep,
) -> EventOut:
    """Add an event of your own for the current day (it has no mechanical effect)."""
    return service.create_manual(session_id, facilitator.id, body)


@router.post("/sessions/{session_id}/events/{event_id}/apply")
def apply_event(
    session_id: uuid.UUID,
    event_id: uuid.UUID,
    facilitator: CurrentFacilitator,
    service: EventServiceDep,
) -> EventOut:
    """Confirm an event and carry out its effect on every team's board."""
    return service.apply(session_id, event_id, facilitator.id)


@router.post("/sessions/{session_id}/events/{event_id}/dismiss")
def dismiss_event(
    session_id: uuid.UUID,
    event_id: uuid.UUID,
    facilitator: CurrentFacilitator,
    service: EventServiceDep,
) -> EventOut:
    """Skip an event without any effect."""
    return service.dismiss(session_id, event_id, facilitator.id)
