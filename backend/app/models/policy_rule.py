import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import PolicyEffect, sql_in_list


class PolicyRule(Base):
    """A rule mapping an action type to an effect.

    `agent_id` NULL means the rule applies to every agent. `conditions` holds
    rule-specific parameters (format defined by the policy engine, Phase 3).
    Higher `priority` wins when several rules match.
    """

    __tablename__ = "policy_rules"
    __table_args__ = (
        CheckConstraint(f"effect IN ({sql_in_list(PolicyEffect)})", name="effect_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(100), index=True)
    effect: Mapped[str] = mapped_column(String(20))
    conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
