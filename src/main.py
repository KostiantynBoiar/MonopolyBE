import asyncio
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.router import api_router
from core.config import get_settings
from core.exceptions import AppError
from core.logging import setup_logging
from gateway.backplane import Backplane
from gateway.manager import ConnectionManager
from gateway.router import ws_router
from infra.mongo.client import MongoClient
from infra.mongo.indexes import ensure_indexes
from infra.redis.client import RedisClient

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings)

    mongo = MongoClient()
    redis = RedisClient()

    await mongo.connect(settings)
    await redis.connect(settings)
    await ensure_indexes(mongo.db)

    manager = ConnectionManager()
    backplane = Backplane(redis_url=settings.redis_url, manager=manager)
    await backplane.start()

    app.state.mongo = mongo
    app.state.redis = redis
    app.state.manager = manager
    app.state.backplane = backplane

    logger.info("application_started", app_env=settings.app_env)

    yield

    for conn in manager.all_connections():
        await conn.close(1001)
    await backplane.stop()

    await redis.disconnect()
    await mongo.disconnect()

    logger.info("application_stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Monopoly API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(ws_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready(request: Request) -> JSONResponse:
        mongo: MongoClient = request.app.state.mongo
        redis: RedisClient = request.app.state.redis

        checks: dict[str, str] = {"mongo": "ok", "redis": "ok"}
        failed = False

        async def check_mongo() -> None:
            nonlocal failed
            try:
                await mongo.ping()
            except Exception:
                checks["mongo"] = "error"
                failed = True

        async def check_redis() -> None:
            nonlocal failed
            try:
                await redis.ping()
            except Exception:
                checks["redis"] = "error"
                failed = True

        await asyncio.gather(check_mongo(), check_redis())

        body: dict[str, Any] = {"status": "ok" if not failed else "degraded", **checks}
        response_status = status.HTTP_200_OK if not failed else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(content=body, status_code=response_status)

    return app


app = create_app()
