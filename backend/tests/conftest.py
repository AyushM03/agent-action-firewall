import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_limiter
from app.core.config import settings
from app.core.db import get_db
from app.main import app
from app.ratelimit import RateLimiter


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Session bound to an outer transaction that is always rolled back.

    Requires the database to be migrated (`alembic upgrade head`). Tests leave
    no rows behind, which matters here since the append-only tables can't be
    cleaned up with DELETE.
    """
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )  # same expire_on_commit as app.core.db.async_session
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()


@pytest.fixture
async def redis() -> AsyncGenerator[Redis, None]:
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    yield client
    await client.aclose()


class FakeClock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
async def limiter(redis: Redis, clock: FakeClock) -> AsyncGenerator[RateLimiter, None]:
    """Limiter on a per-test key prefix, using a controllable clock. Keys are removed afterwards."""
    prefix = f"test-ratelimit:{uuid.uuid4().hex}"
    yield RateLimiter(redis, prefix=prefix, clock=clock)
    keys = [key async for key in redis.scan_iter(f"{prefix}:*")]
    if keys:
        await redis.delete(*keys)


@pytest.fixture
async def client(db: AsyncSession, limiter: RateLimiter) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client for the real app, wired to the rolled-back test session and test limiter."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_limiter] = lambda: limiter
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http
    finally:
        app.dependency_overrides.clear()
