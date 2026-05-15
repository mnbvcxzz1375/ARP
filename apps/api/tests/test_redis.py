import pytest

from app import redis as redis_module


class DummyRedis:
    async def ping(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_redis_connectivity_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(redis_module, "redis_client", DummyRedis())

    assert await redis_module.check_redis() is True

