"""DB-layer guarantees of the event store (ADR-001, TEST_PLAN.md: Audit Log)."""

import uuid

import pytest
from sqlalchemy import delete, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActionRequest, Agent, AuditEvent, AuditEventType


async def make_request(db: AsyncSession) -> ActionRequest:
    agent = Agent(name=f"test-agent-{uuid.uuid4().hex[:8]}", allowed_action_types=["send_email"])
    db.add(agent)
    await db.flush()
    request = ActionRequest(agent_id=agent.id, action_type="send_email", payload={"to": "a@example.com"})
    db.add(request)
    await db.flush()
    return request


def event_for(request: ActionRequest, event_type: AuditEventType) -> AuditEvent:
    return AuditEvent(
        action_request_id=request.id,
        agent_id=request.agent_id,
        action_type=request.action_type,
        event_type=event_type,
        reason="test",
        actor="firewall",
    )


async def expect_rejected(db: AsyncSession, statement, exc_type=DBAPIError) -> str:
    """Run `statement` in a savepoint and return the DB error message it raised."""
    with pytest.raises(exc_type) as exc_info:
        async with db.begin_nested():
            await db.execute(statement)
    return str(exc_info.value.orig)


async def test_audit_event_can_be_inserted(db: AsyncSession) -> None:
    request = await make_request(db)
    event = event_for(request, AuditEventType.ALLOWED)
    db.add(event)
    await db.flush()

    assert event.id is not None
    assert event.created_at is not None


async def test_audit_log_rejects_update(db: AsyncSession) -> None:
    request = await make_request(db)
    db.add(event_for(request, AuditEventType.DENIED))
    await db.flush()

    msg = await expect_rejected(
        db, update(AuditEvent).where(AuditEvent.action_request_id == request.id).values(reason="tampered")
    )
    assert "audit_log is append-only: UPDATE" in msg


async def test_audit_log_rejects_delete(db: AsyncSession) -> None:
    request = await make_request(db)
    db.add(event_for(request, AuditEventType.DENIED))
    await db.flush()

    msg = await expect_rejected(db, delete(AuditEvent).where(AuditEvent.action_request_id == request.id))
    assert "audit_log is append-only: DELETE" in msg


async def test_audit_log_rejects_truncate(db: AsyncSession) -> None:
    msg = await expect_rejected(db, text("TRUNCATE audit_log CASCADE"))
    assert "is append-only: TRUNCATE" in msg


async def test_action_requests_reject_update_and_delete(db: AsyncSession) -> None:
    request = await make_request(db)

    msg = await expect_rejected(
        db, update(ActionRequest).where(ActionRequest.id == request.id).values(payload={"to": "evil@example.com"})
    )
    assert "action_requests is append-only: UPDATE" in msg

    msg = await expect_rejected(db, delete(ActionRequest).where(ActionRequest.id == request.id))
    assert "action_requests is append-only: DELETE" in msg


async def test_only_one_decision_event_per_request(db: AsyncSession) -> None:
    request = await make_request(db)
    db.add(event_for(request, AuditEventType.NEEDS_APPROVAL))
    await db.flush()

    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            db.add(event_for(request, AuditEventType.ALLOWED))
            await db.flush()


async def test_follow_up_events_are_allowed_after_decision(db: AsyncSession) -> None:
    request = await make_request(db)
    for event_type in (AuditEventType.NEEDS_APPROVAL, AuditEventType.APPROVED, AuditEventType.EXECUTED):
        db.add(event_for(request, event_type))
    await db.flush()


async def test_unknown_event_type_is_rejected(db: AsyncSession) -> None:
    request = await make_request(db)

    with pytest.raises(IntegrityError, match="ck_audit_log_event_type_valid"):
        async with db.begin_nested():
            db.add(event_for(request, "made_up"))  # type: ignore[arg-type]
            await db.flush()
