import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
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
def list_documents(db: Session = Depends(get_db)) -> DocumentListResponse:
    repository = DocumentRepository(db)
    documents = repository.list_documents()
    return DocumentListResponse(
        documents=[
            DocumentListItem(
                id=document.id,
                title=document.title,
                source_type=document.source_type,
                source_path=document.source_path,
                file_name=document.file_name,
                file_extension=document.file_extension,
                status=document.status,
                chunk_count=repository.count_chunks(document.id),
                created_at=document.created_at,
            )
            for document in documents
        ]
    )


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
                created_at=chunk.created_at,
            )
            for chunk in chunks
        ],
    )
