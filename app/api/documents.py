import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document
from app.db.repositories import DocumentRepository
from app.db.session import get_db
from app.schemas.document import (
    DocumentChunkItem,
    DocumentChunksResponse,
    DocumentImportResponse,
    DocumentListItem,
    DocumentListResponse,
)
from app.services.ingestion.parser import UnsupportedDocumentTypeError
from app.services.ingestion.service import (
    EmptyDocumentError,
    IngestionConfig,
    IngestionService,
)

router = APIRouter(prefix="/documents", tags=["documents"])
ROOT_DIR = Path(__file__).resolve().parents[2]


def get_ingestion_config() -> IngestionConfig:
    settings = get_settings()
    return IngestionConfig(raw_dir=settings.raw_data_dir)


@router.post("/import", response_model=DocumentImportResponse)
def import_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
    ingestion_config: IngestionConfig = Depends(get_ingestion_config),
) -> DocumentImportResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename.",
        )

    safe_filename = Path(file.filename).name
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / safe_filename
        with temp_path.open("wb") as output:
            shutil.copyfileobj(file.file, output)

        try:
            result = IngestionService(db, ingestion_config).import_document(
                temp_path,
                title=title,
                source_path=safe_filename,
                file_name=safe_filename,
            )
        except UnsupportedDocumentTypeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except EmptyDocumentError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    return DocumentImportResponse(
        document_id=result.document_id,
        title=result.title,
        chunk_count=result.chunk_count,
        status=result.status,
        content_hash=result.content_hash,
        raw_path=result.raw_path,
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(
    db: Session = Depends(get_db),
    ingestion_config: IngestionConfig = Depends(get_ingestion_config),
) -> DocumentListResponse:
    repository = DocumentRepository(db)
    documents = repository.list_documents()
    return DocumentListResponse(
        documents=[
            DocumentListItem(
                id=document.id,
                title=document.title,
                source_type=document.source_type,
                source_path=document.source_path,
                open_url=document_open_url(document, ingestion_config.raw_dir),
                file_name=document.file_name,
                file_extension=document.file_extension,
                status=document.status,
                chunk_count=repository.count_chunks(document.id),
                created_at=document.created_at,
            )
            for document in documents
        ]
    )


@router.get("/{document_id}/open", include_in_schema=False)
def open_document(
    document_id: int,
    db: Session = Depends(get_db),
    ingestion_config: IngestionConfig = Depends(get_ingestion_config),
):
    repository = DocumentRepository(db)
    document = repository.get_by_id(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} was not found.",
        )

    external_url = first_external_document_url(document)
    if external_url is not None:
        return RedirectResponse(external_url)

    local_path = resolve_document_file(document, ingestion_config.raw_dir)
    if local_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} original file was not found.",
        )
    return FileResponse(local_path)


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
def list_document_chunks(
    document_id: int,
    db: Session = Depends(get_db),
) -> DocumentChunksResponse:
    repository = DocumentRepository(db)
    document = repository.get_by_id(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} was not found.",
        )

    chunks = repository.list_chunks(document_id)
    return DocumentChunksResponse(
        document_id=document.id,
        title=document.title,
        source_path=document.source_path,
        file_name=document.file_name,
        chunk_count=len(chunks),
        chunks=[
            DocumentChunkItem(
                id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                char_count=chunk.char_count,
                heading_path=chunk.heading_path,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                chunk_type=chunk.chunk_type,
                source_image_path=chunk.source_image_path,
                caption=chunk.caption,
                page_number=chunk.page_number,
                created_at=chunk.created_at,
            )
            for chunk in chunks
        ],
    )


def document_open_url(document: Document, raw_dir: str | Path) -> str | None:
    if first_external_document_url(document) is not None:
        return f"/documents/{document.id}/open"
    if resolve_document_file(document, raw_dir) is None:
        return None
    return f"/documents/{document.id}/open"


def first_external_document_url(document: Document) -> str | None:
    for value in (document.source_path,):
        if is_http_url(value):
            return value
    return None


def resolve_document_file(document: Document, raw_dir: str | Path) -> Path | None:
    raw_root = resolve_raw_root(raw_dir)
    candidates: list[Path] = []
    for value in (document.raw_path, document.source_path):
        if value and not is_http_url(value):
            candidates.extend(path_candidates(value, raw_root))
    if document.file_name:
        candidates.append(raw_root / Path(document.file_name).name)

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = safe_resolve(candidate)
        if resolved is None or resolved in seen:
            continue
        seen.add(resolved)
        if is_path_within(resolved, raw_root) and resolved.is_file():
            return resolved
    return None


def path_candidates(value: str, raw_root: Path) -> list[Path]:
    path = Path(value)
    if path.is_absolute():
        return [path]
    return [
        ROOT_DIR / path,
        raw_root / path,
        raw_root / path.name,
    ]


def resolve_raw_root(raw_dir: str | Path) -> Path:
    raw_path = Path(raw_dir)
    if not raw_path.is_absolute():
        raw_path = ROOT_DIR / raw_path
    resolved = safe_resolve(raw_path)
    return resolved or raw_path


def safe_resolve(path: Path) -> Path | None:
    try:
        return path.resolve()
    except (OSError, RuntimeError):
        return None


def is_path_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def is_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
