"""Condition format for `policy_rules.conditions` and one evaluator per operator.

Stored JSON shape (all conditions must match for the rule to apply):

    {"all": [{"field": "amount", "op": "lte", "value": 5000},
             {"field": "to", "op": "email_domain_in", "value": ["example.com"]}]}

`{}` (no conditions) means the rule always applies. `field` is a dotted path
into the action request payload, e.g. "customer.country".
"""

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

Op = Literal[
    "eq", "neq", "lt", "lte", "gt", "gte", "in", "not_in", "email_domain_in", "email_domain_not_in"
]

NUMERIC_OPS = frozenset({"lt", "lte", "gt", "gte"})
LIST_OPS = frozenset({"in", "not_in"})
DOMAIN_OPS = frozenset({"email_domain_in", "email_domain_not_in"})


class ConditionError(Exception):
    """A condition couldn't be evaluated against the payload (missing field, wrong type)."""


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    op: Op
    value: Any

    @model_validator(mode="after")
    def check_value_type(self) -> "Condition":
        if self.op in NUMERIC_OPS and not is_number(self.value):
            raise ValueError(f"'{self.op}' needs a numeric value")
        if self.op in LIST_OPS and not isinstance(self.value, list):
            raise ValueError(f"'{self.op}' needs a list value")
        if self.op in DOMAIN_OPS and not (
            isinstance(self.value, list) and all(isinstance(d, str) for d in self.value)
        ):
            raise ValueError(f"'{self.op}' needs a list of domain strings")
        return self


class RuleConditions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    all: tuple[Condition, ...] = ()


def is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def resolve_field(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ConditionError(f"payload field '{path}' is missing")
        current = current[part]
    return current


def require_number(field: str, actual: Any) -> int | float:
    if not is_number(actual):
        raise ConditionError(f"payload field '{field}' must be a number")
    return actual


def email_domain(field: str, actual: Any) -> str:
    if not isinstance(actual, str) or actual.count("@") != 1:
        raise ConditionError(f"payload field '{field}' must be an email address")
    return actual.rsplit("@", 1)[1].lower()


def _eq(c: Condition, actual: Any) -> bool:
    return actual == c.value


def _neq(c: Condition, actual: Any) -> bool:
    return actual != c.value


def _lt(c: Condition, actual: Any) -> bool:
    return require_number(c.field, actual) < c.value


def _lte(c: Condition, actual: Any) -> bool:
    return require_number(c.field, actual) <= c.value


def _gt(c: Condition, actual: Any) -> bool:
    return require_number(c.field, actual) > c.value


def _gte(c: Condition, actual: Any) -> bool:
    return require_number(c.field, actual) >= c.value


def _in(c: Condition, actual: Any) -> bool:
    return actual in c.value


def _not_in(c: Condition, actual: Any) -> bool:
    return actual not in c.value


def _email_domain_in(c: Condition, actual: Any) -> bool:
    return email_domain(c.field, actual) in {d.lower() for d in c.value}


def _email_domain_not_in(c: Condition, actual: Any) -> bool:
    return email_domain(c.field, actual) not in {d.lower() for d in c.value}


OPERATORS: dict[str, Callable[[Condition, Any], bool]] = {
    "eq": _eq,
    "neq": _neq,
    "lt": _lt,
    "lte": _lte,
    "gt": _gt,
    "gte": _gte,
    "in": _in,
    "not_in": _not_in,
    "email_domain_in": _email_domain_in,
    "email_domain_not_in": _email_domain_not_in,
}


def conditions_match(conditions: RuleConditions, payload: dict[str, Any]) -> bool:
    """True if every condition holds. Raises ConditionError if one can't be evaluated."""
    return all(OPERATORS[c.op](c, resolve_field(payload, c.field)) for c in conditions.all)
