import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentApprover, DbSession
from app.models import Approver
from app.services import approvals
from app.services.approvals import AlreadyResolvedError, NotAwaitingApprovalError, RequestNotFoundError

router = APIRouter(prefix="/approvals", tags=["approvals"])


class PendingApprovalOut(BaseModel):
    request_id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    action_type: str
    payload: dict[str, Any]
    reason: str
    requested_at: datetime


class ResolveIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class ResolutionOut(BaseModel):
    request_id: uuid.UUID
    event_type: str
    reason: str
    actor: str
    created_at: datetime


@router.get("/pending")
async def list_pending(db: DbSession, _: CurrentApprover) -> list[PendingApprovalOut]:
    return [
        PendingApprovalOut(
            request_id=item.request.id,
            agent_id=item.request.agent_id,
            agent_name=item.agent_name,
            action_type=item.request.action_type,
            payload=item.request.payload,
            reason=item.decision.reason,
            requested_at=item.request.created_at,
        )
        for item in await approvals.list_pending(db)
    ]


async def resolve(
    db: DbSession, approver: Approver, request_id: uuid.UUID, approve: bool, body: ResolveIn | None
) -> ResolutionOut:
    try:
        event = await approvals.resolve(db, request_id, approver.username, approve, body.note if body else None)
    except RequestNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action request not found.")
    except NotAwaitingApprovalError:
        raise HTTPException(status.HTTP_409_CONFLICT, "This request was not sent for approval.")
    except AlreadyResolvedError:
        raise HTTPException(status.HTTP_409_CONFLICT, "This request has already been approved or rejected.")
    await db.refresh(event)
    return ResolutionOut(
        request_id=request_id,
        event_type=event.event_type,
        reason=event.reason,
        actor=event.actor,
        created_at=event.created_at,
    )


@router.post("/{request_id}/approve")
async def approve(
    request_id: uuid.UUID, db: DbSession, approver: CurrentApprover, body: ResolveIn | None = None
) -> ResolutionOut:
    return await resolve(db, approver, request_id, True, body)


@router.post("/{request_id}/reject")
async def reject(
    request_id: uuid.UUID, db: DbSession, approver: CurrentApprover, body: ResolveIn | None = None
) -> ResolutionOut:
    return await resolve(db, approver, request_id, False, body)
