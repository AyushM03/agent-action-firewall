"""least-privilege app role

Creates `aaf_app`, the group role the backend's login belongs to (SECURITY.md:
least-privilege DB credentials). It can read everything it needs and append to
the event store, but it cannot UPDATE, DELETE or TRUNCATE `audit_log` or
`action_requests`, and because it doesn't own any table it can't disable or
drop the append-only triggers either. No table grants DELETE: nothing in the
app removes rows.

The login itself (with its password) is created by the operator, not here, so
no credential ends up in a migration:
    CREATE ROLE aaf_backend LOGIN PASSWORD '...' IN ROLE aaf_app;

New tables need their own GRANT in the migration that creates them
(tests/test_db_privileges.py fails until they do).

Revision ID: 5c1e7a9d2f40
Revises: b852307924b1
Create Date: 2026-10-02 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5c1e7a9d2f40'
down_revision: Union[str, None] = 'b852307924b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "aaf_app"

GRANTS = {
    # Event store: append and read, nothing else.
    "audit_log": "SELECT, INSERT",
    "action_requests": "SELECT, INSERT",
    # Configuration: the app and its operator commands (seed, create-approver,
    # issue-agent-key) create and edit these, but never delete.
    "agents": "SELECT, INSERT, UPDATE",
    "approvers": "SELECT, INSERT, UPDATE",
    "policy_rules": "SELECT, INSERT, UPDATE",
    "rate_limits": "SELECT, INSERT, UPDATE",
}


def upgrade() -> None:
    # Roles are cluster-wide, so another database on the same server may have created it already.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    for table, privileges in GRANTS.items():
        op.execute(f"GRANT {privileges} ON {table} TO {APP_ROLE}")
    # audit_log.id is an identity column; inserting needs its sequence.
    op.execute(f"GRANT USAGE ON SEQUENCE audit_log_id_seq TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
    # Left in place: dropping it would fail while login roles still belong to it,
    # and it holds no privileges any more.
