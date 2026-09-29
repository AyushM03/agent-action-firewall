import uuid
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentAgent, DbSession, Limiter
from app.models import PolicyEffect
from app.services.firewall import submit_action_request

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionRequestIn(BaseModel):
    action_type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionDecisionOut(BaseModel):
    request_id: uuid.UUID
    decision: PolicyEffect
    code: str
    reason: str


@router.post("/request", status_code=status.HTTP_201_CREATED)
async def request_action(
    body: ActionRequestIn, agent: CurrentAgent, db: DbSession, limiter: Limiter
) -> ActionDecisionOut:
    """Submit an action for a decision. Every call is recorded, whatever the outcome."""
    result = await submit_action_request(db, limiter, agent.id, body.action_type, body.payload)
    return ActionDecisionOut(
        request_id=result.request_id,
        decision=result.decision.effect,
        code=result.decision.code,
        reason=result.decision.reason,
    )
