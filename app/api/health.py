from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_admin_in_production
from app.db.models import Chunk, Document
from app.db.session import get_db
from app.schemas.health import (
    DatabaseHealth,
    FaissHealth,
    FaissIndexHealth,
    HealthDetailsResponse,
    HealthResponse,
    ProviderConfigHealth,
    ProviderItemHealth,
)
from app.services.retrieval.faiss_index import read_metadata

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
    )


@router.get("/health/details", response_model=HealthDetailsResponse)
def health_details(
    _admin=Depends(require_admin_in_production),
    db: Session = Depends(get_db),
) -> HealthDetailsResponse:
    settings = get_settings()
    database = inspect_database(db)
    faiss = inspect_faiss(Path("data/faiss"))
    providers = inspect_provider_config(settings)
    overall_status = aggregate_status(
        database.status,
        faiss.status,
        providers.status,
    )
    return HealthDetailsResponse(
        status=overall_status,
        service=settings.app_name,
        environment=settings.app_env,
        database=database,
        faiss=faiss,
        providers=providers,
    )


def inspect_database(db: Session) -> DatabaseHealth:
    try:
        db.execute(text("SELECT 1"))
        document_count = db.query(Document).count()
        chunk_count = db.query(Chunk).count()
    except Exception as exc:  # pragma: no cover - driver-specific formatting
        return DatabaseHealth(
            status="error",
            connected=False,
            error=exc.__class__.__name__,
        )
    return DatabaseHealth(
        status="ok",
        connected=True,
        document_count=document_count,
        chunk_count=chunk_count,
    )


def inspect_faiss(index_dir: Path) -> FaissHealth:
    candidates = discover_faiss_indexes(index_dir)
    if not candidates:
        return FaissHealth(
            status="missing",
            index_dir=str(index_dir),
            index_count=0,
            indexes=[],
        )

    indexes = [inspect_faiss_index(index_path, metadata_path) for index_path, metadata_path in candidates]
    status = "ok"
    if any(index.status == "error" for index in indexes):
        status = "error"
    elif any(index.status in {"missing", "incomplete"} for index in indexes):
        status = "degraded"

    return FaissHealth(
        status=status,
        index_dir=str(index_dir),
        index_count=len(indexes),
        indexes=indexes,
    )


def discover_faiss_indexes(index_dir: Path) -> list[tuple[Path, Path]]:
    if not index_dir.exists():
        return []

    pairs: dict[str, tuple[Path | None, Path | None]] = {}
    for index_path in index_dir.glob("*.index"):
        pairs[index_path.stem] = (index_path, pairs.get(index_path.stem, (None, None))[1])
    for metadata_path in index_dir.glob("*_ids.json"):
        stem = metadata_path.name[: -len("_ids.json")]
        pairs[stem] = (pairs.get(stem, (None, None))[0], metadata_path)

    discovered: list[tuple[Path, Path]] = []
    for stem in sorted(pairs):
        index_path, metadata_path = pairs[stem]
        discovered.append(
            (
                index_path or index_dir / f"{stem}.index",
                metadata_path or index_dir / f"{stem}_ids.json",
            )
        )
    return discovered


def inspect_faiss_index(index_path: Path, metadata_path: Path) -> FaissIndexHealth:
    index_exists = index_path.exists()
    metadata_exists = metadata_path.exists()
    if not index_exists or not metadata_exists:
        return FaissIndexHealth(
            status="missing",
            index_path=str(index_path),
            metadata_path=str(metadata_path),
            index_exists=index_exists,
            metadata_exists=metadata_exists,
        )

    try:
        metadata = read_metadata(metadata_path)
    except Exception as exc:
        return FaissIndexHealth(
            status="error",
            index_path=str(index_path),
            metadata_path=str(metadata_path),
            index_exists=True,
            metadata_exists=True,
            error=exc.__class__.__name__,
        )

    status = "ok" if metadata.complete else "incomplete"
    return FaissIndexHealth(
        status=status,
        provider=metadata.provider,
        model_name=metadata.model_name,
        dimension=metadata.dimension,
        metric=metadata.metric,
        normalized=metadata.normalized,
        complete=metadata.complete,
        vector_count=len(metadata.chunk_ids),
        index_path=str(index_path),
        metadata_path=str(metadata_path),
        index_exists=True,
        metadata_exists=True,
    )


def inspect_provider_config(settings) -> ProviderConfigHealth:
    chat = provider_item(
        provider=settings.chat_model_provider,
        model_name=settings.chat_model_name,
        configured=bool(settings.chat_model_provider and settings.chat_model_name),
    )
    embedding = provider_item(
        provider=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        configured=bool(
            settings.embedding_provider
            and settings.embedding_model_name
            and settings.embedding_dimension > 0
        ),
    )
    reranking_enabled = bool(settings.reranking_enabled)
    reranking = provider_item(
        provider=settings.reranking_provider,
        model_name=settings.reranking_model_name,
        configured=bool(
            not reranking_enabled
            or (settings.reranking_provider and settings.reranking_model_name)
        ),
        enabled=reranking_enabled,
    )
    status = "ok" if chat.configured and embedding.configured and reranking.configured else "degraded"
    return ProviderConfigHealth(
        status=status,
        chat=chat,
        embedding=embedding,
        reranking=reranking,
        deterministic_available=True,
    )


def provider_item(
    provider: str,
    model_name: str,
    configured: bool,
    enabled: bool = True,
) -> ProviderItemHealth:
    display_provider = provider or "not_configured"
    display_model = model_name or "not_configured"
    return ProviderItemHealth(
        status="ok" if configured else "missing",
        provider=display_provider,
        model_name=display_model,
        configured=configured,
        enabled=enabled,
    )


def aggregate_status(*statuses: str) -> str:
    if any(status == "error" for status in statuses):
        return "error"
    if any(status in {"missing", "degraded"} for status in statuses):
        return "degraded"
    return "ok"
