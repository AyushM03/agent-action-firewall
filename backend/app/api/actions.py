import uuid
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentAgent, DbSession, Executors, Limiter
from app.api.schemas import ExecutionOut
from app.models import PolicyEffect
from app.services.execution import submit_and_execute

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionRequestIn(BaseModel):
    action_type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionDecisionOut(BaseModel):
    request_id: uuid.UUID
    decision: PolicyEffect
    code: str
    reason: str
    # Present only when the decision was allow: what happened when the action ran.
    execution: ExecutionOut | None = None


@router.post("/request", status_code=status.HTTP_201_CREATED)
async def request_action(
    body: ActionRequestIn, agent: CurrentAgent, db: DbSession, limiter: Limiter, executors: Executors
) -> ActionDecisionOut:
    """Submit an action. Every call is recorded; allowed actions are executed immediately."""
    result, execution = await submit_and_execute(db, limiter, executors, agent.id, body.action_type, body.payload)
    return ActionDecisionOut(
        request_id=result.request_id,
        decision=result.decision.effect,
        code=result.decision.code,
        reason=result.decision.reason,
        execution=ExecutionOut.from_event(execution),
    )
