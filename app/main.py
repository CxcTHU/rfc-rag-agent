from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api.agent import router as agent_router
from app.api.assets import IMAGE_ASSETS_DIR
from app.api.assets import router as assets_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.frontend import FRONTEND_DIR
from app.api.frontend import REACT_FRONTEND_DIST_DIR
from app.api.frontend import router as frontend_router
from app.api.feedback import router as feedback_router
from app.api.feedback_export import router as feedback_export_router
from app.api.health import router as health_router
from app.api.image_upload import router as image_upload_router
from app.api.search import router as search_router
from app.api.sources import router as sources_router
from app.core.config import get_settings
from app.core.request_logger import (
    finish_request_trace,
    reset_request_trace,
    start_request_trace,
)
from app.core.structured_logging import (
    configure_structured_logging,
    log_event,
    new_request_id,
    reset_request_id,
    set_request_id,
)
from app.db.session import init_db
from app.middleware.rate_limit import RateLimitMiddleware


request_logger = logging.getLogger("rfc_rag_agent.request")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    configure_structured_logging()
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Citation-first RAG agent for rock-filled concrete knowledge retrieval.",
        lifespan=lifespan,
    )
    app.add_middleware(RateLimitMiddleware)

    @app.middleware("http")
    async def structured_request_logging(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        token = set_request_id(request_id)
        trace_token = start_request_trace(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
            log_event(
                request_logger,
                "request_failed",
                method=request.method,
                path=request.url.path,
                status_code=500,
                latency_ms=latency_ms,
            )
            finish_request_trace(
                status_code=500,
                latency_ms=latency_ms,
                error_type="unhandled_exception",
            )
            reset_request_trace(trace_token)
            reset_request_id(token)
            raise
        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        log_event(
            request_logger,
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )
        finish_request_trace(
            status_code=response.status_code,
            latency_ms=latency_ms,
        )
        response.headers["X-Request-ID"] = request_id
        reset_request_trace(trace_token)
        reset_request_id(token)
        return response

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(search_router)
    app.include_router(chat_router)
    app.include_router(conversations_router)
    app.include_router(sources_router)
    app.include_router(agent_router)
    app.include_router(image_upload_router)
    app.include_router(feedback_router)
    app.include_router(feedback_export_router)
    IMAGE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    app.include_router(assets_router)
    app.mount(
        "/assets",
        StaticFiles(directory=REACT_FRONTEND_DIST_DIR / "assets", check_dir=False),
        name="react-assets",
    )
    app.mount(
        "/static",
        StaticFiles(directory=FRONTEND_DIR / "static"),
        name="static",
    )
    app.include_router(frontend_router)
    return app


app = create_app()
