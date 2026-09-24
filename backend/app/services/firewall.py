"""The decision flow for an incoming action request.

    load agent + rules -> policy.evaluate -> rate limiter -> write request + one decision event

Policy runs first, so requests it denies don't use up rate-limit budget
(ADR-006). Everything that can't be checked fails closed (ADR-005).
"""

import uuid
from dataclasses import dataclass, replace
from typing import Any

from pydantic import ValidationError
from redis import RedisError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.store import append_event
from app.models import ActionRequest, Agent, AuditEventType, PolicyEffect, PolicyRule, RateLimit
from app.policy import ActionContext, AgentContext, Decision, DecisionCode, Rule, evaluate
from app.ratelimit import RateLimiter, select_limits

FIREWALL_ACTOR = "firewall"

EVENT_FOR_EFFECT = {
    PolicyEffect.ALLOW: AuditEventType.ALLOWED,
    PolicyEffect.DENY: AuditEventType.DENIED,
    PolicyEffect.NEEDS_APPROVAL: AuditEventType.NEEDS_APPROVAL,
}


class AgentNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class SubmitResult:
    request_id: uuid.UUID
    decision: Decision


def for_agent(model: type[PolicyRule] | type[RateLimit], agent_id: uuid.UUID, action_type: str):
    return select(model).where(
        model.action_type == action_type,
        model.is_active,
        or_(model.agent_id.is_(None), model.agent_id == agent_id),
    )


async def decide_policy(
    session: AsyncSession, agent: Agent, action: ActionContext
) -> Decision:
    rows = (await session.scalars(for_agent(PolicyRule, agent.id, action.action_type))).all()
    try:
        rules = [Rule.from_model(row) for row in rows]
    except ValidationError as exc:
        return Decision(
            PolicyEffect.DENY,
            DecisionCode.POLICY_ERROR,
            f"A policy rule for '{action.action_type}' is malformed: {exc.error_count()} error(s).",
        )
    return evaluate(AgentContext.from_model(agent), action, rules)


async def apply_rate_limit(
    session: AsyncSession, limiter: RateLimiter, agent: Agent, action: ActionContext, decision: Decision
) -> tuple[Decision, dict[str, Any]]:
    """Downgrade a non-deny decision to DENY if the agent is over its limit."""
    rows = (await session.scalars(for_agent(RateLimit, agent.id, action.action_type))).all()
    limits = select_limits(agent.id, action.action_type, rows)
    try:
        result = await limiter.hit(agent.id, action.action_type, limits)
    except RedisError:
        return (
            Decision(
                PolicyEffect.DENY,
                DecisionCode.RATE_LIMITER_UNAVAILABLE,
                "Rate limiter is unavailable, so the request could not be checked.",
            ),
            {},
        )

    if result.allowed:
        return decision, {}

    limit = result.exceeded
    assert limit is not None
    reason = (
        f"Rate limited: at most {limit.max_requests} '{action.action_type}' request(s) "
        f"per {limit.window_seconds}s. Retry in {result.retry_after_seconds:.0f}s."
    )
    data = {
        "rate_limit": {"max_requests": limit.max_requests, "window_seconds": limit.window_seconds},
        "retry_after_seconds": result.retry_after_seconds,
        "policy_effect": decision.effect.value,
    }
    return replace(decision, effect=PolicyEffect.DENY, code=DecisionCode.RATE_LIMITED, reason=reason), data


async def submit_action_request(
    session: AsyncSession,
    limiter: RateLimiter,
    agent_id: uuid.UUID,
    action_type: str,
    payload: dict[str, Any],
) -> SubmitResult:
    """Decide on an action request and record it with exactly one decision event."""
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise AgentNotFoundError(str(agent_id))

    action = ActionContext(action_type, payload)
    decision = await decide_policy(session, agent, action)
    extra: dict[str, Any] = {}
    if decision.effect != PolicyEffect.DENY:
        decision, extra = await apply_rate_limit(session, limiter, agent, action, decision)

    request = ActionRequest(agent_id=agent.id, action_type=action_type, payload=payload)
    session.add(request)
    await session.flush()
    append_event(
        session,
        request,
        EVENT_FOR_EFFECT[decision.effect],
        decision.reason,
        FIREWALL_ACTOR,
        {
            "code": decision.code.value,
            "rule_id": str(decision.rule_id) if decision.rule_id else None,
            **extra,
        },
    )
    request_id = request.id
    await session.commit()
    return SubmitResult(request_id, decision)
