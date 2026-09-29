"""The approval queue for NEEDS_APPROVAL requests.

There is no queue table or status column (ADR-001): a request is pending when
its firewall decision was `needs_approval` and it has no `approved`/`rejected`
event yet. Resolving it appends one of those events; a partial unique index
guarantees at most one per request even under concurrent approvers (ADR-007).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.events.store import append_event
from app.models import ActionRequest, Agent, AuditEvent, AuditEventType
from app.models.enums import DECISION_EVENT_TYPES, RESOLUTION_EVENT_TYPES


class ApprovalError(Exception):
    pass


class RequestNotFoundError(ApprovalError):
    pass


class NotAwaitingApprovalError(ApprovalError):
    """The firewall allowed or denied this request; there is nothing to approve."""


class AlreadyResolvedError(ApprovalError):
    pass


@dataclass(frozen=True)
class PendingApproval:
    request: ActionRequest
    agent_name: str
    decision: AuditEvent


def approver_actor(username: str) -> str:
    return f"approver:{username}"


async def list_pending(session: AsyncSession) -> list[PendingApproval]:
    """Unresolved NEEDS_APPROVAL requests, oldest first."""
    resolution = aliased(AuditEvent)
    resolved = (
        select(resolution.id)
        .where(
            resolution.action_request_id == ActionRequest.id,
            resolution.event_type.in_(RESOLUTION_EVENT_TYPES),
        )
        .exists()
    )
    stmt = (
        select(ActionRequest, Agent.name, AuditEvent)
        .join(Agent, Agent.id == ActionRequest.agent_id)
        .join(
            AuditEvent,
            (AuditEvent.action_request_id == ActionRequest.id)
            & (AuditEvent.event_type == AuditEventType.NEEDS_APPROVAL),
        )
        .where(~resolved)
        .order_by(ActionRequest.created_at, ActionRequest.id)
    )
    rows = (await session.execute(stmt)).all()
    return [PendingApproval(request, agent_name, decision) for request, agent_name, decision in rows]


async def resolve(
    session: AsyncSession,
    request_id: uuid.UUID,
    approver_username: str,
    approve: bool,
    note: str | None = None,
) -> AuditEvent:
    """Approve or reject a pending request by appending exactly one event."""
    request = await session.get(ActionRequest, request_id)
    if request is None:
        raise RequestNotFoundError(str(request_id))

    events = (
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.action_request_id == request_id,
                AuditEvent.event_type.in_(DECISION_EVENT_TYPES | RESOLUTION_EVENT_TYPES),
            )
        )
    ).all()
    event_types = {event.event_type for event in events}
    if AuditEventType.NEEDS_APPROVAL not in event_types:
        raise NotAwaitingApprovalError(str(request_id))
    if event_types & RESOLUTION_EVENT_TYPES:
        raise AlreadyResolvedError(str(request_id))

    verb = "Approved" if approve else "Rejected"
    reason = f"{verb} by {approver_username}" + (f": {note}" if note else ".")
    event = append_event(
        session,
        request,
        AuditEventType.APPROVED if approve else AuditEventType.REJECTED,
        reason,
        approver_actor(approver_username),
        {"note": note} if note else {},
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        # Another approver resolved it between our check and our insert.
        await session.rollback()
        raise AlreadyResolvedError(str(request_id)) from exc
    await session.commit()
    return event
