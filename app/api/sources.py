from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.path_safety import ensure_path_within_allowed_roots, parse_allowed_roots
from app.core.security import get_current_user, require_admin_when_auth_enabled
from app.db.repositories import SourceRepository
from app.db.session import get_db
from app.schemas.source import (
    SourceItem,
    SourceListResponse,
    SourceReindexRequest,
    SourceReindexResponse,
    SourceSyncRequest,
    SourceSyncResponse,
)
from app.services.ingestion.service import IngestionConfig
from app.services.source_registry import (
    SourceNotFoundError,
    SourceRegistryService,
    SourceReindexError,
)
from scripts.sync_sources import resolve_source_paths, sync_sources

router = APIRouter(prefix="/sources", tags=["sources"])


def get_source_ingestion_config() -> IngestionConfig:
    settings = get_settings()
    return IngestionConfig(raw_dir=settings.raw_data_dir)


@router.get("", response_model=SourceListResponse)
def list_sources(
    status: str | None = Query(default=None),
    fulltext_permission: str | None = Query(default=None),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceListResponse:
    repository = SourceRepository(db)
    sources = repository.list_sources(
        status=status,
        fulltext_permission=fulltext_permission,
    )
    return SourceListResponse(sources=[to_source_item(source) for source in sources])


@router.get("/{source_id}", response_model=SourceItem)
def get_source(
    source_id: str,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceItem:
    source = SourceRepository(db).get_by_source_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source {source_id} was not found.")
    return to_source_item(source)


@router.post("/sync", response_model=SourceSyncResponse)
def sync_source_registry(
    request: SourceSyncRequest,
    settings: Settings = Depends(get_settings),
    _admin=Depends(require_admin_when_auth_enabled),
    db: Session = Depends(get_db),
) -> SourceSyncResponse:
    allowed_roots = parse_allowed_roots(settings.source_sync_allowed_roots)
    try:
        candidate_csvs = [
            ensure_path_within_allowed_roots(path, allowed_roots)
            for path in request.candidate_csvs
        ]
        fulltext_manifests = [
            ensure_path_within_allowed_roots(path, allowed_roots)
            for path in request.fulltext_manifests
        ]
        metadata_csvs = [
            ensure_path_within_allowed_roots(path, allowed_roots)
            for path in request.metadata_csvs
        ]
        metadata_cards_dirs = [
            ensure_path_within_allowed_roots(path, allowed_roots)
            for path in request.metadata_cards_dirs
        ]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    candidate_csvs, fulltext_manifests, metadata_csvs, metadata_cards_dirs = resolve_source_paths(
        include_defaults=request.include_defaults,
        candidate_csvs=[Path(path) for path in candidate_csvs],
        fulltext_manifests=[Path(path) for path in fulltext_manifests],
        metadata_csvs=[Path(path) for path in metadata_csvs],
        metadata_cards_dirs=[Path(path) for path in metadata_cards_dirs],
    )
    summary = sync_sources(
        db,
        candidate_csv_paths=candidate_csvs,
        fulltext_manifest_paths=fulltext_manifests,
        metadata_csv_paths=metadata_csvs,
        metadata_cards_dirs=metadata_cards_dirs,
    )
    return SourceSyncResponse(
        total=summary.total,
        created=summary.created,
        updated=summary.updated,
        duplicates=summary.duplicates,
    )


@router.post("/{source_id}/reindex", response_model=SourceReindexResponse)
def reindex_source(
    source_id: str,
    request: SourceReindexRequest | None = None,
    settings: Settings = Depends(get_settings),
    _admin=Depends(require_admin_when_auth_enabled),
    db: Session = Depends(get_db),
    ingestion_config: IngestionConfig = Depends(get_source_ingestion_config),
) -> SourceReindexResponse:
    try:
        metadata_cards_dir = (
            ensure_path_within_allowed_roots(
                request.metadata_cards_dir,
                parse_allowed_roots(settings.source_sync_allowed_roots),
            )
            if request is not None and request.metadata_cards_dir
            else Path("data/imports/metadata_corpus")
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        result = SourceRegistryService(SourceRepository(db)).reindex_source(
            source_id,
            ingestion_config=ingestion_config,
            metadata_cards_dir=metadata_cards_dir,
        )
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceReindexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SourceReindexResponse(
        source_id=result.source.source_id,
        document_id=result.import_result.document_id,
        title=result.import_result.title,
        chunk_count=result.import_result.chunk_count,
        import_status=result.import_result.status,
        source_status=result.source.status,
        raw_path=result.import_result.raw_path,
    )


def to_source_item(source) -> SourceItem:
    return SourceItem(
        id=source.id,
        source_id=source.source_id,
        title=source.title,
        authors=source.authors,
        year=source.year,
        venue=source.venue,
        category=source.category,
        discovered_via=source.discovered_via,
        doi=source.doi,
        url=source.url,
        pdf_url=source.pdf_url,
        source_type=source.source_type,
        trust_level=source.trust_level,
        access_rights=source.access_rights,
        fulltext_permission=source.fulltext_permission,
        local_path=source.local_path,
        status=source.status,
        document_id=source.document_id,
        notes=source.notes,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )
