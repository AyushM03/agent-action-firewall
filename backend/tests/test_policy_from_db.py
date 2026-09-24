"""Snapshotting DB rows into the policy engine (Rule/AgentContext.from_model)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, PolicyEffect, PolicyRule
from app.policy import ActionContext, AgentContext, Rule, evaluate
from app.seed import seed


async def test_seeded_payment_policy_end_to_end(db: AsyncSession) -> None:
    await seed(db)  # commits into the rolled-back outer transaction

    agent_row = await db.scalar(select(Agent).where(Agent.name == "demo-payments-agent"))
    assert agent_row is not None
    rule_rows = (await db.scalars(select(PolicyRule))).all()

    agent = AgentContext.from_model(agent_row)
    rules = [Rule.from_model(r) for r in rule_rows]

    def decide(amount: int) -> PolicyEffect:
        return evaluate(agent, ActionContext("make_payment", {"amount": amount}), rules).effect

    assert decide(5000) == PolicyEffect.ALLOW
    assert decide(5001) == PolicyEffect.NEEDS_APPROVAL

    email_agent = AgentContext.from_model(
        await db.scalar(select(Agent).where(Agent.name == "demo-email-agent"))
    )
    # Not registered for payments, regardless of rules.
    assert evaluate(email_agent, ActionContext("make_payment", {"amount": 1}), rules).effect == PolicyEffect.DENY
    assert evaluate(email_agent, ActionContext("send_email", {"to": "a@b.com"}), rules).effect == PolicyEffect.ALLOW


async def test_from_model_snapshots_rule(db: AsyncSession) -> None:
    agent = Agent(name=f"test-agent-{uuid.uuid4().hex[:8]}", allowed_action_types=["make_payment"])
    db.add(agent)
    await db.flush()
    row = PolicyRule(
        agent_id=agent.id,
        action_type="make_payment",
        effect=PolicyEffect.NEEDS_APPROVAL,
        priority=5,
        conditions={"all": [{"field": "amount", "op": "gt", "value": 100}]},
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)

    snapshot = Rule.from_model(row)

    assert snapshot.effect is PolicyEffect.NEEDS_APPROVAL
    assert snapshot.priority == 5
    assert snapshot.conditions.all[0].op == "gt"
