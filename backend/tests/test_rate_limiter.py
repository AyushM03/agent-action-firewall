"""Rate limiter tests (TEST_PLAN.md: Rate Limiting). Needs Redis running."""

import asyncio
import uuid
from types import SimpleNamespace

from app.ratelimit import Limit, RateLimiter, select_limits
from tests.conftest import FakeClock

AGENT = uuid.uuid4()


async def test_n_requests_succeed_and_n_plus_one_is_denied(limiter: RateLimiter) -> None:
    limits = [Limit(max_requests=3, window_seconds=60)]

    for _ in range(3):
        assert (await limiter.hit(AGENT, "send_email", limits)).allowed

    result = await limiter.hit(AGENT, "send_email", limits)
    assert not result.allowed
    assert result.exceeded == limits[0]
    assert 0 < result.retry_after_seconds <= 60


async def test_counter_resets_after_window(limiter: RateLimiter, clock: FakeClock) -> None:
    limits = [Limit(max_requests=2, window_seconds=60)]
    for _ in range(2):
        await limiter.hit(AGENT, "send_email", limits)
    assert not (await limiter.hit(AGENT, "send_email", limits)).allowed

    clock.advance(60)
    assert (await limiter.hit(AGENT, "send_email", limits)).allowed


async def test_window_slides_rather_than_resetting_all_at_once(limiter: RateLimiter, clock: FakeClock) -> None:
    limits = [Limit(max_requests=2, window_seconds=60)]
    await limiter.hit(AGENT, "send_email", limits)  # t=0
    clock.advance(30)
    await limiter.hit(AGENT, "send_email", limits)  # t=30

    clock.advance(20)  # t=50: both still inside the window
    result = await limiter.hit(AGENT, "send_email", limits)
    assert not result.allowed
    assert result.retry_after_seconds == 10  # when the t=0 request ages out

    clock.advance(10)  # t=60: the first request has aged out, the second hasn't
    assert (await limiter.hit(AGENT, "send_email", limits)).allowed
    assert not (await limiter.hit(AGENT, "send_email", limits)).allowed


async def test_denied_requests_do_not_consume_budget(limiter: RateLimiter, clock: FakeClock) -> None:
    limits = [Limit(max_requests=1, window_seconds=60)]
    await limiter.hit(AGENT, "send_email", limits)
    for _ in range(5):
        await limiter.hit(AGENT, "send_email", limits)  # all denied

    clock.advance(60)  # only the one admitted request needs to age out
    assert (await limiter.hit(AGENT, "send_email", limits)).allowed


async def test_limits_are_per_agent_and_per_action_type(limiter: RateLimiter) -> None:
    limits = [Limit(max_requests=1, window_seconds=60)]
    assert (await limiter.hit(AGENT, "send_email", limits)).allowed
    assert not (await limiter.hit(AGENT, "send_email", limits)).allowed

    assert (await limiter.hit(AGENT, "make_payment", limits)).allowed
    assert (await limiter.hit(uuid.uuid4(), "send_email", limits)).allowed


async def test_multiple_windows_all_must_have_room(limiter: RateLimiter, clock: FakeClock) -> None:
    per_minute = Limit(max_requests=2, window_seconds=60)
    per_hour = Limit(max_requests=3, window_seconds=3600)
    limits = [per_minute, per_hour]

    for _ in range(2):
        assert (await limiter.hit(AGENT, "make_payment", limits)).allowed
    assert (await limiter.hit(AGENT, "make_payment", limits)).exceeded == per_minute

    clock.advance(60)
    assert (await limiter.hit(AGENT, "make_payment", limits)).allowed  # 3rd this hour
    clock.advance(60)
    assert (await limiter.hit(AGENT, "make_payment", limits)).exceeded == per_hour


async def test_request_denied_by_one_window_is_not_counted_in_another(
    limiter: RateLimiter, clock: FakeClock
) -> None:
    per_minute = Limit(max_requests=1, window_seconds=60)
    per_hour = Limit(max_requests=2, window_seconds=3600)
    limits = [per_minute, per_hour]

    await limiter.hit(AGENT, "make_payment", limits)
    for _ in range(3):
        await limiter.hit(AGENT, "make_payment", limits)  # denied by per_minute

    clock.advance(60)
    # If denied requests had leaked into the hourly count this would be denied.
    assert (await limiter.hit(AGENT, "make_payment", limits)).allowed


async def test_concurrent_requests_cannot_exceed_limit(limiter: RateLimiter) -> None:
    limits = [Limit(max_requests=5, window_seconds=60)]
    results = await asyncio.gather(*(limiter.hit(AGENT, "send_email", limits) for _ in range(25)))
    assert sum(r.allowed for r in results) == 5


async def test_no_limits_means_unlimited(limiter: RateLimiter) -> None:
    for _ in range(50):
        assert (await limiter.hit(AGENT, "send_email", [])).allowed


# --- select_limits (pure) ------------------------------------------------------


def row(agent_id: uuid.UUID | None, action_type: str, max_requests: int, window: int, active: bool = True):
    return SimpleNamespace(
        agent_id=agent_id,
        action_type=action_type,
        max_requests=max_requests,
        window_seconds=window,
        is_active=active,
    )


def test_select_limits_uses_global_defaults_when_agent_has_none() -> None:
    rows = [row(None, "send_email", 10, 60), row(uuid.uuid4(), "send_email", 1, 60)]
    assert select_limits(AGENT, "send_email", rows) == [Limit(10, 60)]


def test_select_limits_agent_specific_replaces_defaults() -> None:
    rows = [
        row(None, "make_payment", 5, 60),
        row(AGENT, "make_payment", 3, 60),
        row(AGENT, "make_payment", 20, 86400),
    ]
    assert select_limits(AGENT, "make_payment", rows) == [Limit(3, 60), Limit(20, 86400)]


def test_select_limits_ignores_inactive_and_other_action_types() -> None:
    rows = [row(AGENT, "make_payment", 3, 60, active=False), row(None, "send_email", 10, 60)]
    assert select_limits(AGENT, "make_payment", rows) == []
