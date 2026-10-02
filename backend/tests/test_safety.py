"""Startup safety checks (app/core/safety.py): unsafe settings refuse to start outside development."""

import logging
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import DEFAULT_JWT_SECRET, Settings, settings
from app.core.db import engine as app_engine
from app.core.safety import UnsafeConfigurationError, check_database_role, check_settings, enforce_safe_configuration

STRONG_SECRET = "x" * 48


@pytest.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """The backend's own login, on a fresh engine (the app's pooled engine is bound to another event loop)."""
    backend = create_async_engine(settings.database_url, poolclass=NullPool)
    yield backend
    await backend.dispose()


def test_placeholder_or_short_jwt_secret_is_flagged() -> None:
    assert check_settings(Settings(jwt_secret=DEFAULT_JWT_SECRET))
    assert check_settings(Settings(jwt_secret="short"))
    assert check_settings(Settings(jwt_secret=STRONG_SECRET)) == []


async def test_owner_or_superuser_login_is_flagged() -> None:
    owner = create_async_engine(settings.owner_database_url, poolclass=NullPool)
    try:
        [problem] = await check_database_role(owner)
    finally:
        await owner.dispose()
    assert "could disable its append-only triggers" in problem


async def test_unsafe_configuration_refuses_to_start_outside_development(engine: AsyncEngine) -> None:
    unsafe = Settings(environment="production", jwt_secret=DEFAULT_JWT_SECRET)
    with pytest.raises(UnsafeConfigurationError, match="JWT_SECRET"):
        await enforce_safe_configuration(unsafe, engine)


async def test_unsafe_configuration_only_warns_in_development(
    engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.core.safety"):
        await enforce_safe_configuration(Settings(environment="development", jwt_secret="short"), engine)
    assert "JWT_SECRET" in caplog.text


async def test_safe_configuration_starts_in_production(engine: AsyncEngine) -> None:
    await enforce_safe_configuration(Settings(environment="production", jwt_secret=STRONG_SECRET), engine)


def test_sql_parameters_are_never_logged() -> None:
    assert app_engine.sync_engine.hide_parameters is True
