"""Policy engine: a pure function from (agent, action, rules) to a decision.

No DB access, no network, no mutation of inputs. Callers load the agent and
rules, then pass plain snapshots in (see `Rule.from_model`).

Precedence (ADR-005):
1. Inactive agent -> DENY.
2. Action type not in the agent's allowed_action_types -> DENY.
3. Of the active rules for this action type that apply to this agent, the
   first whose conditions match wins, ordered by: higher priority, then
   agent-specific over global, then most restrictive effect.
4. A rule whose conditions can't be evaluated -> DENY (fail closed).
5. No matching rule -> DENY (default deny).
"""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from app.models.enums import PolicyEffect
from app.policy.conditions import ConditionError, RuleConditions, conditions_match

if TYPE_CHECKING:
    from app.models import Agent, PolicyRule


class DecisionCode(StrEnum):
    RULE_MATCHED = "rule_matched"
    AGENT_INACTIVE = "agent_inactive"
    ACTION_NOT_PERMITTED = "action_not_permitted"
    NO_MATCHING_RULE = "no_matching_rule"
    POLICY_ERROR = "policy_error"


# Lower number = more restrictive; used to break exact ties safely.
RESTRICTIVENESS = {PolicyEffect.DENY: 0, PolicyEffect.NEEDS_APPROVAL: 1, PolicyEffect.ALLOW: 2}


@dataclass(frozen=True)
class AgentContext:
    id: uuid.UUID
    is_active: bool
    allowed_action_types: frozenset[str]

    @classmethod
    def from_model(cls, agent: "Agent") -> "AgentContext":
        return cls(agent.id, agent.is_active, frozenset(agent.allowed_action_types))


@dataclass(frozen=True)
class ActionContext:
    action_type: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Rule:
    id: uuid.UUID
    agent_id: uuid.UUID | None
    action_type: str
    effect: PolicyEffect
    conditions: RuleConditions = RuleConditions()
    priority: int = 0
    is_active: bool = True

    @classmethod
    def from_model(cls, rule: "PolicyRule") -> "Rule":
        """Snapshot a DB row. Raises pydantic.ValidationError on malformed conditions."""
        return cls(
            id=rule.id,
            agent_id=rule.agent_id,
            action_type=rule.action_type,
            effect=PolicyEffect(rule.effect),
            conditions=RuleConditions.model_validate(rule.conditions),
            priority=rule.priority,
            is_active=rule.is_active,
        )


@dataclass(frozen=True)
class Decision:
    effect: PolicyEffect
    code: DecisionCode
    reason: str
    rule_id: uuid.UUID | None = None


def deny(code: DecisionCode, reason: str, rule_id: uuid.UUID | None = None) -> Decision:
    return Decision(PolicyEffect.DENY, code, reason, rule_id)


def applicable_rules(agent: AgentContext, action: ActionContext, rules: Iterable[Rule]) -> list[Rule]:
    candidates = [
        r
        for r in rules
        if r.is_active
        and r.action_type == action.action_type
        and (r.agent_id is None or r.agent_id == agent.id)
    ]
    return sorted(
        candidates,
        key=lambda r: (-r.priority, r.agent_id is None, RESTRICTIVENESS[r.effect]),
    )


def evaluate(agent: AgentContext, action: ActionContext, rules: Iterable[Rule]) -> Decision:
    if not agent.is_active:
        return deny(DecisionCode.AGENT_INACTIVE, "Agent is deactivated.")

    if action.action_type not in agent.allowed_action_types:
        return deny(
            DecisionCode.ACTION_NOT_PERMITTED,
            f"Agent is not registered for action type '{action.action_type}'.",
        )

    payload = dict(action.payload)
    for rule in applicable_rules(agent, action, rules):
        try:
            matched = conditions_match(rule.conditions, payload)
        except ConditionError as exc:
            return deny(DecisionCode.POLICY_ERROR, f"Rule could not be evaluated: {exc}.", rule.id)
        if matched:
            scope = "agent-specific" if rule.agent_id else "global"
            return Decision(
                rule.effect,
                DecisionCode.RULE_MATCHED,
                f"Matched {scope} rule (priority {rule.priority}): {rule.effect}.",
                rule.id,
            )

    return deny(
        DecisionCode.NO_MATCHING_RULE,
        f"No policy rule allows '{action.action_type}' for this agent (default deny).",
    )
