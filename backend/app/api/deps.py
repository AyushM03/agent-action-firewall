"""Shared route dependencies: DB session, rate limiter, and the two kinds of caller."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import redis_client
from app.core.security import decode_access_token, hash_api_key
from app.models import Agent, Approver
from app.ratelimit import RateLimiter

DbSession = Annotated[AsyncSession, Depends(get_db)]

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Agent API key")
bearer = HTTPBearer(auto_error=False, description="Approver JWT from POST /auth/login")


def get_limiter() -> RateLimiter:
    return RateLimiter(redis_client)


async def get_current_agent(db: DbSession, api_key: Annotated[str | None, Depends(api_key_header)]) -> Agent:
    """The agent is identified by its key alone, never by an ID in the request body."""
    agent = None
    if api_key:
        agent = await db.scalar(select(Agent).where(Agent.api_key_hash == hash_api_key(api_key)))
    if agent is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Missing or invalid API key.", headers={"WWW-Authenticate": "ApiKey"}
        )
    return agent


async def get_current_approver(
    db: DbSession, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> Approver:
    """Checked against the DB on every call, so deactivating an approver takes effect immediately."""
    username = decode_access_token(credentials.credentials) if credentials else None
    approver = None
    if username is not None:
        approver = await db.scalar(select(Approver).where(Approver.username == username, Approver.is_active))
    if approver is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Not authenticated.", headers={"WWW-Authenticate": "Bearer"}
        )
    return approver


Limiter = Annotated[RateLimiter, Depends(get_limiter)]
CurrentAgent = Annotated[Agent, Depends(get_current_agent)]
CurrentApprover = Annotated[Approver, Depends(get_current_approver)]
