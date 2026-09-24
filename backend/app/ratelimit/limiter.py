"""Redis-backed sliding-window rate limiter.

Each (agent, action_type, window) gets a sorted set of request timestamps.
A request is admitted only if every applicable window has room; the check and
the insert happen in one Lua script, so concurrent requests can't both slip
into the last slot, and a request rejected by one window doesn't use up
budget in the others.
"""

import time
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from redis.asyncio import Redis

if TYPE_CHECKING:
    from app.models import RateLimit

# KEYS: one sorted set per window.
# ARGV: now_ms, member, then (window_ms, max_requests) for each key.
# Returns {1} if admitted, else {0, index of the exceeded key (1-based), retry_after_ms}.
SLIDING_WINDOW_LUA = """
local now = tonumber(ARGV[1])
local member = ARGV[2]
for i, key in ipairs(KEYS) do
    local window = tonumber(ARGV[1 + i * 2])
    local max_requests = tonumber(ARGV[2 + i * 2])
    redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
    if redis.call('ZCARD', key) >= max_requests then
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        return {0, i, tonumber(oldest[2]) + window - now}
    end
end
for i, key in ipairs(KEYS) do
    redis.call('ZADD', key, now, member)
    redis.call('PEXPIRE', key, tonumber(ARGV[1 + i * 2]))
end
return {1}
"""


@dataclass(frozen=True)
class Limit:
    max_requests: int
    window_seconds: int

    @classmethod
    def from_model(cls, row: "RateLimit") -> "Limit":
        return cls(row.max_requests, row.window_seconds)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    exceeded: Limit | None = None
    retry_after_seconds: float = 0.0


def select_limits(agent_id: uuid.UUID, action_type: str, rows: Iterable["RateLimit"]) -> list[Limit]:
    """Pick the limits that apply: the agent's own if it has any, else the global defaults."""
    matching = [r for r in rows if r.is_active and r.action_type == action_type]
    own = [r for r in matching if r.agent_id == agent_id]
    chosen = own or [r for r in matching if r.agent_id is None]
    return [Limit.from_model(r) for r in chosen]


class RateLimiter:
    def __init__(
        self,
        redis: Redis,
        prefix: str = "ratelimit",
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._redis = redis
        self._prefix = prefix
        self._clock = clock
        self._script = redis.register_script(SLIDING_WINDOW_LUA)

    def _key(self, agent_id: uuid.UUID, action_type: str, limit: Limit) -> str:
        return f"{self._prefix}:{agent_id}:{action_type}:{limit.window_seconds}"

    async def hit(
        self, agent_id: uuid.UUID, action_type: str, limits: Sequence[Limit]
    ) -> RateLimitResult:
        """Count one request against every limit, or none if any limit is full.

        Raises redis.RedisError if Redis is unreachable; callers must fail closed.
        """
        if not limits:
            return RateLimitResult(allowed=True)

        keys = [self._key(agent_id, action_type, limit) for limit in limits]
        args: list[int | str] = [int(self._clock() * 1000), uuid.uuid4().hex]
        for limit in limits:
            args += [limit.window_seconds * 1000, limit.max_requests]

        result = await self._script(keys=keys, args=args)
        if result[0] == 1:
            return RateLimitResult(allowed=True)
        return RateLimitResult(
            allowed=False,
            exceeded=limits[int(result[1]) - 1],
            retry_after_seconds=max(int(result[2]), 0) / 1000,
        )
