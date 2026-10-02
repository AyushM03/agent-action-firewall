"""Startup checks for settings that would quietly undo the firewall's guarantees.

Outside development the app refuses to start if any of them fail (fail closed,
like the policy engine); in development they are logged as warnings so a fresh
checkout still runs.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import DEFAULT_JWT_SECRET, Settings

logger = logging.getLogger(__name__)

MIN_JWT_SECRET_LENGTH = 32


class UnsafeConfigurationError(RuntimeError):
    pass


def check_settings(settings: Settings) -> list[str]:
    problems = []
    if settings.jwt_secret == DEFAULT_JWT_SECRET or len(settings.jwt_secret) < MIN_JWT_SECRET_LENGTH:
        problems.append(
            f"JWT_SECRET is the placeholder or shorter than {MIN_JWT_SECRET_LENGTH} characters, "
            "so approver tokens could be forged."
        )
    return problems


async def check_database_role(engine: AsyncEngine) -> list[str]:
    """The backend must not be able to rewrite history: no superuser, and no owner rights over audit_log
    (an owner can disable the append-only triggers)."""
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT r.rolsuper, pg_has_role(current_user, t.tableowner, 'MEMBER'), current_user "
                    "FROM pg_roles r, pg_tables t "
                    "WHERE r.rolname = current_user AND t.schemaname = 'public' AND t.tablename = 'audit_log'"
                )
            )
        ).one_or_none()
    if row is None:
        return ["audit_log table not found; run `alembic upgrade head`."]
    is_superuser, owns_audit_log, user = row
    if is_superuser or owns_audit_log:
        return [
            f"The backend connects to Postgres as '{user}', which "
            f"{'is a superuser' if is_superuser else 'owns audit_log'} and could disable its append-only "
            "triggers. Set DATABASE_URL to a login in the aaf_app role (see backend/.env.example)."
        ]
    return []


async def enforce_safe_configuration(settings: Settings, engine: AsyncEngine) -> None:
    problems = check_settings(settings) + await check_database_role(engine)
    if not problems:
        return
    if settings.environment == "development":
        for problem in problems:
            logger.warning("Unsafe configuration (allowed in development): %s", problem)
        return
    raise UnsafeConfigurationError("Refusing to start:\n- " + "\n- ".join(problems))
