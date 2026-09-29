import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_executors, get_limiter
from app.core.config import settings
from app.core.db import get_db
from app.executors import ExecutionError, ExecutionResult
from app.executors.payloads import Payload
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


class FakeExecutor:
    """Stands in for Gmail/Stripe in tests that aren't about the integrations themselves."""

    def __init__(self, name: str) -> None:
        self.actor = f"executor:fake-{name}"
        self.calls: list[tuple[uuid.UUID, Payload]] = []
        self.error: ExecutionError | None = None

    async def execute(self, request_id: uuid.UUID, payload: Payload) -> ExecutionResult:
        self.calls.append((request_id, payload))
        if self.error:
            raise self.error
        return ExecutionResult(f"fake-{len(self.calls)}", {"fake": True})


@pytest.fixture
def executors() -> dict[str, FakeExecutor]:
    return {"send_email": FakeExecutor("gmail"), "make_payment": FakeExecutor("stripe")}


@pytest.fixture
async def client(
    db: AsyncSession, limiter: RateLimiter, executors: dict[str, FakeExecutor]
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client for the real app, wired to the rolled-back test session, limiter and fake executors."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_limiter] = lambda: limiter
    app.dependency_overrides[get_executors] = lambda: executors
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http
    finally:
        app.dependency_overrides.clear()
