from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document


@dataclass(frozen=True)
class DocumentCreate:
    title: str
    source_type: str
    source_path: str | None
    file_name: str
    file_extension: str
    content_hash: str
    raw_path: str
    status: str = "imported"


@dataclass(frozen=True)
class ChunkCreate:
    chunk_index: int
    content: str
    char_count: int
    heading_path: str | None
    start_char: int | None
    end_char: int | None


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_with_chunks(
        self,
        document_data: DocumentCreate,
        chunks_data: Sequence[ChunkCreate],
    ) -> Document:
        document = Document(
            title=document_data.title,
            source_type=document_data.source_type,
            source_path=document_data.source_path,
            file_name=document_data.file_name,
            file_extension=document_data.file_extension,
            content_hash=document_data.content_hash,
            raw_path=document_data.raw_path,
            status=document_data.status,
            chunks=[
                Chunk(
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    char_count=chunk.char_count,
                    heading_path=chunk.heading_path,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                )
                for chunk in chunks_data
            ],
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_by_content_hash(self, content_hash: str) -> Document | None:
        statement = select(Document).where(Document.content_hash == content_hash)
        return self.db.scalar(statement)

    def get_by_id(self, document_id: int) -> Document | None:
        statement = select(Document).where(Document.id == document_id)
        return self.db.scalar(statement)

    def list_documents(self) -> list[Document]:
        statement = select(Document).order_by(Document.id)
        return list(self.db.scalars(statement).all())

    def list_chunks(self, document_id: int) -> list[Chunk]:
        statement = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        return list(self.db.scalars(statement).all())

    def count_chunks(self, document_id: int) -> int:
        statement = select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
        return self.db.scalar(statement) or 0
