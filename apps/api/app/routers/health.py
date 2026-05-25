"""Health check router with dependency verification.

Provides /healthz (lightweight) and /readyz (deep dependency checks)
for load balancer probes and operational monitoring.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis import asyncio as aioredis
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.metrics import HEALTH_CHECK_STATUS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# Module-level redis client for health checks (created lazily)
_redis_client: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


@router.get("/healthz")
async def healthz():
    """Lightweight liveness probe.

    Returns 200 if the API process is running. Does not check
    external dependencies -- use /readyz for that.
    """
    return {"status": "alive"}


@router.get("/readyz")
async def readyz():
    """Deep readiness probe with dependency checks.

    Checks PostgreSQL and Redis connectivity. Returns 200 only
    when all dependencies are reachable; 503 otherwise.

    Also updates the agentnet_health_check_status Prometheus gauge
    so that alerting can fire when a dependency degrades.
    """
    checks: dict[str, str] = {}
    overall = "healthy"

    # -- PostgreSQL --
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgresql"] = "ok"
        HEALTH_CHECK_STATUS.labels(component="postgresql").set(1)
    except Exception as exc:
        logger.error("PostgreSQL health check failed: %s", exc)
        checks["postgresql"] = f"error: {exc}"
        HEALTH_CHECK_STATUS.labels(component="postgresql").set(0)
        overall = "degraded"

    # -- Redis --
    try:
        redis = await _get_redis()
        await redis.ping()
        checks["redis"] = "ok"
        HEALTH_CHECK_STATUS.labels(component="redis").set(1)
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        checks["redis"] = f"error: {exc}"
        HEALTH_CHECK_STATUS.labels(component="redis").set(0)
        overall = "degraded"

    status_code = 200 if overall == "healthy" else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": overall, "checks": checks},
    )