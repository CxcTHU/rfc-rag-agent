from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.services.ingestion.cleaner import clean_text
from app.services.ingestion.loader import store_raw_file
from app.services.ingestion.parser import parse_text_file
from app.services.ingestion.splitter import split_text


class EmptyDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class ImportDocumentResult:
    document_id: int
    title: str
    chunk_count: int
    status: str
    content_hash: str
    raw_path: str


@dataclass(frozen=True)
class IngestionConfig:
    raw_dir: str | Path = "data/raw"
    chunk_size: int = 800
    chunk_overlap: int = 120


class IngestionService:
    def __init__(
        self,
        db: Session,
        config: IngestionConfig | None = None,
    ) -> None:
        self.repository = DocumentRepository(db)
        self.config = config or IngestionConfig()

    def import_document(
        self,
        file_path: str | Path,
        title: str | None = None,
        source_path: str | None = None,
        file_name: str | None = None,
        source_type: str = "local_file",
    ) -> ImportDocumentResult:
        parsed = parse_text_file(file_path, title=title)
        stored_file = store_raw_file(parsed.source_path, raw_dir=self.config.raw_dir)

        existing_document = self.repository.get_by_content_hash(stored_file.content_hash)
        if existing_document is not None:
            return ImportDocumentResult(
                document_id=existing_document.id,
                title=existing_document.title,
                chunk_count=self.repository.count_chunks(existing_document.id),
                status="duplicate",
                content_hash=existing_document.content_hash,
                raw_path=existing_document.raw_path,
            )

        cleaned_content = clean_text(parsed.content)
        chunks = split_text(
            cleaned_content,
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )
        if not chunks:
            raise EmptyDocumentError(f"No importable text found in {file_path}")

        document = self.repository.create_with_chunks(
            DocumentCreate(
                title=parsed.title,
                source_type=source_type,
                source_path=source_path or parsed.source_path,
                file_name=file_name or parsed.file_name,
                file_extension=parsed.file_extension,
                content_hash=stored_file.content_hash,
                raw_path=stored_file.raw_path,
                status="imported",
            ),
            [
                ChunkCreate(
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    char_count=chunk.char_count,
                    heading_path=chunk.heading_path,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                )
                for chunk in chunks
            ],
        )

        return ImportDocumentResult(
            document_id=document.id,
            title=document.title,
            chunk_count=len(chunks),
            status=document.status,
            content_hash=document.content_hash,
            raw_path=document.raw_path,
        )
