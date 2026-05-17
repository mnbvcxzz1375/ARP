"""Prometheus metrics for AgentNet."""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest


HTTP_REQUESTS = Counter(
    "agentnet_http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status"],
)
HTTP_DURATION = Histogram(
    "agentnet_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)
HTTP_ERRORS = Counter(
    "agentnet_http_errors_total",
    "Total HTTP 5xx errors.",
    ["method", "path", "status"],
)

WS_CONNECTIONS_ACTIVE = Gauge(
    "agentnet_ws_connections_active",
    "Currently active WebSocket connections.",
)
WS_CONNECTIONS_TOTAL = Counter(
    "agentnet_ws_connections_total",
    "Total accepted WebSocket connections.",
)
WS_DISCONNECTS_TOTAL = Counter(
    "agentnet_ws_disconnects_total",
    "Total WebSocket disconnects.",
)
WS_AUTH_FAILURES_TOTAL = Counter(
    "agentnet_ws_auth_failures_total",
    "Total WebSocket authentication failures.",
)

TASKS_CREATED_TOTAL = Counter("agentnet_tasks_created_total", "Tasks created.")
TASKS_COMPLETED_TOTAL = Counter("agentnet_tasks_completed_total", "Tasks completed.")
TASKS_FAILED_TOTAL = Counter("agentnet_tasks_failed_total", "Tasks failed.")
TASKS_EXPIRED_TOTAL = Counter("agentnet_tasks_expired_total", "Tasks expired.")
TASK_DURATION_SECONDS = Histogram("agentnet_task_duration_seconds", "Task duration in seconds.")

MESSAGES_DELIVERED_TOTAL = Counter("agentnet_messages_delivered_total", "Messages delivered online.")
MESSAGES_ACKED_TOTAL = Counter("agentnet_messages_acked_total", "Messages acked.")
MESSAGES_RETRIED_TOTAL = Counter("agentnet_messages_retried_total", "Messages retried.")
MESSAGES_EXPIRED_TOTAL = Counter("agentnet_messages_expired_total", "Messages expired.")
PENDING_MESSAGES = Gauge("agentnet_pending_messages", "Pending messages known to the relay.")

APPROVALS_PENDING = Gauge("agentnet_approvals_pending", "Pending approvals.")
APPROVALS_ACCEPTED_TOTAL = Counter("agentnet_approvals_accepted_total", "Approvals accepted.")
APPROVALS_REJECTED_TOTAL = Counter("agentnet_approvals_rejected_total", "Approvals rejected.")
APPROVALS_EXPIRED_TOTAL = Counter("agentnet_approvals_expired_total", "Approvals expired.")

RETRY_WORKER_CYCLES_TOTAL = Counter("agentnet_retry_worker_cycles_total", "Retry worker cycles.")
TIMEOUT_WORKER_CYCLES_TOTAL = Counter("agentnet_timeout_worker_cycles_total", "Timeout worker cycles.")
WORKER_ERRORS_TOTAL = Counter("agentnet_worker_errors_total", "Worker errors.", ["worker"])


async def metrics_middleware(request: Request, call_next: Callable):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    method = request.method
    status = str(response.status_code)
    HTTP_REQUESTS.labels(method=method, path=path, status=status).inc()
    HTTP_DURATION.labels(method=method, path=path).observe(duration)
    if response.status_code >= 500:
        HTTP_ERRORS.labels(method=method, path=path, status=status).inc()
    return response


async def metrics_endpoint() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def ws_connected() -> None:
    WS_CONNECTIONS_ACTIVE.inc()
    WS_CONNECTIONS_TOTAL.inc()


def ws_disconnected() -> None:
    WS_CONNECTIONS_ACTIVE.dec()
    WS_DISCONNECTS_TOTAL.inc()


def ws_auth_failed() -> None:
    WS_AUTH_FAILURES_TOTAL.inc()
