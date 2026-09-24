"""Seed demo agents, policy rules and rate limits for local development.

Idempotent: re-running only inserts rows that don't exist yet.
Usage (from backend/):  python -m app.seed
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session, engine
from app.models import Agent, PolicyEffect, PolicyRule, RateLimit

AGENTS = [
    {
        "name": "demo-email-agent",
        "description": "Demo agent that sends notification emails.",
        "allowed_action_types": ["send_email"],
    },
    {
        "name": "demo-payments-agent",
        "description": "Demo agent that issues test-mode payments and receipt emails.",
        "allowed_action_types": ["make_payment", "send_email"],
    },
]

# (agent name or None for a global rule, action_type, effect, priority, conditions, description)
RULES = [
    (None, "send_email", PolicyEffect.ALLOW, 0, {}, "Emails are allowed by default."),
    (None, "make_payment", PolicyEffect.DENY, 0, {}, "Payments are denied unless a more specific rule applies."),
    (
        "demo-payments-agent",
        "make_payment",
        PolicyEffect.NEEDS_APPROVAL,
        10,
        {},
        "Payments by the payments agent require human approval.",
    ),
    (
        "demo-payments-agent",
        "make_payment",
        PolicyEffect.ALLOW,
        20,
        {"all": [{"field": "amount", "op": "lte", "value": 5000}]},
        "Payments of $50.00 or less (amount in cents) are auto-allowed.",
    ),
]

# (agent name or None for the default, action_type, max_requests, window_seconds)
RATE_LIMITS = [
    (None, "send_email", 10, 60),
    (None, "make_payment", 5, 60),
    ("demo-payments-agent", "make_payment", 3, 60),
    ("demo-payments-agent", "make_payment", 20, 86400),
]


async def seed(session: AsyncSession) -> None:
    agents_by_name: dict[str, Agent] = {}
    for spec in AGENTS:
        agent = await session.scalar(select(Agent).where(Agent.name == spec["name"]))
        if agent is None:
            agent = Agent(**spec)
            session.add(agent)
            print(f"+ agent {spec['name']}")
        agents_by_name[spec["name"]] = agent
    await session.flush()

    for agent_name, action_type, effect, priority, conditions, description in RULES:
        agent_id = agents_by_name[agent_name].id if agent_name else None
        exists = await session.scalar(
            select(PolicyRule.id).where(
                PolicyRule.agent_id.is_(None) if agent_id is None else PolicyRule.agent_id == agent_id,
                PolicyRule.action_type == action_type,
                PolicyRule.effect == effect,
            )
        )
        if exists is None:
            session.add(
                PolicyRule(
                    agent_id=agent_id,
                    action_type=action_type,
                    effect=effect,
                    priority=priority,
                    conditions=conditions,
                    description=description,
                )
            )
            print(f"+ rule {agent_name or '*'} / {action_type} -> {effect}")

    for agent_name, action_type, max_requests, window_seconds in RATE_LIMITS:
        agent_id = agents_by_name[agent_name].id if agent_name else None
        exists = await session.scalar(
            select(RateLimit.id).where(
                RateLimit.agent_id.is_(None) if agent_id is None else RateLimit.agent_id == agent_id,
                RateLimit.action_type == action_type,
                RateLimit.window_seconds == window_seconds,
            )
        )
        if exists is None:
            session.add(
                RateLimit(
                    agent_id=agent_id,
                    action_type=action_type,
                    max_requests=max_requests,
                    window_seconds=window_seconds,
                )
            )
            print(f"+ rate limit {agent_name or '*'} / {action_type}: {max_requests} per {window_seconds}s")

    await session.commit()


async def main() -> None:
    engine.echo = False
    async with async_session() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
