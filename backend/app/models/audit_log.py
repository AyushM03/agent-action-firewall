import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import DECISION_EVENT_TYPES, AuditEventType, sql_in_list


class AuditEvent(Base):
    """One immutable entry in the append-only audit log (ADR-001).

    UPDATE, DELETE and TRUNCATE are rejected by DB triggers — see the initial
    Alembic migration. `agent_id` and `action_type` are copied from the request
    so the log can be filtered without joins.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(f"event_type IN ({sql_in_list(AuditEventType)})", name="event_type_valid"),
        # Every action request gets exactly one firewall decision event.
        Index(
            "uq_audit_log_one_decision_per_request",
            "action_request_id",
            unique=True,
            postgresql_where=text(
                "event_type IN ({})".format(", ".join(f"'{e.value}'" for e in sorted(DECISION_EVENT_TYPES)))
            ),
        ),
        Index("ix_audit_log_agent_created", "agent_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    action_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("action_requests.id"), index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"))
    action_type: Mapped[str] = mapped_column(String(100), index=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    reason: Mapped[str] = mapped_column(Text)
    # Who produced the event: "firewall", "executor:gmail", "approver:<username>", ...
    actor: Mapped[str] = mapped_column(String(100))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
