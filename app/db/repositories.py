import json
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document, QuestionAnswerLog


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


@dataclass(frozen=True)
class ChunkEmbeddingCreate:
    chunk_id: int
    provider: str
    model_name: str
    dimension: int
    embedding: Sequence[float]
    content_hash: str


@dataclass(frozen=True)
class QuestionAnswerLogCreate:
    question: str
    answer: str
    retrieved_chunk_ids: Sequence[int]
    citations: Sequence[int]
    model_provider: str
    model_name: str
    retrieval_mode: str
    refused: bool
    refusal_reason: str | None = None


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


class ChunkEmbeddingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_embedding(
        self,
        embedding_data: ChunkEmbeddingCreate,
        commit: bool = True,
    ) -> ChunkEmbedding:
        existing_embedding = self.get_embedding(
            chunk_id=embedding_data.chunk_id,
            provider=embedding_data.provider,
            model_name=embedding_data.model_name,
        )
        embedding_json = serialize_embedding(embedding_data.embedding)
        if existing_embedding is not None:
            existing_embedding.dimension = embedding_data.dimension
            existing_embedding.embedding_json = embedding_json
            existing_embedding.content_hash = embedding_data.content_hash
            if commit:
                self.db.commit()
                self.db.refresh(existing_embedding)
            return existing_embedding

        chunk_embedding = ChunkEmbedding(
            chunk_id=embedding_data.chunk_id,
            provider=embedding_data.provider,
            model_name=embedding_data.model_name,
            dimension=embedding_data.dimension,
            embedding_json=embedding_json,
            content_hash=embedding_data.content_hash,
        )
        self.db.add(chunk_embedding)
        if commit:
            self.db.commit()
            self.db.refresh(chunk_embedding)
        return chunk_embedding

    def get_embedding(
        self,
        chunk_id: int,
        provider: str,
        model_name: str,
    ) -> ChunkEmbedding | None:
        statement = select(ChunkEmbedding).where(
            ChunkEmbedding.chunk_id == chunk_id,
            ChunkEmbedding.provider == provider,
            ChunkEmbedding.model_name == model_name,
        )
        return self.db.scalar(statement)

    def list_embeddings(
        self,
        provider: str | None = None,
        model_name: str | None = None,
    ) -> list[ChunkEmbedding]:
        statement = select(ChunkEmbedding).order_by(ChunkEmbedding.id)
        if provider is not None:
            statement = statement.where(ChunkEmbedding.provider == provider)
        if model_name is not None:
            statement = statement.where(ChunkEmbedding.model_name == model_name)
        return list(self.db.scalars(statement).all())

    def count_embeddings(
        self,
        provider: str | None = None,
        model_name: str | None = None,
    ) -> int:
        statement = select(func.count(ChunkEmbedding.id))
        if provider is not None:
            statement = statement.where(ChunkEmbedding.provider == provider)
        if model_name is not None:
            statement = statement.where(ChunkEmbedding.model_name == model_name)
        return self.db.scalar(statement) or 0


class QuestionAnswerLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_log(
        self,
        log_data: QuestionAnswerLogCreate,
        commit: bool = True,
    ) -> QuestionAnswerLog:
        log = QuestionAnswerLog(
            question=log_data.question,
            answer=log_data.answer,
            retrieved_chunk_ids=serialize_int_list(log_data.retrieved_chunk_ids),
            citations=serialize_int_list(log_data.citations),
            model_provider=log_data.model_provider,
            model_name=log_data.model_name,
            retrieval_mode=log_data.retrieval_mode,
            refused=log_data.refused,
            refusal_reason=log_data.refusal_reason,
        )
        self.db.add(log)
        if commit:
            self.db.commit()
            self.db.refresh(log)
        return log

    def get_by_id(self, log_id: int) -> QuestionAnswerLog | None:
        statement = select(QuestionAnswerLog).where(QuestionAnswerLog.id == log_id)
        return self.db.scalar(statement)

    def list_logs(self) -> list[QuestionAnswerLog]:
        statement = select(QuestionAnswerLog).order_by(QuestionAnswerLog.id)
        return list(self.db.scalars(statement).all())

    def count_logs(self) -> int:
        statement = select(func.count(QuestionAnswerLog.id))
        return self.db.scalar(statement) or 0


def serialize_embedding(embedding: Sequence[float]) -> str:
    return json.dumps([float(value) for value in embedding], separators=(",", ":"))


def deserialize_embedding(embedding_json: str) -> list[float]:
    values = json.loads(embedding_json)
    if not isinstance(values, list):
        raise ValueError("embedding_json must contain a JSON list")
    return [float(value) for value in values]


def serialize_int_list(values: Sequence[int]) -> str:
    return json.dumps([int(value) for value in values], separators=(",", ":"))


def deserialize_int_list(values_json: str) -> list[int]:
    values = json.loads(values_json)
    if not isinstance(values, list):
        raise ValueError("values_json must contain a JSON list")
    return [int(value) for value in values]
