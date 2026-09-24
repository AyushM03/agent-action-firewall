from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


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
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()
