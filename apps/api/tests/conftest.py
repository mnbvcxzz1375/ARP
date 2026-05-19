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
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session, SessionLocal
from app.main import create_app


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Provide an async SQLAlchemy session where commits are rolled back.

    The session's commit() is patched to only flush(), so an outer
    rollback() at the end of the test undoes all changes.
    """
    async with SessionLocal() as s:
        original_commit = s.commit
        s.commit = s.flush  # commit() → flush() so rollback() can undo
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
async def app(session: AsyncSession):
    """FastAPI app instance with test DB session override."""
    _app = create_app()

    async def _test_session():
        yield session

    _app.dependency_overrides[get_session] = _test_session
    try:
        yield _app
    finally:
        _app.dependency_overrides.pop(get_session, None)


@pytest.fixture
async def client(app):
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def anyio_backend():
    return "asyncio"
