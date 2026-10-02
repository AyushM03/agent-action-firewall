"""The backend's least-privilege DB role (SECURITY.md: Database).

Most tests switch to `aaf_app` inside the rolled-back owner transaction, so they
check the role's grants regardless of which login runs the suite.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.db import Base
from app.core.safety import check_database_role
from app.models import ActionRequest, Agent, AuditEvent, AuditEventType

APP_ROLE = "aaf_app"
ALL_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
EXPECTED = {
    "audit_log": {"SELECT", "INSERT"},
    "action_requests": {"SELECT", "INSERT"},
    "agents": {"SELECT", "INSERT", "UPDATE"},
    "approvers": {"SELECT", "INSERT", "UPDATE"},
    "policy_rules": {"SELECT", "INSERT", "UPDATE"},
    "rate_limits": {"SELECT", "INSERT", "UPDATE"},
}


@pytest.fixture
async def as_app(owner_db: AsyncSession) -> AsyncSession:
    """The owner's rolled-back session, acting as the backend's role for the rest of the test."""
    await owner_db.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
    return owner_db


async def expect_denied(db: AsyncSession, sql: str) -> str:
    with pytest.raises(DBAPIError) as exc_info:
        async with db.begin_nested():
            await db.execute(text(sql))
    return str(exc_info.value.orig).lower()


async def test_every_table_has_exactly_the_expected_privileges(owner_db: AsyncSession) -> None:
    tables = {table.name for table in Base.metadata.sorted_tables}
    # A new table must be added here (and granted in its migration) on purpose.
    assert tables == set(EXPECTED)
    for table in sorted(tables):
        granted = {
            privilege
            for privilege in ALL_PRIVILEGES
            if await owner_db.scalar(text("SELECT has_table_privilege(:role, :table, :p)"), {"role": APP_ROLE, "table": table, "p": privilege})
        }
        assert granted == EXPECTED[table], table


async def test_role_cannot_log_in_or_escalate(owner_db: AsyncSession) -> None:
    row = (
        await owner_db.execute(
            text("SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}
        )
    ).one()
    assert tuple(row) == (False, False, False, False)


@pytest.mark.parametrize("table", ["audit_log", "action_requests"])
@pytest.mark.parametrize(
    "statement",
    ["UPDATE {table} SET created_at = now()", "DELETE FROM {table}", "TRUNCATE {table} CASCADE"],
)
async def test_event_store_cannot_be_rewritten(as_app: AsyncSession, table: str, statement: str) -> None:
    assert "permission denied" in await expect_denied(as_app, statement.format(table=table))


@pytest.mark.parametrize(
    "statement",
    [
        "ALTER TABLE audit_log DISABLE TRIGGER ALL",
        "DROP FUNCTION reject_mutation() CASCADE",
        "DROP INDEX uq_audit_log_one_decision_per_request",
        "ALTER TABLE audit_log OWNER TO aaf_app",
    ],
)
async def test_append_only_safeguards_cannot_be_removed(as_app: AsyncSession, statement: str) -> None:
    message = await expect_denied(as_app, statement)
    assert "must be owner" in message or "permission denied" in message


async def test_no_rows_can_be_deleted_anywhere(as_app: AsyncSession) -> None:
    for table in EXPECTED:
        assert "permission denied" in await expect_denied(as_app, f"DELETE FROM {table}")


async def test_role_cannot_create_tables(as_app: AsyncSession) -> None:
    assert "permission denied" in await expect_denied(as_app, "CREATE TABLE public.shadow_audit_log (id int)")


async def test_role_can_do_everything_the_firewall_needs(as_app: AsyncSession) -> None:
    agent = Agent(name=f"test-agent-{uuid.uuid4().hex[:8]}", allowed_action_types=["send_email"])
    as_app.add(agent)
    await as_app.flush()
    agent.is_active = False  # config tables can be edited
    request = ActionRequest(agent_id=agent.id, action_type="send_email", payload={})
    as_app.add(request)
    await as_app.flush()
    event = AuditEvent(
        action_request_id=request.id,
        agent_id=agent.id,
        action_type="send_email",
        event_type=AuditEventType.DENIED,
        reason="test",
        actor="firewall",
    )
    as_app.add(event)
    await as_app.flush()

    assert event.id is not None
    assert await as_app.scalar(text("SELECT count(*) FROM audit_log WHERE action_request_id = :id"), {"id": request.id}) == 1


async def test_backend_login_is_least_privilege() -> None:
    """DATABASE_URL in backend/.env must be a login in aaf_app, not the owner or a superuser."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        assert await check_database_role(engine) == []
    finally:
        await engine.dispose()
