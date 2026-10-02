import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentApprover, DbSession
from app.services import audit

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentActivityOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    is_active: bool
    allowed_action_types: list[str]
    # Whether an API key has been issued — never the key or its hash.
    has_api_key: bool
    total_requests: int
    pending_approvals: int
    event_counts: dict[str, int]
    last_activity_at: datetime | None


@router.get("")
async def list_agents(db: DbSession, _: CurrentApprover) -> list[AgentActivityOut]:
    return [
        AgentActivityOut(
            id=item.agent.id,
            name=item.agent.name,
            description=item.agent.description,
            is_active=item.agent.is_active,
            allowed_action_types=item.agent.allowed_action_types,
            has_api_key=item.agent.api_key_hash is not None,
            total_requests=item.total_requests,
            pending_approvals=item.pending_approvals,
            event_counts=item.event_counts,
            last_activity_at=item.last_activity_at,
        )
        for item in await audit.list_agent_activity(db)
    ]
