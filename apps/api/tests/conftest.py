import os
os.environ["DB_POOL_PRE_PING"] = "true"
os.environ["DB_NULL_POOL"] = "true"
os.environ["RATE_LIMIT_IP_MAX"] = "999999"  # disable IP rate limit for test suite
os.environ["RATE_LIMIT_USER_MAX"] = "999999"
os.environ["RATE_LIMIT_AGENT_MAX"] = "999999"
os.environ["RATE_LIMIT_GLOBAL_MAX"] = "999999"

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Provide an async SQLAlchemy session that rolls back after each test."""
    async with SessionLocal() as s:
        try:
            yield s
        finally:
            await s.rollback()


@pytest.fixture(autouse=True)
def _mock_redis():
    """Mock Redis for all tests — the test environment has no real Redis."""
    mock = AsyncMock()
    mock.eval = AsyncMock(return_value=0)
    mock.zremrangebyscore = AsyncMock()
    mock.zcard = AsyncMock(return_value=0)
    mock.ping = AsyncMock(return_value=True)
    mock.aclose = AsyncMock()
    mock.set = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.delete = AsyncMock()
    mock.zadd = AsyncMock()
    mock.expire = AsyncMock()
    mock.keys = AsyncMock(return_value=[])
    mock.exists = AsyncMock(return_value=0)

    with patch("app.services.rate_limit_service.redis_client", mock), \
         patch("app.redis.redis_client", mock):
        yield mock


@pytest.fixture
def anyio_backend():
    return "asyncio"
