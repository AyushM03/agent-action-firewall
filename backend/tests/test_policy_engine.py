"""Policy engine tests (TEST_PLAN.md: Policy Engine). Pure — no DB or Redis needed."""

import copy
import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.models import PolicyEffect
from app.policy import ActionContext, AgentContext, DecisionCode, Rule, RuleConditions, evaluate
from app.seed import RULES as SEED_RULES

AGENT = AgentContext(uuid.uuid4(), True, frozenset({"send_email", "make_payment"}))
OTHER_AGENT_ID = uuid.uuid4()


def rule(
    effect: PolicyEffect,
    action_type: str = "make_payment",
    *,
    agent_id: uuid.UUID | None = None,
    priority: int = 0,
    conditions: dict[str, Any] | None = None,
    is_active: bool = True,
) -> Rule:
    return Rule(
        id=uuid.uuid4(),
        agent_id=agent_id,
        action_type=action_type,
        effect=effect,
        conditions=RuleConditions.model_validate(conditions or {}),
        priority=priority,
        is_active=is_active,
    )


def when(field: str, op: str, value: Any) -> dict[str, Any]:
    return {"all": [{"field": field, "op": op, "value": value}]}


def payment(**payload: Any) -> ActionContext:
    return ActionContext("make_payment", payload)


# --- Basic effects -----------------------------------------------------------


def test_allow_rule_allows() -> None:
    r = rule(PolicyEffect.ALLOW)
    decision = evaluate(AGENT, payment(amount=100), [r])
    assert decision.effect == PolicyEffect.ALLOW
    assert decision.code == DecisionCode.RULE_MATCHED
    assert decision.rule_id == r.id


def test_deny_rule_denies_with_reason() -> None:
    r = rule(PolicyEffect.DENY)
    decision = evaluate(AGENT, payment(amount=100), [r])
    assert decision.effect == PolicyEffect.DENY
    assert decision.rule_id == r.id
    assert decision.reason


def test_needs_approval_rule_is_queued_not_allowed() -> None:
    decision = evaluate(AGENT, payment(amount=100), [rule(PolicyEffect.NEEDS_APPROVAL)])
    assert decision.effect == PolicyEffect.NEEDS_APPROVAL


def test_no_matching_rule_is_default_deny() -> None:
    decision = evaluate(AGENT, payment(amount=100), [rule(PolicyEffect.ALLOW, "send_email")])
    assert decision.effect == PolicyEffect.DENY
    assert decision.code == DecisionCode.NO_MATCHING_RULE


# --- Agent checks ------------------------------------------------------------


def test_inactive_agent_is_denied_even_with_allow_rule() -> None:
    inactive = AgentContext(AGENT.id, False, AGENT.allowed_action_types)
    decision = evaluate(inactive, payment(amount=1), [rule(PolicyEffect.ALLOW)])
    assert decision.effect == PolicyEffect.DENY
    assert decision.code == DecisionCode.AGENT_INACTIVE


def test_unregistered_action_type_is_denied_even_with_allow_rule() -> None:
    email_only = AgentContext(AGENT.id, True, frozenset({"send_email"}))
    decision = evaluate(email_only, payment(amount=1), [rule(PolicyEffect.ALLOW)])
    assert decision.effect == PolicyEffect.DENY
    assert decision.code == DecisionCode.ACTION_NOT_PERMITTED


# --- Rule selection ----------------------------------------------------------


def test_inactive_rule_is_ignored() -> None:
    rules = [rule(PolicyEffect.ALLOW, is_active=False)]
    assert evaluate(AGENT, payment(amount=1), rules).code == DecisionCode.NO_MATCHING_RULE


def test_other_agents_rule_is_ignored() -> None:
    rules = [rule(PolicyEffect.ALLOW, agent_id=OTHER_AGENT_ID)]
    assert evaluate(AGENT, payment(amount=1), rules).code == DecisionCode.NO_MATCHING_RULE


def test_higher_priority_wins() -> None:
    rules = [rule(PolicyEffect.DENY, priority=0), rule(PolicyEffect.ALLOW, priority=10)]
    assert evaluate(AGENT, payment(amount=1), rules).effect == PolicyEffect.ALLOW

    rules = [rule(PolicyEffect.DENY, priority=10), rule(PolicyEffect.ALLOW, priority=0)]
    assert evaluate(AGENT, payment(amount=1), rules).effect == PolicyEffect.DENY


def test_agent_specific_rule_beats_global_at_same_priority() -> None:
    rules = [rule(PolicyEffect.DENY), rule(PolicyEffect.ALLOW, agent_id=AGENT.id)]
    assert evaluate(AGENT, payment(amount=1), rules).effect == PolicyEffect.ALLOW

    rules = [rule(PolicyEffect.ALLOW), rule(PolicyEffect.DENY, agent_id=AGENT.id)]
    assert evaluate(AGENT, payment(amount=1), rules).effect == PolicyEffect.DENY


def test_exact_tie_resolves_to_most_restrictive() -> None:
    rules = [
        rule(PolicyEffect.ALLOW),
        rule(PolicyEffect.NEEDS_APPROVAL),
        rule(PolicyEffect.DENY),
    ]
    assert evaluate(AGENT, payment(amount=1), rules).effect == PolicyEffect.DENY
    assert evaluate(AGENT, payment(amount=1), rules[:2]).effect == PolicyEffect.NEEDS_APPROVAL


def test_non_matching_higher_priority_rule_falls_through() -> None:
    rules = [
        rule(PolicyEffect.ALLOW, priority=20, conditions=when("amount", "lte", 5000)),
        rule(PolicyEffect.NEEDS_APPROVAL, priority=10),
    ]
    assert evaluate(AGENT, payment(amount=4000), rules).effect == PolicyEffect.ALLOW
    assert evaluate(AGENT, payment(amount=9000), rules).effect == PolicyEffect.NEEDS_APPROVAL


# --- Condition operators: one allow case and one deny case each ---------------
# Setup: a conditioned DENY rule on top of a baseline ALLOW. The condition
# matching -> DENY; not matching -> falls through to ALLOW.

OPERATOR_CASES = [
    # op, value, payload that matches (-> deny), payload that doesn't (-> allow)
    ("eq", "EUR", {"currency": "EUR"}, {"currency": "USD"}),
    ("neq", "USD", {"currency": "EUR"}, {"currency": "USD"}),
    ("lt", 100, {"amount": 99}, {"amount": 100}),
    ("lte", 100, {"amount": 100}, {"amount": 101}),
    ("gt", 5000, {"amount": 5001}, {"amount": 5000}),
    ("gte", 5000, {"amount": 5000}, {"amount": 4999}),
    ("in", ["KP", "IR"], {"country": "KP"}, {"country": "US"}),
    ("not_in", ["US", "IN"], {"country": "KP"}, {"country": "IN"}),
    ("email_domain_in", ["evil.com"], {"to": "x@Evil.com"}, {"to": "x@example.com"}),
    ("email_domain_not_in", ["example.com"], {"to": "x@evil.com"}, {"to": "x@example.com"}),
]


@pytest.mark.parametrize("op,value,matching,non_matching", OPERATOR_CASES, ids=[c[0] for c in OPERATOR_CASES])
def test_operator(op: str, value: Any, matching: dict[str, Any], non_matching: dict[str, Any]) -> None:
    field = next(iter(matching))
    rules = [
        rule(PolicyEffect.DENY, priority=10, conditions=when(field, op, value)),
        rule(PolicyEffect.ALLOW),
    ]
    assert evaluate(AGENT, payment(**matching), rules).effect == PolicyEffect.DENY
    assert evaluate(AGENT, payment(**non_matching), rules).effect == PolicyEffect.ALLOW


def test_all_conditions_must_match() -> None:
    conditions = {
        "all": [
            {"field": "amount", "op": "lte", "value": 5000},
            {"field": "currency", "op": "eq", "value": "USD"},
        ]
    }
    rules = [rule(PolicyEffect.ALLOW, conditions=conditions)]
    assert evaluate(AGENT, payment(amount=100, currency="USD"), rules).effect == PolicyEffect.ALLOW
    assert evaluate(AGENT, payment(amount=100, currency="EUR"), rules).effect == PolicyEffect.DENY


def test_nested_field_path() -> None:
    rules = [rule(PolicyEffect.ALLOW, conditions=when("customer.country", "eq", "US"))]
    assert evaluate(AGENT, payment(customer={"country": "US"}), rules).effect == PolicyEffect.ALLOW
    assert evaluate(AGENT, payment(customer={"country": "FR"}), rules).effect == PolicyEffect.DENY


# --- Fail closed -------------------------------------------------------------


@pytest.mark.parametrize(
    "conditions,payload",
    [
        (when("amount", "gt", 5000), {}),  # missing field
        (when("amount", "gt", 5000), {"amount": "lots"}),  # wrong type
        (when("amount", "gt", 5000), {"amount": True}),  # bool is not a number
        (when("to", "email_domain_in", ["evil.com"]), {"to": "not-an-email"}),
    ],
    ids=["missing-field", "string-amount", "bool-amount", "bad-email"],
)
def test_unevaluable_condition_fails_closed(conditions: dict[str, Any], payload: dict[str, Any]) -> None:
    # A deny rule that can't be checked must not silently let the action through.
    rules = [rule(PolicyEffect.DENY, priority=10, conditions=conditions), rule(PolicyEffect.ALLOW)]
    decision = evaluate(AGENT, payment(**payload), rules)
    assert decision.effect == PolicyEffect.DENY
    assert decision.code == DecisionCode.POLICY_ERROR


# --- Purity ------------------------------------------------------------------


def test_evaluate_does_not_mutate_inputs_and_is_deterministic() -> None:
    payload = {"amount": 9000, "customer": {"country": "US"}}
    action = payment(**payload)
    rules = [
        rule(PolicyEffect.ALLOW, priority=20, conditions=when("amount", "lte", 5000)),
        rule(PolicyEffect.NEEDS_APPROVAL, priority=10, conditions=when("customer.country", "eq", "US")),
    ]
    before = copy.deepcopy((action, rules))

    first = evaluate(AGENT, action, rules)
    second = evaluate(AGENT, action, list(reversed(rules)))

    assert first == second
    assert (action, rules) == before


# --- Condition format validation ----------------------------------------------


@pytest.mark.parametrize(
    "conditions",
    [
        {"any": []},  # unknown top-level key
        {"all": [{"field": "amount", "op": "between", "value": 1}]},  # unknown op
        {"all": [{"field": "amount", "op": "gt", "value": "5000"}]},  # non-numeric
        {"all": [{"field": "amount", "op": "gt", "value": True}]},  # bool
        {"all": [{"field": "country", "op": "in", "value": "US"}]},  # not a list
        {"all": [{"field": "to", "op": "email_domain_in", "value": [1]}]},  # not strings
        {"all": [{"field": "amount", "op": "gt"}]},  # missing value
    ],
)
def test_malformed_conditions_are_rejected(conditions: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RuleConditions.model_validate(conditions)


def test_seed_rule_conditions_are_valid() -> None:
    for *_, conditions, _description in SEED_RULES:
        RuleConditions.model_validate(conditions)
