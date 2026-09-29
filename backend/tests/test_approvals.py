"""The approval queue service (TEST_PLAN.md: Approval Workflow). Needs Postgres and Redis."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, AuditEventType, PolicyEffect
from app.ratelimit import RateLimiter
from app.services.approvals import (
    AlreadyResolvedError,
    NotAwaitingApprovalError,
    RequestNotFoundError,
    list_pending,
    resolve,
)
from tests.test_firewall_flow import add_rule, make_agent, submit


async def pending_request(db: AsyncSession, limiter: RateLimiter) -> uuid.UUID:
    agent = await make_agent(db, "make_payment")
    add_rule(db, agent, "make_payment", PolicyEffect.NEEDS_APPROVAL)
    await db.flush()
    result = await submit(db, limiter, agent, "make_payment", amount=10_000)
    assert result.decision.effect == PolicyEffect.NEEDS_APPROVAL
    return result.request_id


async def pending_ids(db: AsyncSession) -> set[uuid.UUID]:
    return {item.request.id for item in await list_pending(db)}


async def event_types(db: AsyncSession, request_id: uuid.UUID) -> list[str]:
    stmt = select(AuditEvent.event_type).where(AuditEvent.action_request_id == request_id).order_by(AuditEvent.id)
    return list((await db.scalars(stmt)).all())


async def test_needs_approval_request_appears_in_queue(db: AsyncSession, limiter: RateLimiter) -> None:
    request_id = await pending_request(db, limiter)

    [item] = [item for item in await list_pending(db) if item.request.id == request_id]
    assert item.request.payload == {"amount": 10_000}
    assert item.agent_name.startswith("test-agent-")
    assert item.decision.event_type == AuditEventType.NEEDS_APPROVAL


async def test_allowed_and_denied_requests_are_not_queued(db: AsyncSession, limiter: RateLimiter) -> None:
    agent = await make_agent(db, "send_email", "make_payment")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    add_rule(db, agent, "make_payment", PolicyEffect.DENY)
    await db.flush()
    allowed = await submit(db, limiter, agent, "send_email", to="a@example.com")
    denied = await submit(db, limiter, agent, "make_payment", amount=1)

    assert not {allowed.request_id, denied.request_id} & await pending_ids(db)


async def test_approve_appends_event_and_leaves_queue(db: AsyncSession, limiter: RateLimiter) -> None:
    request_id = await pending_request(db, limiter)

    event = await resolve(db, request_id, "alice", approve=True)

    assert event.event_type == AuditEventType.APPROVED
    assert event.actor == "approver:alice"
    assert event.reason == "Approved by alice."
    assert request_id not in await pending_ids(db)
    assert await event_types(db, request_id) == ["needs_approval", "approved"]


async def test_reject_appends_event_with_note(db: AsyncSession, limiter: RateLimiter) -> None:
    request_id = await pending_request(db, limiter)

    event = await resolve(db, request_id, "bob", approve=False, note="Amount looks wrong")

    assert event.event_type == AuditEventType.REJECTED
    assert event.actor == "approver:bob"
    assert event.reason == "Rejected by bob: Amount looks wrong"
    assert event.data == {"note": "Amount looks wrong"}
    assert request_id not in await pending_ids(db)


@pytest.mark.parametrize("second_approve", [True, False])
async def test_resolved_request_cannot_be_resolved_again(
    db: AsyncSession, limiter: RateLimiter, second_approve: bool
) -> None:
    request_id = await pending_request(db, limiter)
    await resolve(db, request_id, "alice", approve=True)

    with pytest.raises(AlreadyResolvedError):
        await resolve(db, request_id, "bob", approve=second_approve)
    assert await event_types(db, request_id) == ["needs_approval", "approved"]


async def test_allowed_request_cannot_be_approved(db: AsyncSession, limiter: RateLimiter) -> None:
    agent = await make_agent(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()
    result = await submit(db, limiter, agent, "send_email", to="a@example.com")

    with pytest.raises(NotAwaitingApprovalError):
        await resolve(db, result.request_id, "alice", approve=True)


async def test_denied_request_cannot_be_approved(db: AsyncSession, limiter: RateLimiter) -> None:
    agent = await make_agent(db, "make_payment")
    add_rule(db, agent, "make_payment", PolicyEffect.DENY)
    await db.flush()
    result = await submit(db, limiter, agent, "make_payment", amount=1)

    with pytest.raises(NotAwaitingApprovalError):
        await resolve(db, result.request_id, "alice", approve=True)
    assert await event_types(db, result.request_id) == ["denied"]


async def test_unknown_request_raises(db: AsyncSession) -> None:
    with pytest.raises(RequestNotFoundError):
        await resolve(db, uuid.uuid4(), "alice", approve=True)
