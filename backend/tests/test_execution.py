"""The execution guard and result events (ADR-008), with fake executors. Needs Postgres and Redis."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.executors import ExecutionError
from app.models import AuditEvent, AuditEventType, PolicyEffect
from app.policy import DecisionCode
from app.ratelimit import RateLimiter
from app.services.approvals import resolve
from app.services.execution import (
    AlreadyExecutedError,
    NotAuthorizedError,
    execute_request,
    resolve_and_execute,
    submit_and_execute,
)
from tests.conftest import FakeExecutor
from tests.test_firewall_flow import add_limit, add_rule, make_agent, payload_for, submit


async def events(db: AsyncSession, request_id: uuid.UUID) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(AuditEvent.action_request_id == request_id).order_by(AuditEvent.id)
    return list((await db.scalars(stmt)).all())


async def submit_with(db, limiter, executors, agent, action_type, **payload):
    return await submit_and_execute(db, limiter, executors, agent.id, action_type, payload_for(action_type, **payload))


async def test_allowed_request_is_executed_once(db: AsyncSession, limiter: RateLimiter, executors) -> None:
    agent = await make_agent(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()

    result, execution = await submit_with(db, limiter, executors, agent, "send_email", to="b@example.com")

    assert execution is not None
    assert execution.event_type == AuditEventType.EXECUTED
    assert execution.actor == "executor:fake-gmail"
    assert execution.data == {"authorized_by": "allowed", "external_id": "fake-1", "fake": True}
    [(request_id, payload)] = executors["send_email"].calls
    assert request_id == result.request_id and payload.to == "b@example.com"
    assert [e.event_type for e in await events(db, result.request_id)] == ["allowed", "executed"]


@pytest.mark.parametrize("effect", [PolicyEffect.DENY, PolicyEffect.NEEDS_APPROVAL])
async def test_non_allowed_decisions_are_not_executed(
    db: AsyncSession, limiter: RateLimiter, executors, effect: PolicyEffect
) -> None:
    agent = await make_agent(db, "make_payment")
    add_rule(db, agent, "make_payment", effect)
    await db.flush()

    result, execution = await submit_with(db, limiter, executors, agent, "make_payment")

    assert execution is None
    assert executors["make_payment"].calls == []
    with pytest.raises(NotAuthorizedError):
        await execute_request(db, result.request_id, executors)
    assert executors["make_payment"].calls == []
    assert len(await events(db, result.request_id)) == 1


async def test_rate_limited_request_is_not_executed(db: AsyncSession, limiter: RateLimiter, executors) -> None:
    agent = await make_agent(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    add_limit(db, agent, "send_email", max_requests=1)
    await db.flush()

    await submit_with(db, limiter, executors, agent, "send_email")
    result, execution = await submit_with(db, limiter, executors, agent, "send_email")

    assert result.decision.code == DecisionCode.RATE_LIMITED
    assert execution is None
    assert len(executors["send_email"].calls) == 1
    assert [e.event_type for e in await events(db, result.request_id)] == ["denied"]


async def test_executor_failure_is_recorded_distinctly_from_denial(
    db: AsyncSession, limiter: RateLimiter, executors
) -> None:
    agent = await make_agent(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()
    executors["send_email"].error = ExecutionError("auth_failed", "Gmail rejected the OAuth credentials.")

    result, execution = await submit_with(db, limiter, executors, agent, "send_email")

    assert result.decision.effect == PolicyEffect.ALLOW
    assert execution is not None
    assert execution.event_type == AuditEventType.EXECUTION_FAILED
    assert execution.reason == "Gmail rejected the OAuth credentials."
    assert execution.data == {"authorized_by": "allowed", "code": "auth_failed"}
    assert [e.event_type for e in await events(db, result.request_id)] == ["allowed", "execution_failed"]


async def test_unexpected_executor_crash_is_recorded_without_details(
    db: AsyncSession, limiter: RateLimiter, executors, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = await make_agent(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()

    async def crash(*args, **kwargs):
        raise RuntimeError("token=super-secret")

    monkeypatch.setattr(executors["send_email"], "execute", crash)
    _, execution = await submit_with(db, limiter, executors, agent, "send_email")

    assert execution.event_type == AuditEventType.EXECUTION_FAILED
    assert execution.data["code"] == "unexpected_error"
    assert "super-secret" not in execution.reason


async def test_missing_executor_is_recorded_as_failure(db: AsyncSession, limiter: RateLimiter) -> None:
    agent = await make_agent(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()

    _, execution = await submit_with(db, limiter, {}, agent, "send_email")

    assert execution.event_type == AuditEventType.EXECUTION_FAILED
    assert execution.data["code"] == "no_executor"


async def test_request_cannot_be_executed_twice(db: AsyncSession, limiter: RateLimiter, executors) -> None:
    agent = await make_agent(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()
    result, _ = await submit_with(db, limiter, executors, agent, "send_email")

    with pytest.raises(AlreadyExecutedError):
        await execute_request(db, result.request_id, executors)
    assert len(executors["send_email"].calls) == 1


async def test_approved_request_is_executed(db: AsyncSession, limiter: RateLimiter, executors) -> None:
    agent = await make_agent(db, "make_payment")
    add_rule(db, agent, "make_payment", PolicyEffect.NEEDS_APPROVAL)
    await db.flush()
    result = await submit(db, limiter, agent, "make_payment", amount=20_000)

    resolution, execution = await resolve_and_execute(db, executors, result.request_id, "alice", approve=True)

    assert resolution.event_type == AuditEventType.APPROVED
    assert execution.event_type == AuditEventType.EXECUTED
    assert execution.data["authorized_by"] == "approved"
    assert executors["make_payment"].calls[0][1].amount == 20_000
    assert [e.event_type for e in await events(db, result.request_id)] == ["needs_approval", "approved", "executed"]


async def test_rejected_request_is_never_executed(db: AsyncSession, limiter: RateLimiter, executors) -> None:
    agent = await make_agent(db, "make_payment")
    add_rule(db, agent, "make_payment", PolicyEffect.NEEDS_APPROVAL)
    await db.flush()
    result = await submit(db, limiter, agent, "make_payment")

    _, execution = await resolve_and_execute(db, executors, result.request_id, "alice", approve=False)

    assert execution is None
    with pytest.raises(NotAuthorizedError):
        await execute_request(db, result.request_id, executors)
    assert executors["make_payment"].calls == []


async def test_agent_deactivated_while_awaiting_approval_is_not_executed(
    db: AsyncSession, limiter: RateLimiter, executors
) -> None:
    agent = await make_agent(db, "make_payment")
    add_rule(db, agent, "make_payment", PolicyEffect.NEEDS_APPROVAL)
    await db.flush()
    result = await submit(db, limiter, agent, "make_payment")
    agent.is_active = False
    await db.flush()

    await resolve(db, result.request_id, "alice", approve=True)
    execution = await execute_request(db, result.request_id, executors)

    assert execution.event_type == AuditEventType.EXECUTION_FAILED
    assert execution.data["code"] == "agent_inactive"
    assert executors["make_payment"].calls == []


async def test_unknown_request_is_not_executed(db: AsyncSession, executors) -> None:
    with pytest.raises(NotAuthorizedError):
        await execute_request(db, uuid.uuid4(), executors)
