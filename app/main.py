from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.agent import router as agent_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.frontend import FRONTEND_DIR
from app.api.frontend import router as frontend_router
from app.api.health import router as health_router
from app.api.search import router as search_router
from app.api.sources import router as sources_router
from app.core.config import get_settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Citation-first RAG agent for rock-filled concrete knowledge retrieval.",
        lifespan=lifespan,
    )
    app.include_router(frontend_router)
    app.include_router(health_router)
    app.include_router(documents_router)
    app.include_router(search_router)
    app.include_router(chat_router)
    app.include_router(sources_router)
    app.include_router(agent_router)
    app.mount(
        "/static",
        StaticFiles(directory=FRONTEND_DIR / "static"),
        name="static",
    )
    return app


app = create_app()
