"""Read side of the audit log for the dashboard. Queries only — nothing here writes.

Everything is derived from `audit_log` (ADR-001): there is no status column to
read, so an agent's activity and a request's state are both computed from its
events.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActionRequest, Agent, AuditEvent, AuditEventType

MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class EventRow:
    event: AuditEvent
    agent_name: str


@dataclass(frozen=True)
class RequestHistory:
    request: ActionRequest
    agent_name: str
    events: list[AuditEvent]


@dataclass(frozen=True)
class AgentActivity:
    agent: Agent
    # Number of events of each type, e.g. {"allowed": 3, "denied": 1}. Missing types are 0.
    event_counts: dict[str, int] = field(default_factory=dict)
    total_requests: int = 0
    pending_approvals: int = 0
    last_activity_at: datetime | None = None


async def list_events(
    session: AsyncSession,
    *,
    agent_id: uuid.UUID | None = None,
    action_type: str | None = None,
    event_types: Collection[AuditEventType] = (),
    before_id: int | None = None,
    limit: int = 50,
) -> list[EventRow]:
    """Newest first. Page with `before_id` (the last id of the previous page) rather than offsets,
    so new events arriving while someone scrolls don't shift the pages."""
    stmt = select(AuditEvent, Agent.name).join(Agent, Agent.id == AuditEvent.agent_id)
    if agent_id is not None:
        stmt = stmt.where(AuditEvent.agent_id == agent_id)
    if action_type:
        stmt = stmt.where(AuditEvent.action_type == action_type)
    if event_types:
        stmt = stmt.where(AuditEvent.event_type.in_(event_types))
    if before_id is not None:
        stmt = stmt.where(AuditEvent.id < before_id)
    stmt = stmt.order_by(AuditEvent.id.desc()).limit(min(limit, MAX_PAGE_SIZE))
    rows = (await session.execute(stmt)).all()
    return [EventRow(event, agent_name) for event, agent_name in rows]


async def get_request_history(session: AsyncSession, request_id: uuid.UUID) -> RequestHistory | None:
    """The request exactly as submitted plus all its events, oldest first."""
    row = (
        await session.execute(
            select(ActionRequest, Agent.name)
            .join(Agent, Agent.id == ActionRequest.agent_id)
            .where(ActionRequest.id == request_id)
        )
    ).first()
    if row is None:
        return None
    request, agent_name = row
    events = (
        await session.scalars(
            select(AuditEvent).where(AuditEvent.action_request_id == request_id).order_by(AuditEvent.id)
        )
    ).all()
    return RequestHistory(request, agent_name, list(events))


async def list_agent_activity(session: AsyncSession) -> list[AgentActivity]:
    """Every agent with its event counts, in name order. Agents with no activity are included."""
    agents = (await session.scalars(select(Agent).order_by(Agent.name))).all()

    counts: dict[uuid.UUID, dict[str, int]] = {}
    last_seen: dict[uuid.UUID, datetime] = {}
    rows = await session.execute(
        select(AuditEvent.agent_id, AuditEvent.event_type, func.count(), func.max(AuditEvent.created_at)).group_by(
            AuditEvent.agent_id, AuditEvent.event_type
        )
    )
    for agent_id, event_type, count, latest in rows:
        counts.setdefault(agent_id, {})[event_type] = count
        if agent_id not in last_seen or latest > last_seen[agent_id]:
            last_seen[agent_id] = latest

    activity = []
    for agent in agents:
        c = counts.get(agent.id, {})
        # Every request gets exactly one decision event, and approved/rejected only ever
        # follow a needs_approval one (both enforced by unique indexes), so these add up.
        total = sum(c.get(t, 0) for t in (AuditEventType.ALLOWED, AuditEventType.DENIED, AuditEventType.NEEDS_APPROVAL))
        pending = c.get(AuditEventType.NEEDS_APPROVAL, 0) - c.get(AuditEventType.APPROVED, 0) - c.get(
            AuditEventType.REJECTED, 0
        )
        activity.append(AgentActivity(agent, c, total, pending, last_seen.get(agent.id)))
    return activity
