"""The full decision flow: policy + rate limiter + audit log. Needs Postgres and Redis."""

import uuid
from typing import Any

import pytest
from redis import RedisError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActionRequest, Agent, AuditEvent, AuditEventType, PolicyEffect, PolicyRule, RateLimit
from app.policy import DecisionCode
from app.ratelimit import RateLimiter
from app.services.firewall import AgentNotFoundError, SubmitResult, submit_action_request


async def make_agent(db: AsyncSession, *action_types: str, is_active: bool = True) -> Agent:
    agent = Agent(
        name=f"test-agent-{uuid.uuid4().hex[:8]}",
        allowed_action_types=list(action_types),
        is_active=is_active,
    )
    db.add(agent)
    await db.flush()
    return agent


def add_rule(
    db: AsyncSession, agent: Agent, action_type: str, effect: PolicyEffect, priority: int = 100, **kwargs: Any
) -> PolicyRule:
    # High priority so global seed rules in the dev DB never win.
    rule = PolicyRule(agent_id=agent.id, action_type=action_type, effect=effect, priority=priority, **kwargs)
    db.add(rule)
    return rule


def add_limit(db: AsyncSession, agent: Agent, action_type: str, max_requests: int, window: int = 60) -> None:
    db.add(RateLimit(agent_id=agent.id, action_type=action_type, max_requests=max_requests, window_seconds=window))


async def events_for(db: AsyncSession, request_id: uuid.UUID) -> list[AuditEvent]:
    return list(
        (await db.scalars(select(AuditEvent).where(AuditEvent.action_request_id == request_id))).all()
    )


async def submit(db: AsyncSession, limiter: RateLimiter, agent: Agent, action_type: str, **payload: Any) -> SubmitResult:
    return await submit_action_request(db, limiter, agent.id, action_type, payload)


async def test_allowed_request_is_recorded_with_one_event(db: AsyncSession, limiter: RateLimiter) -> None:
    agent = await make_agent(db, "send_email")
    rule = add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()

    result = await submit(db, limiter, agent, "send_email", to="a@example.com")

    assert result.decision.effect == PolicyEffect.ALLOW
    request = await db.get(ActionRequest, result.request_id)
    assert request is not None and request.payload == {"to": "a@example.com"}
    [event] = await events_for(db, result.request_id)
    assert event.event_type == AuditEventType.ALLOWED
    assert event.actor == "firewall"
    assert event.data["code"] == DecisionCode.RULE_MATCHED
    assert event.data["rule_id"] == str(rule.id)


async def test_needs_approval_is_recorded(db: AsyncSession, limiter: RateLimiter) -> None:
    agent = await make_agent(db, "make_payment")
    add_rule(db, agent, "make_payment", PolicyEffect.NEEDS_APPROVAL)
    await db.flush()

    result = await submit(db, limiter, agent, "make_payment", amount=10_000)

    assert result.decision.effect == PolicyEffect.NEEDS_APPROVAL
    [event] = await events_for(db, result.request_id)
    assert event.event_type == AuditEventType.NEEDS_APPROVAL


async def test_rate_limit_denies_request_n_plus_one_with_reason(db: AsyncSession, limiter: RateLimiter) -> None:
    agent = await make_agent(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    add_limit(db, agent, "send_email", max_requests=2)
    await db.flush()

    for _ in range(2):
        result = await submit(db, limiter, agent, "send_email", to="a@example.com")
        assert result.decision.effect == PolicyEffect.ALLOW

    result = await submit(db, limiter, agent, "send_email", to="a@example.com")

    assert result.decision.effect == PolicyEffect.DENY
    assert result.decision.code == DecisionCode.RATE_LIMITED
    [event] = await events_for(db, result.request_id)
    assert event.event_type == AuditEventType.DENIED
    assert event.data["code"] == "rate_limited"
    assert event.data["rate_limit"] == {"max_requests": 2, "window_seconds": 60}
    assert event.data["policy_effect"] == "allow"
    assert event.reason.startswith("Rate limited:")


async def test_rate_limit_also_applies_to_needs_approval(db: AsyncSession, limiter: RateLimiter) -> None:
    agent = await make_agent(db, "make_payment")
    add_rule(db, agent, "make_payment", PolicyEffect.NEEDS_APPROVAL)
    add_limit(db, agent, "make_payment", max_requests=1)
    await db.flush()

    await submit(db, limiter, agent, "make_payment", amount=1)
    result = await submit(db, limiter, agent, "make_payment", amount=1)

    assert result.decision.code == DecisionCode.RATE_LIMITED


async def test_policy_denied_requests_do_not_use_rate_limit_budget(db: AsyncSession, limiter: RateLimiter) -> None:
    agent = await make_agent(db, "send_email")
    only_example = {"all": [{"field": "to", "op": "email_domain_in", "value": ["example.com"]}]}
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW, conditions=only_example)
    add_rule(db, agent, "send_email", PolicyEffect.DENY, priority=50)
    add_limit(db, agent, "send_email", max_requests=1)
    await db.flush()

    for _ in range(3):
        denied = await submit(db, limiter, agent, "send_email", to="x@evil.com")
        assert denied.decision.code == DecisionCode.RULE_MATCHED
        assert denied.decision.effect == PolicyEffect.DENY

    allowed = await submit(db, limiter, agent, "send_email", to="x@example.com")
    assert allowed.decision.effect == PolicyEffect.ALLOW


async def test_redis_failure_fails_closed(db: AsyncSession, limiter: RateLimiter, monkeypatch: pytest.MonkeyPatch) -> None:
    agent = await make_agent(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()

    async def broken_hit(*args: Any, **kwargs: Any) -> None:
        raise RedisError("connection refused")

    monkeypatch.setattr(limiter, "hit", broken_hit)
    result = await submit(db, limiter, agent, "send_email", to="a@example.com")

    assert result.decision.effect == PolicyEffect.DENY
    assert result.decision.code == DecisionCode.RATE_LIMITER_UNAVAILABLE
    [event] = await events_for(db, result.request_id)
    assert event.event_type == AuditEventType.DENIED


async def test_unreachable_redis_fails_closed(db: AsyncSession) -> None:
    agent = await make_agent(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()
    dead = Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.5)
    try:
        result = await submit(db, RateLimiter(dead), agent, "send_email", to="a@example.com")
    finally:
        await dead.aclose()

    assert result.decision.code == DecisionCode.RATE_LIMITER_UNAVAILABLE


async def test_malformed_rule_in_db_fails_closed(db: AsyncSession, limiter: RateLimiter) -> None:
    agent = await make_agent(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW, conditions={"all": [{"field": "to", "op": "bogus"}]})
    await db.flush()

    result = await submit(db, limiter, agent, "send_email", to="a@example.com")

    assert result.decision.effect == PolicyEffect.DENY
    assert result.decision.code == DecisionCode.POLICY_ERROR


async def test_inactive_agent_is_denied_and_recorded(db: AsyncSession, limiter: RateLimiter) -> None:
    agent = await make_agent(db, "send_email", is_active=False)
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()

    result = await submit(db, limiter, agent, "send_email", to="a@example.com")

    assert result.decision.code == DecisionCode.AGENT_INACTIVE
    assert len(await events_for(db, result.request_id)) == 1


async def test_unknown_agent_raises(db: AsyncSession, limiter: RateLimiter) -> None:
    with pytest.raises(AgentNotFoundError):
        await submit_action_request(db, limiter, uuid.uuid4(), "send_email", {})
