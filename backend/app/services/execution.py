"""Running an authorized action through its executor (ADR-008).

`execute_request` is the only caller of executors. It re-reads the request's
events itself instead of trusting its caller, so an executor can only ever run
after an `allowed` decision or an `approved` resolution, and at most once.
Every attempt ends in exactly one `executed` or `execution_failed` event.
"""

import logging
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.store import append_event
from app.executors import ExecutionError, Executor
from app.executors.payloads import InvalidPayloadError, UnknownActionTypeError, parse_payload
from app.models import ActionRequest, Agent, AuditEvent, AuditEventType, PolicyEffect
from app.models.enums import RESULT_EVENT_TYPES
from app.ratelimit import RateLimiter
from app.services import approvals
from app.services.firewall import SubmitResult, submit_action_request

logger = logging.getLogger(__name__)

Executors = Mapping[str, Executor]


class NotAuthorizedError(Exception):
    """The request was never allowed or approved. Reaching this is a bug in the caller."""


class AlreadyExecutedError(Exception):
    pass


async def execute_request(session: AsyncSession, request_id: uuid.UUID, executors: Executors) -> AuditEvent:
    request = await session.get(ActionRequest, request_id)
    if request is None:
        raise NotAuthorizedError(str(request_id))
    event_types = set(
        (await session.scalars(select(AuditEvent.event_type).where(AuditEvent.action_request_id == request_id))).all()
    )
    if AuditEventType.ALLOWED in event_types:
        authorized_by = AuditEventType.ALLOWED
    elif AuditEventType.APPROVED in event_types:
        authorized_by = AuditEventType.APPROVED
    else:
        raise NotAuthorizedError(str(request_id))
    if event_types & RESULT_EVENT_TYPES:
        raise AlreadyExecutedError(str(request_id))

    executor = executors.get(request.action_type)
    actor = executor.actor if executor else "executor"
    event_type, reason, data = await run(session, request, executor)
    event = append_event(session, request, event_type, reason, actor, {"authorized_by": authorized_by.value, **data})
    try:
        await session.flush()
    except IntegrityError as exc:
        # Another worker recorded a result for this request first.
        await session.rollback()
        raise AlreadyExecutedError(str(request_id)) from exc
    await session.commit()
    return event


async def run(
    session: AsyncSession, request: ActionRequest, executor: Executor | None
) -> tuple[AuditEventType, str, dict[str, Any]]:
    def failed(code: str, message: str) -> tuple[AuditEventType, str, dict[str, Any]]:
        return AuditEventType.EXECUTION_FAILED, message, {"code": code}

    agent = await session.get(Agent, request.agent_id)
    if agent is None or not agent.is_active:
        # Matters for approvals: the agent may have been deactivated while waiting.
        return failed("agent_inactive", "Not executed: the agent was deactivated.")
    if executor is None:
        return failed("no_executor", f"No executor is registered for '{request.action_type}'.")
    try:
        payload = parse_payload(request.action_type, request.payload)
    except (UnknownActionTypeError, InvalidPayloadError):
        return failed("invalid_payload", "Not executed: the stored payload no longer validates.")

    try:
        result = await executor.execute(request.id, payload)
    except ExecutionError as exc:
        return failed(exc.code, exc.message)
    except Exception:
        logger.exception("Executor %s crashed on request %s", executor.actor, request.id)
        return failed("unexpected_error", "The executor failed unexpectedly; see server logs.")

    return (
        AuditEventType.EXECUTED,
        f"Executed by {executor.actor}: {result.external_id}.",
        {"external_id": result.external_id, **result.details},
    )


async def submit_and_execute(
    session: AsyncSession,
    limiter: RateLimiter,
    executors: Executors,
    agent_id: uuid.UUID,
    action_type: str,
    payload: dict[str, Any],
) -> tuple[SubmitResult, AuditEvent | None]:
    """Decide on a request and, if it was allowed outright, run it."""
    result = await submit_action_request(session, limiter, agent_id, action_type, payload)
    if result.decision.effect != PolicyEffect.ALLOW:
        return result, None
    return result, await execute_request(session, result.request_id, executors)


async def resolve_and_execute(
    session: AsyncSession,
    executors: Executors,
    request_id: uuid.UUID,
    approver_username: str,
    approve: bool,
    note: str | None = None,
) -> tuple[AuditEvent, AuditEvent | None]:
    """Record an approver's decision and, if approved, run the action."""
    resolution = await approvals.resolve(session, request_id, approver_username, approve, note)
    if not approve:
        return resolution, None
    return resolution, await execute_request(session, request_id, executors)
