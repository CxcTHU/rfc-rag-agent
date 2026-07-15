from hashlib import sha256
from pathlib import Path
from dataclasses import dataclass
import re

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_admin_in_production, require_authenticated_in_production
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
    RetrievalContractHealthResponse,
)
from app.services.retrieval.faiss_index import read_metadata

router = APIRouter(tags=["health"])

_PHASE65_MODEL_PATHS = (
    ("chat", "chat_model_provider", "chat_model_name", True),
    ("runtime_identity", "runtime_identity_model_provider", "runtime_identity_model_name", False),
    ("planner", "planner_chat_model_provider", "planner_chat_model_name", False),
)
_PHASE65_MODEL_IDENTITY_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Phase65ModelInventoryEntry:
    """One non-secret configured model path that can call during ToolCalling."""

    path: str
    identity_sha256: str | None
    configured: bool
    usage_receipt_verified: bool

    def as_safe_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "identity_sha256": self.identity_sha256,
            "configured": self.configured,
            "usage_receipt_verified": self.usage_receipt_verified,
        }


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
    )


@router.get("/health/retrieval-contract", response_model=RetrievalContractHealthResponse)
def retrieval_contract_health(
    _user=Depends(require_authenticated_in_production),
    db: Session = Depends(get_db),
) -> RetrievalContractHealthResponse:
    """Expose only safe configuration and corpus identity for frozen E2E A/B runs."""

    settings = get_settings()
    document_count = db.query(Document).count()
    chunk_count = db.query(Chunk).count()
    corpus_fingerprint = retrieval_corpus_fingerprint(db)
    return RetrievalContractHealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        corpus_fingerprint=corpus_fingerprint,
        index_fingerprint_sha256=retrieval_index_fingerprint_sha256(Path("data/faiss")),
        cold_run_receipts_supported=supports_phase65_cold_run_receipts(settings),
        endpoint_identity_sha256=retrieval_endpoint_identity_sha256(settings, corpus_fingerprint),
        phase65_model_inventory=[
            entry.as_safe_dict() for entry in phase65_model_inventory(settings)
        ],
        chat_model_provider=settings.chat_model_provider,
        chat_model_name=settings.chat_model_name,
        embedding_provider=settings.embedding_provider,
        embedding_model_name=settings.embedding_model_name,
        embedding_dimension=settings.embedding_dimension,
        document_count=document_count,
        chunk_count=chunk_count,
        retrieval_runtime_enabled=settings.retrieval_runtime_enabled,
        retrieval_runtime_default_enabled=settings.retrieval_runtime_default_enabled,
        pgvector_search_enabled=settings.pgvector_search_enabled,
        vector_backend_policy=settings.vector_backend_policy,
        retrieval_runtime_schema=settings.retrieval_runtime_schema,
        agent_short_loop_enabled=settings.agent_short_loop_enabled,
        phase64_route_first_enabled=settings.phase64_route_first_enabled,
        phase64_retrieval_fanout_enabled=settings.phase64_retrieval_fanout_enabled,
        phase64_final_non_thinking_enabled=settings.phase64_final_non_thinking_enabled,
        phase64_execution_graph_schema=settings.phase64_execution_graph_schema,
        reranking_enabled=settings.reranking_enabled,
        reranking_provider=settings.reranking_provider,
        reranking_model_name=settings.reranking_model_name,
        retrieval_candidate_cache_enabled=settings.retrieval_candidate_cache_enabled,
        rerank_order_cache_enabled=settings.rerank_order_cache_enabled,
        tool_result_cache_enabled=settings.tool_result_cache_enabled,
        semantic_evidence_cache_enabled=settings.semantic_evidence_cache_enabled,
    )


def retrieval_endpoint_identity_sha256(settings, corpus_fingerprint: str) -> str:
    """Return a non-secret, stable endpoint identity for A/B lane binding.

    This deliberately hashes only model labels and retrieval-affecting booleans;
    URLs, credentials, prompts, documents, and raw provider settings never leave
    the process through this health endpoint.
    """
    runtime_source = Path(__file__).resolve().parents[1] / "services" / "agent" / "tool_calling_service.py"
    runtime_source_sha256 = sha256(runtime_source.read_bytes()).hexdigest()
    model_inventory_parts = tuple(
        f"{entry.path}:{entry.identity_sha256 or 'unconfigured'}"
        for entry in phase65_model_inventory(settings)
    )
    lane_label = str(getattr(settings, "phase65_endpoint_identity_label", "") or "").strip()
    lane_label_sha256 = sha256(
        f"phase65-endpoint-lane-v1:{lane_label}".encode("utf-8")
    ).hexdigest()
    safe_parts = (
        "phase65-endpoint-identity-v1",
        corpus_fingerprint,
        lane_label_sha256,
        settings.app_name,
        settings.app_env,
        settings.chat_model_provider,
        settings.chat_model_name,
        settings.embedding_provider,
        settings.embedding_model_name,
        str(settings.embedding_dimension),
        settings.reranking_provider,
        settings.reranking_model_name,
        settings.retrieval_runtime_schema,
        settings.phase64_execution_graph_schema,
        str(settings.retrieval_runtime_enabled),
        str(settings.pgvector_search_enabled),
        str(settings.reranking_enabled),
        str(settings.retrieval_candidate_cache_enabled),
        str(settings.rerank_order_cache_enabled),
        str(settings.tool_result_cache_enabled),
        str(settings.semantic_evidence_cache_enabled),
        *model_inventory_parts,
        runtime_source_sha256,
    )
    return sha256("\n".join(safe_parts).encode("utf-8")).hexdigest()


def supports_phase65_cold_run_receipts(settings) -> bool:
    """Return a conservative capability claim, never a promise from configuration alone."""
    chat_provider = str(getattr(settings, "chat_model_provider", "")).strip()
    chat_model = str(getattr(settings, "chat_model_name", "")).strip()
    supported_provider = chat_provider.casefold() in {
        "openai-compatible",
        "openai",
        "compatible",
        "domestic",
    }
    inventory = phase65_model_inventory(settings)
    return bool(
        supported_provider
        and chat_model
        and getattr(settings, "phase65_cold_run_receipts_enabled", False)
        and getattr(settings, "phase65_provider_usage_receipts_verified", False)
        and inventory
        and all(entry.configured and entry.usage_receipt_verified for entry in inventory)
    )


def phase65_model_inventory(settings) -> tuple[Phase65ModelInventoryEntry, ...]:
    """Describe every configured ToolCalling model path using hashes only.

    ToolCalling can use its main chat provider for tools/final generation and may
    use independent runtime-identity or planner configuration for identity/HyDE.
    The inventory deliberately never includes URLs, keys, prompts, or raw model
    labels. An operator must bind each enabled path to a separately verified
    provider usage/cost receipt before Phase 65 live execution becomes available.
    """

    declared = _parse_phase65_usage_receipt_inventory(
        str(getattr(settings, "phase65_provider_usage_receipt_inventory", "") or "")
    )
    entries: list[Phase65ModelInventoryEntry] = []
    for path, provider_field, model_field, required in _PHASE65_MODEL_PATHS:
        provider = str(getattr(settings, provider_field, "") or "").strip()
        model = str(getattr(settings, model_field, "") or "").strip()
        enabled = required or bool(provider or model)
        if not enabled:
            continue
        configured = bool(provider and model)
        identity_sha256 = (
            sha256(f"phase65-model-identity-v1:{provider}:{model}".encode("utf-8")).hexdigest()
            if configured
            else None
        )
        entries.append(
            Phase65ModelInventoryEntry(
                path=path,
                identity_sha256=identity_sha256,
                configured=configured,
                usage_receipt_verified=bool(
                    identity_sha256 and declared.get(path) == identity_sha256
                ),
            )
        )
    return tuple(entries)


def phase65_usage_receipt_inventory_value(
    entries: list[Phase65ModelInventoryEntry] | tuple[Phase65ModelInventoryEntry, ...],
) -> str:
    """Format a safe operator-facing inventory value from endpoint hash receipts."""

    if any(not entry.identity_sha256 for entry in entries):
        raise ValueError("phase65_model_identity_unavailable")
    return ";".join(
        f"{entry.path}=sha256:{entry.identity_sha256}"
        for entry in sorted(entries, key=lambda item: item.path)
    )


def _parse_phase65_usage_receipt_inventory(value: str) -> dict[str, str]:
    if not value.strip():
        return {}
    valid_paths = {item[0] for item in _PHASE65_MODEL_PATHS}
    parsed: dict[str, str] = {}
    for component in value.split(";"):
        path, separator, receipt = component.strip().partition("=")
        if not separator or path not in valid_paths or path in parsed:
            return {}
        prefix, receipt_separator, digest = receipt.strip().partition(":")
        if (
            receipt_separator != ":"
            or prefix != "sha256"
            or not _PHASE65_MODEL_IDENTITY_SHA256.fullmatch(digest)
        ):
            return {}
        parsed[path] = digest
    return parsed


def retrieval_corpus_fingerprint(db: Session) -> str:
    """Hash only stable metadata; never expose document or chunk content."""

    digest = sha256()
    for document in db.query(Document.id, Document.content_hash).order_by(Document.id):
        digest.update(f"document:{document.id}:{document.content_hash}\\n".encode("utf-8"))
    for chunk in db.query(
        Chunk.id,
        Chunk.document_id,
        Chunk.chunk_index,
        Chunk.chunk_type,
    ).order_by(Chunk.id):
        digest.update(
            f"chunk:{chunk.id}:{chunk.document_id}:{chunk.chunk_index}:{chunk.chunk_type}\\n".encode(
                "utf-8"
            )
        )
    return digest.hexdigest()


def retrieval_index_fingerprint_sha256(index_dir: Path) -> str:
    """Hash index bytes locally without exposing filenames or index content."""
    digest = sha256()
    if index_dir.exists():
        for candidate in sorted(path for path in index_dir.iterdir() if path.is_file()):
            digest.update(sha256(candidate.read_bytes()).digest())
    return digest.hexdigest()


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
