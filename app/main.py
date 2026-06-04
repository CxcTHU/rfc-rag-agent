from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.search import router as search_router
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
    app.include_router(health_router)
    app.include_router(documents_router)
    app.include_router(search_router)
    return app


app = create_app()
