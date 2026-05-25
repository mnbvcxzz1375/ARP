"""Egress service: external API/service access control and proxying."""

import hashlib
import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import redis as redis_module
from app.exceptions import DomainException
from app.metrics import EGRESS_REQUESTS_TOTAL, EGRESS_LATENCY_MS
from app.models.egress_gateway import EgressGateway
from app.models.egress_log import EgressLog
from app.protocol.constants import ErrorCode
from app.services.approval_service import create_approval
from app.services.audit_service import write_audit

logger = logging.getLogger(__name__)

# High-risk operations that require approval
HIGH_RISK_OPERATIONS = {
    "upload", "deploy", "delete", "destroy", "remove",
    "secret_update", "secret_create", "secret_delete",
    "production", "prod", "live"
}


async def check_domain_allowlist(
    session: AsyncSession,
    gateway_id: UUID,
    target_url: str,
) -> bool:
    """Check if target domain is in gateway's allowlist."""
    gateway = await _get_gateway(session, gateway_id)

    if not gateway.enabled:
        raise DomainException(
            ErrorCode.EGRESS_BLOCKED,
            f"Egress gateway {gateway_id} is disabled",
            status_code=403,
        )

    parsed = urlparse(target_url)
    target_domain = parsed.netloc or parsed.path.split('/')[0]

    allowlist = gateway.domain_allowlist or []

    # Check exact match or wildcard
    for allowed in allowlist:
        if _domain_matches(target_domain, allowed):
            return True

    logger.warning(
        "Domain %s blocked by gateway %s (allowlist: %s)",
        target_domain, gateway_id, allowlist
    )
    return False


async def proxy_external_request(
    session: AsyncSession,
    *,
    gateway_id: UUID,
    task_id: UUID | None,
    agent_id: UUID,
    request_type: str,
    target_url: str,
    request_body: dict | None = None,
    headers: dict | None = None,
) -> dict[str, Any]:
    """
    Proxy an external request through the egress gateway.

    This is the ONLY way agents can access external services.
    Agents cannot bypass this gateway to use enterprise secrets.
    """
    gateway = await _get_gateway(session, gateway_id)

    # 1. Check domain allowlist
    if not await check_domain_allowlist(session, gateway_id, target_url):
        await _log_egress(
            session,
            gateway_id=gateway_id,
            task_id=task_id,
            agent_id=agent_id,
            request_type=request_type,
            target_domain=urlparse(target_url).netloc,
            status_code=403,
        )
        blocked_reason = f"Domain not in allowlist for gateway {gateway_id}"
        await _persist_failure_evidence(
            session,
            agent_id=agent_id,
            gateway_id=gateway_id,
            task_id=task_id,
            request_type=request_type,
            target_url=target_url,
            status_code=403,
            latency_ms=None,
            reason=blocked_reason,
        )
        raise DomainException(
            ErrorCode.EGRESS_BLOCKED,
            blocked_reason,
            status_code=403,
        )

    # 2. Check if high-risk operation requires approval
    approval_id = None
    if _is_high_risk_operation(request_type, target_url, request_body):
        if not task_id:
            raise DomainException(
                ErrorCode.APPROVAL_REQUIRED,
                "High-risk egress operation requires a task context",
                status_code=400,
            )

        approval = await create_approval(
            session,
            task_id=task_id,
            agent_id=agent_id,
            risk_level="high",
            action_kind=f"egress_{request_type.lower()}",
            action_preview=f"{request_type} {target_url}",
            reason="High-risk external operation requires approval",
        )
        approval_id = approval.id

        # Return early - actual request will be made after approval
        return {
            "status": "awaiting_approval",
            "approval_id": str(approval_id),
            "message": "High-risk operation requires approval before execution",
        }

    # 3. Check egress rate limit (sliding window, per gateway+agent)
    await _check_egress_rate_limit(gateway_id, agent_id, gateway.rate_limit_config)

    # 4. Check cache (GET only, after rate limit, before secret injection)
    cache_ttl = _parse_cache_ttl(gateway.cache_config)
    is_get = request_type.upper() == "GET"
    cache_key = None

    if is_get and cache_ttl:
        cache_key = _build_cache_key(gateway_id, request_type, target_url, request_body)
        cached_data = await _cache_get(cache_key)
        if cached_data is not None:
            await _log_egress(
                session,
                gateway_id=gateway_id,
                task_id=task_id,
                agent_id=agent_id,
                request_type=request_type,
                target_domain=urlparse(target_url).netloc,
                status_code=200,
                latency_ms=0,
                cost_estimate=0,
                approval_id=approval_id,
            )
            EGRESS_REQUESTS_TOTAL.labels(
                gateway_id=str(gateway_id), status="200"
            ).inc()
            EGRESS_LATENCY_MS.labels(gateway_id=str(gateway_id)).observe(0)
            await write_audit(
                session,
                actor_type="agent",
                actor_id=str(agent_id),
                action="egress.request",
                resource_type="egress_gateway",
                resource_id=str(gateway_id),
                task_id=str(task_id) if task_id else None,
                details={
                    "request_type": request_type,
                    "target_url": target_url,
                    "status_code": 200,
                    "latency_ms": 0,
                    "cached": True,
                },
            )
            await session.commit()
            return cached_data

    # 5. Inject secrets (agent never sees them)
    injected_headers = await _inject_secrets(session, gateway, headers or {})

    # 6. Make the actual HTTP request
    start_time = datetime.now(UTC)

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.request(
                method=request_type.upper(),
                url=target_url,
                json=request_body if request_body else None,
                headers=injected_headers,
            )

            status_code = response.status_code
            latency_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

            # Parse response body
            try:
                response_data = response.json()
            except Exception:
                response_data = {"body": response.text}

            response_size_bytes = len(response.content)

    except httpx.TimeoutException as e:
        logger.error("Egress request timeout for %s: %s", target_url, e)
        await _log_egress(
            session,
            gateway_id=gateway_id,
            task_id=task_id,
            agent_id=agent_id,
            request_type=request_type,
            target_domain=urlparse(target_url).netloc,
            request_size_bytes=len(str(request_body or "")),
            response_size_bytes=0,
            status_code=504,
            latency_ms=30000,
            cost_estimate=None,
            approval_id=approval_id,
        )
        timeout_reason = f"Request timeout for {target_url}"
        await _persist_failure_evidence(
            session,
            agent_id=agent_id,
            gateway_id=gateway_id,
            task_id=task_id,
            request_type=request_type,
            target_url=target_url,
            status_code=504,
            latency_ms=30000,
            reason=timeout_reason,
        )
        raise DomainException(
            ErrorCode.EGRESS_BLOCKED,
            timeout_reason,
            status_code=504,
        )
    except httpx.RequestError as e:
        logger.error("Egress request failed for %s: %s", target_url, e)
        req_latency_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
        await _log_egress(
            session,
            gateway_id=gateway_id,
            task_id=task_id,
            agent_id=agent_id,
            request_type=request_type,
            target_domain=urlparse(target_url).netloc,
            request_size_bytes=len(str(request_body or "")),
            response_size_bytes=0,
            status_code=502,
            latency_ms=req_latency_ms,
            cost_estimate=None,
            approval_id=approval_id,
        )
        req_error_reason = f"Request failed for {target_url}: {str(e)}"
        await _persist_failure_evidence(
            session,
            agent_id=agent_id,
            gateway_id=gateway_id,
            task_id=task_id,
            request_type=request_type,
            target_url=target_url,
            status_code=502,
            latency_ms=req_latency_ms,
            reason=req_error_reason,
        )
        raise DomainException(
            ErrorCode.EGRESS_BLOCKED,
            req_error_reason,
            status_code=502,
        )

    # 7. Cache 2xx GET responses
    if is_get and cache_ttl and cache_key and 200 <= status_code < 300:
        await _cache_set(cache_key, response_data, cache_ttl)

    # 8. Track cost
    cost_estimate = None
    if gateway.cost_tracking:
        cost_estimate = await _estimate_cost(
            gateway,
            request_type,
            len(str(request_body or "")),
            response_size_bytes,
        )

    # 9. Log egress
    await _log_egress(
        session,
        gateway_id=gateway_id,
        task_id=task_id,
        agent_id=agent_id,
        request_type=request_type,
        target_domain=urlparse(target_url).netloc,
        request_size_bytes=len(str(request_body or "")),
        response_size_bytes=response_size_bytes,
        status_code=status_code,
        latency_ms=latency_ms,
        cost_estimate=cost_estimate,
        approval_id=approval_id,
    )

    # 10. Audit
    await write_audit(
        session,
        actor_type="agent",
        actor_id=str(agent_id),
        action="egress.request",
        resource_type="egress_gateway",
        resource_id=str(gateway_id),
        task_id=str(task_id) if task_id else None,
        details={
            "request_type": request_type,
            "target_url": target_url,
            "status_code": status_code,
            "latency_ms": latency_ms,
        },
    )
    await session.commit()

    # 11. Prometheus metrics
    EGRESS_REQUESTS_TOTAL.labels(
        gateway_id=str(gateway_id), status=str(status_code)
    ).inc()
    EGRESS_LATENCY_MS.labels(gateway_id=str(gateway_id)).observe(latency_ms)

    return response_data


async def require_approval_for_high_risk(
    session: AsyncSession,
    *,
    task_id: UUID,
    agent_id: UUID,
    operation: str,
    target: str,
) -> UUID:
    """Create approval for high-risk egress operation."""
    approval = await create_approval(
        session,
        task_id=task_id,
        agent_id=agent_id,
        risk_level="high",
        action_kind=f"egress_{operation}",
        action_preview=target,
        reason="High-risk external operation",
    )
    return approval.id


async def _get_gateway(session: AsyncSession, gateway_id: UUID) -> EgressGateway:
    """Get egress gateway by ID."""
    result = await session.execute(
        select(EgressGateway).where(EgressGateway.id == gateway_id)
    )
    gateway = result.scalar_one_or_none()
    if gateway is None:
        raise DomainException(
            ErrorCode.EGRESS_BLOCKED,
            f"Egress gateway {gateway_id} not found",
            status_code=404,
        )
    return gateway


async def _inject_secrets(
    session: AsyncSession,
    gateway: EgressGateway,
    headers: dict[str, str],
) -> dict[str, str]:
    """
    Inject secrets from secret store into headers.

    CRITICAL: Secrets are NEVER exposed to agents.
    They are injected server-side only.

    Supported refs:
      - None / empty: no injection, request proceeds as-is.
      - env:VAR_NAME: read secret from environment variable.
        Missing/empty vars block the request (fail closed).
      - Everything else (vault://, aws://, etc.) blocks the request (fail closed).
    """
    injected = dict(headers)
    secret_ref = gateway.secret_store_ref

    if not secret_ref:
        return injected

    if secret_ref.startswith("env:"):
        var_name = secret_ref[4:]
        secret_value = os.environ.get(var_name)
        if not secret_value:
            logger.error(
                "Secret env var %s is missing or empty for gateway %s",
                var_name, gateway.id,
            )
            raise DomainException(
                ErrorCode.EGRESS_BLOCKED,
                f"Egress secret {var_name} is not configured",
                status_code=503,
            )

        # Reject if agent already provided an Authorization header.
        # This prevents agents from bypassing enterprise secret management
        # by supplying their own credentials.
        has_auth = any(k.lower() == "authorization" for k in injected)
        if has_auth:
            logger.warning(
                "Agent provided Authorization header with secret_store_ref %s for gateway %s",
                secret_ref, gateway.id,
            )
            raise DomainException(
                ErrorCode.EGRESS_BLOCKED,
                "Authorization header must be managed by egress gateway",
                status_code=403,
            )

        injected["Authorization"] = f"Bearer {secret_value}"
        logger.info(
            "Injected secret from env var %s for gateway %s (secret not logged)",
            var_name, gateway.id,
        )
        return injected

    # Unsupported secret store reference - fail closed, never pretend success.
    raise DomainException(
        ErrorCode.EGRESS_BLOCKED,
        f"Unsupported egress secret store ref {secret_ref}",
        status_code=501,
    )


async def _estimate_cost(
    gateway: EgressGateway,
    request_type: str,
    request_size: int,
    response_size: int = 0,
) -> int | None:
    """Estimate cost of external request in cents (as integer)."""
    # Simple cost model - can be extended
    if gateway.gateway_type == "model":
        # Model API: ~$0.01 per 1K tokens (rough estimate)
        # Consider both request and response sizes
        total_size = request_size + response_size
        tokens = max(total_size // 4, 1)  # rough token estimate, at least 1
        cost_cents = max(int((tokens / 1000) * 1.0), 1)  # cents as int, minimum 1
        return cost_cents
    elif gateway.gateway_type == "api":
        # Generic API: flat rate
        return 1  # 1 cent per request
    return None


async def _persist_failure_evidence(
    session: AsyncSession,
    *,
    agent_id: UUID,
    gateway_id: UUID,
    task_id: UUID | None,
    request_type: str,
    target_url: str,
    status_code: int,
    latency_ms: int | None,
    reason: str,
) -> None:
    """Write audit and commit for a failure path so evidence is never lost.

    Must be called AFTER _log_egress (which adds the EgressLog row) and
    BEFORE raising the DomainException.  Commits egress log + audit atomically.
    If write_audit or commit fails, raises DomainException(INTERNAL_ERROR) so
    the original failure is never silently swallowed.
    """
    try:
        await write_audit(
            session,
            actor_type="agent",
            actor_id=str(agent_id),
            action="egress.request",
            resource_type="egress_gateway",
            resource_id=str(gateway_id),
            task_id=str(task_id) if task_id else None,
            details={
                "request_type": request_type,
                "target_url": target_url,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "reason": reason,
            },
        )
        await session.commit()
    except DomainException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to persist egress failure evidence for gateway %s: %s",
            gateway_id, exc,
        )
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            f"Egress failure evidence could not be persisted: {exc}",
            status_code=503,
        )


async def _log_egress(
    session: AsyncSession,
    *,
    gateway_id: UUID,
    task_id: UUID | None,
    agent_id: UUID,
    request_type: str,
    target_domain: str,
    request_size_bytes: int = 0,
    response_size_bytes: int = 0,
    status_code: int | None = None,
    latency_ms: int | None = None,
    cost_estimate: int | None = None,
    approval_id: UUID | None = None,
) -> None:
    """Log egress request for audit and cost tracking.

    Does NOT commit — the caller is responsible for committing the
    transaction so that the egress log and any associated audit entry
    are persisted atomically.
    """
    log = EgressLog(
        gateway_id=gateway_id,
        task_id=task_id,
        agent_id=agent_id,
        request_type=request_type,
        target_domain=target_domain,
        request_size_bytes=request_size_bytes,
        response_size_bytes=response_size_bytes,
        status_code=status_code,
        latency_ms=latency_ms,
        cost_estimate=cost_estimate,
        approval_id=approval_id,
    )
    session.add(log)


def _domain_matches(target: str, pattern: str) -> bool:
    """Check if target domain matches pattern (supports wildcards)."""
    if pattern == "*":
        return True

    # Convert wildcard pattern to regex
    regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
    return bool(re.match(f"^{regex_pattern}$", target))


def _is_high_risk_operation(
    request_type: str,
    target_url: str,
    request_body: dict | None,
) -> bool:
    """Determine if operation is high-risk and requires approval."""
    # Check request type
    if request_type.upper() in {"DELETE", "PUT", "PATCH"}:
        return True

    # Check URL for high-risk keywords
    url_lower = target_url.lower()
    for keyword in HIGH_RISK_OPERATIONS:
        if keyword in url_lower:
            return True

    # Check request body for high-risk keywords
    if request_body:
        body_str = str(request_body).lower()
        for keyword in HIGH_RISK_OPERATIONS:
            if keyword in body_str:
                return True

    return False


def _parse_rate_limit_config(config: dict | None) -> tuple[int | None, int | None]:
    """Parse rate_limit_config, returning (max_requests, window_seconds) or (None, None).

    Supports two formats:
      - {"requests_per_minute": 60}       -> window=60s, limit=60
      - {"max_requests": 10, "window_seconds": 30}
    Missing, empty, or non-positive values disable rate limiting.
    """
    if not config:
        return None, None

    if "requests_per_minute" in config:
        rpm = config["requests_per_minute"]
        if isinstance(rpm, (int, float)) and rpm > 0:
            return int(rpm), 60
        return None, None

    max_r = config.get("max_requests")
    win_s = config.get("window_seconds")
    if (
        isinstance(max_r, (int, float))
        and isinstance(win_s, (int, float))
        and max_r > 0
        and win_s > 0
    ):
        return int(max_r), int(win_s)

    return None, None


async def _check_egress_rate_limit(
    gateway_id: UUID,
    agent_id: UUID,
    rate_limit_config: dict | None,
) -> None:
    """Check egress rate limit with Redis sorted-set sliding window.

    Raises DomainException(RATE_LIMITED, 429) when throttled.
    Raises DomainException(INTERNAL_ERROR, 503) on Redis failure.
    """
    max_requests, window_seconds = _parse_rate_limit_config(rate_limit_config)
    if max_requests is None:
        return

    now_s = time.time()
    window_start = now_s - window_seconds
    member = f"{now_s}:{agent_id}"
    key = f"egress:rate_limit:{gateway_id}:{agent_id}"

    r = redis_module.redis_client
    try:
        await r.zremrangebyscore(key, "-inf", window_start)
        count = await r.zcard(key)
        if count >= max_requests:
            raise DomainException(
                ErrorCode.RATE_LIMITED,
                f"Egress gateway {gateway_id} rate limit exceeded: "
                f"{max_requests} requests per {window_seconds}s",
                status_code=429,
                details={
                    "gateway_id": str(gateway_id),
                    "limit": max_requests,
                    "window_seconds": window_seconds,
                },
            )
        await r.zadd(key, {member: now_s})
        await r.expire(key, window_seconds * 2)
    except DomainException:
        raise
    except Exception as exc:
        logger.error(
            "Egress rate limit Redis error for gateway %s, agent %s: %s",
            gateway_id, agent_id, exc,
        )
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            "Egress rate limiter unavailable",
            status_code=503,
        )


def _parse_cache_ttl(cache_config: dict | None) -> int | None:
    """Parse cache_config, returning ttl_seconds or None if disabled."""
    if not cache_config:
        return None
    ttl = cache_config.get("ttl_seconds")
    if isinstance(ttl, (int, float)) and ttl > 0:
        return int(ttl)
    return None


def _build_cache_key(
    gateway_id: UUID,
    request_type: str,
    target_url: str,
    request_body: dict | None,
) -> str:
    """Build a stable deterministic cache key for egress requests."""
    key_data = {
        "gateway_id": str(gateway_id),
        "request_type": request_type.upper(),
        "target_url": target_url,
        "request_body": request_body,
    }
    raw = json.dumps(key_data, sort_keys=True, separators=(",", ":"))
    return "egress:cache:" + hashlib.sha256(raw.encode()).hexdigest()


async def _cache_get(cache_key: str) -> dict[str, Any] | None:
    """Get cached response from Redis.

    Returns None on cache miss.
    Raises DomainException(503) on Redis or JSON decode failure (fail closed).
    """
    r = redis_module.redis_client
    try:
        data = await r.get(cache_key)
    except Exception as exc:
        logger.error("Egress cache get failed for key %s: %s", cache_key, exc)
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            "Egress cache unavailable",
            status_code=503,
        )

    if data is None:
        return None

    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Egress cache corrupt for key %s: %s", cache_key, exc)
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            "Egress cache data corrupted",
            status_code=503,
        )


async def _cache_set(cache_key: str, response_data: dict[str, Any], ttl: int) -> None:
    """Write response to Redis cache.

    Raises DomainException(503) on failure (fail closed).
    """
    r = redis_module.redis_client
    try:
        raw = json.dumps(response_data, ensure_ascii=False)
        await r.set(cache_key, raw, ex=ttl)
    except Exception as exc:
        logger.error("Egress cache set failed for key %s: %s", cache_key, exc)
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            "Egress cache unavailable",
            status_code=503,
        )
