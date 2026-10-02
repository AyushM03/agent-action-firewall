"""Creating approvers and issuing agent API keys (used by `python -m app.manage`)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import DUMMY_PASSWORD_HASH, generate_api_key, hash_api_key, hash_password, verify_password
from app.models import Agent, Approver


class AccountError(Exception):
    pass


async def create_approver(session: AsyncSession, username: str, password: str) -> Approver:
    if await session.scalar(select(Approver.id).where(Approver.username == username)):
        raise AccountError(f"Approver '{username}' already exists.")
    approver = Approver(username=username, password_hash=hash_password(password))
    session.add(approver)
    await session.commit()
    return approver


async def reset_approver_password(session: AsyncSession, username: str, password: str) -> Approver:
    """Set a new password for an existing approver. Their active/inactive status is left unchanged."""
    approver = await session.scalar(select(Approver).where(Approver.username == username))
    if approver is None:
        raise AccountError(f"No approver named '{username}'.")
    approver.password_hash = hash_password(password)
    await session.commit()
    return approver


async def authenticate_approver(session: AsyncSession, username: str, password: str) -> Approver | None:
    approver = await session.scalar(select(Approver).where(Approver.username == username))
    if approver is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, approver.password_hash) or not approver.is_active:
        return None
    return approver


async def issue_agent_key(session: AsyncSession, agent_name: str) -> str:
    """Give the agent a new API key, replacing any previous one. Returns the plaintext key."""
    agent = await session.scalar(select(Agent).where(Agent.name == agent_name))
    if agent is None:
        raise AccountError(f"No agent named '{agent_name}'.")
    api_key = generate_api_key()
    agent.api_key_hash = hash_api_key(api_key)
    await session.commit()
    return api_key
