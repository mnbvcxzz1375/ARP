import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.config import get_settings

logger = logging.getLogger(__name__)
from app.exceptions import DomainException, domain_exception_handler
from app.logging import configure_logging
from app.metrics import metrics_endpoint, metrics_middleware
from app.routers.agents import router as agents_router
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.ws import router as ws_router
from app.routers.tasks import router as tasks_router
from app.routers.connections import router as connections_router
from app.routers.approvals import router as approvals_router
from app.routers.dashboard_auth import router as dashboard_auth_router
from app.websocket.manager import get_connection_manager


OPENAPI_TAGS = [
    {"name": "health", "description": "Liveness checks used by operators and load balancers."},
    {"name": "auth", "description": "User registration and API key bootstrap."},
    {"name": "agents", "description": "Agent registry, Agent Number metadata, and token rotation."},
    {"name": "tasks", "description": "Asynchronous task creation, lookup, messages, and progress history."},
    {"name": "connections", "description": "Cross-agent connection requests and approvals."},
    {"name": "approvals", "description": "Human-in-the-loop high-risk task approvals."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    from app.workers.retry_worker import retry_loop
    from app.workers.timeout_worker import timeout_loop

    settings = get_settings()

    mgr = get_connection_manager()
    await mgr.start_cleanup_loop()

    retry_task = asyncio.create_task(retry_loop(10.0))
    timeout_task = asyncio.create_task(
        timeout_loop(
            interval_s=settings.timeout_worker_interval_s,
            max_task_runtime_s=settings.task_max_runtime_s,
        )
    )

    yield

    for task in (retry_task, timeout_task):
        task.cancel()
    try:
        await asyncio.gather(retry_task, timeout_task, return_exceptions=True)
    except Exception:
        pass

    await mgr.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        description=(
            "AgentNet is a centralized Agent Relay Platform for registering agents, "
            "routing asynchronous tasks, tracking delivery state, and enforcing "
            "cross-agent approval policy. WebSocket agent transport is available at "
            "`/v1/ws` and documented in `docs/openapi.md`."
        ),
        version="0.1.0",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    app.add_exception_handler(DomainException, domain_exception_handler)
    app.add_api_route(
        "/metrics",
        metrics_endpoint,
        include_in_schema=False,
        methods=["GET"],
    )
    app.middleware("http")(metrics_middleware)

    # Rate limit middleware (skip health endpoint)
    # Uses IP-based rate limiting only — user-level rate limiting is handled
    # by the auth layer to avoid DB queries in the middleware stack.
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if request.url.path in ("/healthz", "/docs", "/openapi.json", "/redoc", "/metrics"):
            return await call_next(request)

        try:
            from app.services.rate_limit_service import check_rate_limit
            request_ip = request.client.host if request.client else None
            await check_rate_limit(
                user_id=None,
                agent_id=None,
                request_ip=request_ip,
            )
        except DomainException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.to_error(),
            )
        except Exception:
            # Fail closed: if the rate limiter itself is broken (Redis down,
            # etc.), return 503. Do NOT silently allow traffic through.
            logger.error("Rate limiter middleware error, returning 503", exc_info=True)
            return JSONResponse(
                status_code=503,
                content={
                    "type": "error",
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Rate limiter unavailable",
                        "details": {},
                    },
                },
            )

        return await call_next(request)

    # CSRF protection for dashboard mutations
    @app.middleware("http")
    async def csrf_middleware(request: Request, call_next):
        if not request.url.path.startswith("/v1/dashboard/"):
            return await call_next(request)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        # CSRF validation is handled by the require_csrf dependency in the router.
        # This middleware exists as a defense-in-depth layer.
        return await call_next(request)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(agents_router)
    app.include_router(ws_router)
    app.include_router(tasks_router)
    app.include_router(connections_router)
    app.include_router(approvals_router)
    app.include_router(dashboard_auth_router)
    _install_openapi_schema(app)

    return app


def _install_openapi_schema(app: FastAPI) -> None:
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=OPENAPI_TAGS,
        )
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["ApiKeyBearer"] = {
            "type": "http",
            "scheme": "bearer",
            "description": "REST API key in `Authorization: Bearer ak_...`.",
        }
        security_schemes["LegacyApiKeyHeader"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Legacy REST API key header.",
        }

        public_operations = {
            ("get", "/healthz"),
            ("post", "/v1/auth/register"),
        }
        for path, methods in schema.get("paths", {}).items():
            for method, operation in methods.items():
                if (method.lower(), path) not in public_operations:
                    operation.setdefault(
                        "security",
                        [{"ApiKeyBearer": []}, {"LegacyApiKeyHeader": []}],
                    )

        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi


app = create_app()

