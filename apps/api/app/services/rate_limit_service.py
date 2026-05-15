"""Rate limiting service: Redis-based sliding window with multi-dimensional support.

Supports rate limiting by user_id, agent_id, and IP address.
Uses Redis sorted sets with Lua scripting for atomic check-and-increment.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import get_settings
from app.exceptions import DomainException
from app.protocol.constants import ErrorCode
from app.redis import redis_client

logger = logging.getLogger(__name__)

# Lua script: atomic sliding-window rate limit check + increment.
# KEYS[1] = sorted set key
# ARGV[1] = now (seconds)
# ARGV[2] = window start (seconds)
# ARGV[3] = max requests
# ARGV[4] = member string (unique per request for dedup)
# Returns: 0 = allowed, 1 = rate limited
_RATE_LIMIT_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[2])
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[3]) then
    return 1
end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('EXPIRE', KEYS[1], math.ceil(tonumber(ARGV[1]) - tonumber(ARGV[2]) + 60))
return 0
"""

# Dimension-specific Redis key prefixes
_KEY_PREFIXES: dict[str, str] = {
    "user": "rl:user:",
    "agent": "rl:agent:",
    "ip": "rl:ip:",
    "global": "rl:global:",
}


async def _check_and_increment(
    dimension: str,
    identifier: str,
    max_requests: int,
    window_s: float,
) -> None:
    """Atomically check and increment a rate limit counter for a given dimension.

    Raises DomainException(RATE_LIMITED) if limit exceeded.
    """
    if max_requests <= 0:
        return  # No limit configured

    now_s = time.time()
    window_start = now_s - window_s
    member = f"{now_s}:{identifier}"
    key = f"{_KEY_PREFIXES.get(dimension, 'rl:')}{identifier}"

    try:
        r = redis_client
        result = await r.eval(
            _RATE_LIMIT_LUA,
            1,
            key,
            str(now_s),
            str(window_start),
            str(max_requests),
            member,
        )
        if result == 1:
            raise DomainException(
                ErrorCode.RATE_LIMITED,
                f"Rate limit exceeded for {dimension} '{identifier}'. "
                f"Limit: {max_requests} requests per {window_s:.0f}s.",
                status_code=429,
                details={
                    "dimension": dimension,
                    "limit": max_requests,
                    "window_seconds": int(window_s),
                },
            )
    except DomainException:
        raise
    except Exception as exc:
        logger.error(
            "Rate limiter Redis error for %s:%s: %s",
            dimension, identifier, exc,
        )
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            f"Rate limiter unavailable: {exc}",
            status_code=503,
        )


async def check_rate_limit(
    *,
    user_id: str | None = None,
    agent_id: str | None = None,
    request_ip: str | None = None,
) -> None:
    """Check rate limits across all applicable dimensions.

    Raises DomainException(RATE_LIMITED) if any dimension exceeds its limit.
    Rate limits are configurable per dimension via app settings.
    """
    settings = get_settings()
    window_s = settings.rate_limit_window_s

    checks: list[tuple[str, str, int]] = []

    if user_id:
        checks.append(("user", user_id, settings.rate_limit_user_max))
    if agent_id:
        checks.append(("agent", agent_id, settings.rate_limit_agent_max))
    if request_ip:
        checks.append(("ip", request_ip, settings.rate_limit_ip_max))

    # Always check global rate limit
    checks.append(("global", "all", settings.rate_limit_global_max))

    for dimension, identifier, max_requests in checks:
        await _check_and_increment(dimension, identifier, max_requests, window_s)


async def get_rate_limit_status(
    *,
    user_id: str | None = None,
    agent_id: str | None = None,
    request_ip: str | None = None,
) -> dict[str, Any]:
    """Get current rate limit status for inspection (read-only)."""
    settings = get_settings()
    window_s = settings.rate_limit_window_s

    status: dict[str, Any] = {
        "window_seconds": int(window_s),
        "limits": {
            "user": settings.rate_limit_user_max,
            "agent": settings.rate_limit_agent_max,
            "ip": settings.rate_limit_ip_max,
            "global": settings.rate_limit_global_max,
        },
        "current": {},
    }

    r = redis_client
    now_s = time.time()
    window_start = now_s - window_s

    for dimension, identifier in [
        ("user", user_id),
        ("agent", agent_id),
        ("ip", request_ip),
        ("global", "all"),
    ]:
        if not identifier:
            continue
        key = f"{_KEY_PREFIXES.get(dimension, 'rl:')}{identifier}"
        try:
            # Clean old entries and count
            await r.zremrangebyscore(key, "-inf", window_start)
            count = await r.zcard(key)
            status["current"][dimension] = count
        except Exception:
            status["current"][dimension] = -1

    return status

