import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings

logger = logging.getLogger(__name__)
from app.exceptions import DomainException, domain_exception_handler
from app.logging import configure_logging
from app.routers.agents import router as agents_router
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.ws import router as ws_router
from app.routers.tasks import router as tasks_router
from app.routers.connections import router as connections_router
from app.routers.approvals import router as approvals_router
from app.websocket.manager import get_connection_manager


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

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_exception_handler(DomainException, domain_exception_handler)

    # Rate limit middleware (skip health endpoint)
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if request.url.path in ("/healthz", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        try:
            from app.services.rate_limit_service import check_rate_limit

            user_id = None
            agent_id = None
            request_ip = request.client.host if request.client else None

            # Try to extract user from X-API-Key or Authorization header (non-blocking for unauthed paths)
            x_api_key = request.headers.get("X-API-Key")
            if not x_api_key:
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    x_api_key = auth_header[7:]
            if x_api_key:
                import hashlib
                from sqlalchemy import select
                from app.database import SessionLocal
                from app.models.api_key import ApiKey

                key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
                async with SessionLocal() as session:
                    result = await session.execute(
                        select(ApiKey).where(
                            ApiKey.key_hash == key_hash,
                            ApiKey.is_revoked == False,
                        )
                    )
                    api_key = result.scalar_one_or_none()
                    if api_key:
                        user_id = str(api_key.user_id)

            await check_rate_limit(
                user_id=user_id,
                agent_id=agent_id,
                request_ip=request_ip,
            )
        except DomainException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.to_error(),
            )
        except Exception:
            logger.error("Rate limiter middleware unexpected error", exc_info=True)
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

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(agents_router)
    app.include_router(ws_router)
    app.include_router(tasks_router)
    app.include_router(connections_router)
    app.include_router(approvals_router)

    return app


app = create_app()

