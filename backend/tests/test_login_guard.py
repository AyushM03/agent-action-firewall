"""Brute-force protection on POST /auth/login (app/services/login_guard.py)."""

from typing import Any

import pytest
from httpx import AsyncClient
from redis import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ratelimit import RateLimiter
from app.services.accounts import create_approver
from app.services.login_guard import LOGIN_LIMITS
from tests.conftest import FakeClock
from tests.test_api import PASSWORD, unique_name

MAX_ATTEMPTS = LOGIN_LIMITS[0].max_requests


async def login(client: AsyncClient, username: str, password: str):
    # Every test request comes from the same client address (httpx's ASGI transport).
    return await client.post("/auth/login", json={"username": username, "password": password})


async def test_repeated_wrong_passwords_are_throttled(db: AsyncSession, client: AsyncClient) -> None:
    username = unique_name("approver")
    await create_approver(db, username, PASSWORD)

    statuses = [(await login(client, username, "wrong-password")).status_code for _ in range(MAX_ATTEMPTS)]
    blocked = await login(client, username, "wrong-password")

    assert statuses == [401] * MAX_ATTEMPTS
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


async def test_throttled_account_rejects_even_the_right_password(db: AsyncSession, client: AsyncClient) -> None:
    """Otherwise the 429/401 difference would tell an attacker when a guess was right."""
    username = unique_name("approver")
    await create_approver(db, username, PASSWORD)
    for _ in range(MAX_ATTEMPTS):
        await login(client, username, "wrong-password")

    assert (await login(client, username, PASSWORD)).status_code == 429


async def test_throttle_lifts_after_the_window(db: AsyncSession, client: AsyncClient, clock: FakeClock) -> None:
    username = unique_name("approver")
    await create_approver(db, username, PASSWORD)
    for _ in range(MAX_ATTEMPTS):
        await login(client, username, "wrong-password")

    clock.advance(LOGIN_LIMITS[0].window_seconds + 1)

    assert (await login(client, username, PASSWORD)).status_code == 200


async def test_username_case_and_spacing_do_not_reset_the_count(db: AsyncSession, client: AsyncClient) -> None:
    username = unique_name("approver")
    await create_approver(db, username, PASSWORD)
    for i in range(MAX_ATTEMPTS):
        await login(client, username.upper() if i % 2 else f" {username} ", "wrong-password")

    assert (await login(client, username, PASSWORD)).status_code == 429


async def test_guessing_across_many_usernames_is_throttled_per_client(client: AsyncClient) -> None:
    for _ in range(MAX_ATTEMPTS):
        await login(client, unique_name("nobody"), "guess")

    assert (await login(client, unique_name("nobody"), "guess")).status_code == 429


async def test_login_fails_closed_when_redis_is_down(
    db: AsyncSession, client: AsyncClient, limiter: RateLimiter, monkeypatch: pytest.MonkeyPatch
) -> None:
    username = unique_name("approver")
    await create_approver(db, username, PASSWORD)

    async def broken(*args: Any, **kwargs: Any) -> None:
        raise RedisError("connection refused")

    monkeypatch.setattr(limiter, "hit_subject", broken)

    assert (await login(client, username, PASSWORD)).status_code == 503
