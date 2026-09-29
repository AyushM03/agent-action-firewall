from typing import Any

from pydantic import BaseModel

from app.models import AuditEvent


class ExecutionOut(BaseModel):
    """The executor's outcome: `executed` (with the Gmail/Stripe ID) or `execution_failed`."""

    status: str
    reason: str
    external_id: str | None = None
    code: str | None = None

    @classmethod
    def from_event(cls, event: AuditEvent | None) -> "ExecutionOut | None":
        if event is None:
            return None
        data: dict[str, Any] = event.data
        return cls(status=event.event_type, reason=event.reason, external_id=data.get("external_id"), code=data.get("code"))
