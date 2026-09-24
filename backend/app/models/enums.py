from enum import StrEnum


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_APPROVAL = "needs_approval"


class AuditEventType(StrEnum):
    # Firewall decision — exactly one of these per action request.
    ALLOWED = "allowed"
    DENIED = "denied"
    NEEDS_APPROVAL = "needs_approval"
    # Human approver decision on a NEEDS_APPROVAL request.
    APPROVED = "approved"
    REJECTED = "rejected"
    # Executor outcome, only ever after ALLOWED or APPROVED.
    EXECUTED = "executed"
    EXECUTION_FAILED = "execution_failed"


DECISION_EVENT_TYPES = frozenset(
    {AuditEventType.ALLOWED, AuditEventType.DENIED, AuditEventType.NEEDS_APPROVAL}
)


def sql_in_list(enum_cls: type[StrEnum]) -> str:
    """Render an enum's values as a SQL IN list for CHECK constraints."""
    return ", ".join(f"'{member.value}'" for member in enum_cls)
