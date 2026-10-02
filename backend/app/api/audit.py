import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentApprover, DbSession
from app.models import AuditEvent, AuditEventType
from app.services import audit
from app.services.audit import MAX_PAGE_SIZE

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEventOut(BaseModel):
    id: int
    request_id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    action_type: str
    event_type: AuditEventType
    reason: str
    actor: str
    data: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_event(cls, event: AuditEvent, agent_name: str) -> "AuditEventOut":
        return cls(
            id=event.id,
            request_id=event.action_request_id,
            agent_id=event.agent_id,
            agent_name=agent_name,
            action_type=event.action_type,
            event_type=event.event_type,
            reason=event.reason,
            actor=event.actor,
            data=event.data,
            created_at=event.created_at,
        )


class AuditPageOut(BaseModel):
    items: list[AuditEventOut]
    # Pass as `before` to get the next (older) page; null when there are no more events.
    next_before: int | None


class RequestHistoryOut(BaseModel):
    request_id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    action_type: str
    payload: dict[str, Any]
    requested_at: datetime
    events: list[AuditEventOut]


@router.get("/events")
async def list_events(
    db: DbSession,
    _: CurrentApprover,
    agent_id: uuid.UUID | None = None,
    action_type: Annotated[str | None, Query(max_length=100)] = None,
    event_type: Annotated[list[AuditEventType] | None, Query()] = None,
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> AuditPageOut:
    """The audit log, newest first. `event_type` may be repeated to match any of several types."""
    # One extra row tells us whether another page exists without a COUNT query.
    rows = await audit.list_events(
        db,
        agent_id=agent_id,
        action_type=action_type,
        event_types=event_type or (),
        before_id=before,
        limit=limit + 1,
    )
    page = rows[:limit]
    return AuditPageOut(
        items=[AuditEventOut.from_event(row.event, row.agent_name) for row in page],
        next_before=page[-1].event.id if len(rows) > limit else None,
    )


@router.get("/requests/{request_id}")
async def get_request(request_id: uuid.UUID, db: DbSession, _: CurrentApprover) -> RequestHistoryOut:
    """One request as the agent submitted it, with every event it produced, oldest first."""
    history = await audit.get_request_history(db, request_id)
    if history is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action request not found.")
    return RequestHistoryOut(
        request_id=history.request.id,
        agent_id=history.request.agent_id,
        agent_name=history.agent_name,
        action_type=history.request.action_type,
        payload=history.request.payload,
        requested_at=history.request.created_at,
        events=[AuditEventOut.from_event(event, history.agent_name) for event in history.events],
    )
