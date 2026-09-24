import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RateLimit(Base):
    """At most `max_requests` of `action_type` per rolling `window_seconds`.

    `agent_id` NULL is the default for every agent. If an agent has any limits
    of its own for an action type, those replace the defaults (ADR-006).
    Counters live in Redis (ADR-003); this table is only configuration.
    """

    __tablename__ = "rate_limits"
    __table_args__ = (
        CheckConstraint("max_requests > 0", name="max_requests_positive"),
        CheckConstraint("window_seconds > 0", name="window_seconds_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(100), index=True)
    max_requests: Mapped[int] = mapped_column(Integer)
    window_seconds: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
