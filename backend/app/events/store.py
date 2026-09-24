"""Write helpers for the append-only audit log. The only place events are created."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActionRequest, AuditEvent, AuditEventType


def append_event(
    session: AsyncSession,
    request: ActionRequest,
    event_type: AuditEventType,
    reason: str,
    actor: str,
    data: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add an event for `request` to the session. The caller commits."""
    event = AuditEvent(
        action_request_id=request.id,
        agent_id=request.agent_id,
        action_type=request.action_type,
        event_type=event_type,
        reason=reason,
        actor=actor,
        data=data or {},
    )
    session.add(event)
    return event
