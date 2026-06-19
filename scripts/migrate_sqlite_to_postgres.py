from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import and_, create_engine, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.models import (  # noqa: E402
    Base,
    Chunk,
    ChunkEmbedding,
    Document,
    QuestionAnswerLog,
    Source,
)
from app.db.session import create_database_engine  # noqa: E402


@dataclass
class TableMigrationStats:
    inserted: int = 0
    skipped: int = 0
    updated: int = 0


@dataclass
class MigrationResult:
    documents: TableMigrationStats = field(default_factory=TableMigrationStats)
    sources: TableMigrationStats = field(default_factory=TableMigrationStats)
    chunks: TableMigrationStats = field(default_factory=TableMigrationStats)
    chunk_embeddings: TableMigrationStats = field(default_factory=TableMigrationStats)
    qa_logs: TableMigrationStats = field(default_factory=TableMigrationStats)


def create_source_engine(sqlite_url: str) -> Engine:
    url = make_url(sqlite_url)
    if url.get_backend_name() != "sqlite":
        raise ValueError("source database must be SQLite")
    return create_engine(sqlite_url, connect_args={"check_same_thread": False})


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def migrate_sqlite_to_target(
    source_sqlite_url: str,
    target_database_url: str,
    *,
    create_schema: bool = False,
) -> MigrationResult:
    source_engine = create_source_engine(source_sqlite_url)
    target_engine = create_database_engine(target_database_url)
    if create_schema:
        Base.metadata.create_all(bind=target_engine)

    SourceSession = create_session_factory(source_engine)
    TargetSession = create_session_factory(target_engine)

    with SourceSession() as source_db, TargetSession() as target_db:
        result = MigrationResult()
        document_id_map = migrate_documents(source_db, target_db, result)
        chunk_id_map = migrate_chunks(source_db, target_db, document_id_map, result)
        migrate_sources(source_db, target_db, document_id_map, result)
        migrate_chunk_embeddings(source_db, target_db, chunk_id_map, result)
        migrate_qa_logs(source_db, target_db, result)
        target_db.commit()
        return result


def migrate_documents(
    source_db: Session,
    target_db: Session,
    result: MigrationResult,
) -> dict[int, int]:
    document_id_map: dict[int, int] = {}
    documents = list(source_db.scalars(select(Document).order_by(Document.id)).all())
    existing_by_hash = {
        document.content_hash: document
        for document in target_db.scalars(select(Document).order_by(Document.id)).all()
    }
    for source_document in documents:
        existing = existing_by_hash.get(source_document.content_hash)
        if existing is not None:
            document_id_map[source_document.id] = existing.id
            result.documents.skipped += 1
            continue
        target_document = Document(
            title=source_document.title,
            source_type=source_document.source_type,
            source_path=source_document.source_path,
            file_name=source_document.file_name,
            file_extension=source_document.file_extension,
            content_hash=source_document.content_hash,
            raw_path=source_document.raw_path,
            status=source_document.status,
            created_at=source_document.created_at,
            updated_at=source_document.updated_at,
        )
        target_db.add(target_document)
        target_db.flush()
        existing_by_hash[target_document.content_hash] = target_document
        document_id_map[source_document.id] = target_document.id
        result.documents.inserted += 1
    return document_id_map


def migrate_chunks(
    source_db: Session,
    target_db: Session,
    document_id_map: dict[int, int],
    result: MigrationResult,
) -> dict[int, int]:
    chunk_id_map: dict[int, int] = {}
    chunks = list(source_db.scalars(select(Chunk).order_by(Chunk.id)).all())
    pending_parent_links: list[tuple[Chunk, int | None]] = []

    for source_chunk in chunks:
        target_document_id = document_id_map[source_chunk.document_id]
        existing = target_db.scalar(
            select(Chunk).where(
                Chunk.document_id == target_document_id,
                Chunk.chunk_index == source_chunk.chunk_index,
            )
        )
        if existing is not None:
            chunk_id_map[source_chunk.id] = existing.id
            pending_parent_links.append((existing, source_chunk.parent_chunk_id))
            result.chunks.skipped += 1
            continue

        values = {
            "document_id": target_document_id,
            "chunk_index": source_chunk.chunk_index,
            "content": source_chunk.content,
            "char_count": source_chunk.char_count,
            "heading_path": source_chunk.heading_path,
            "start_char": source_chunk.start_char,
            "end_char": source_chunk.end_char,
            "created_at": source_chunk.created_at,
        }
        if hasattr(Chunk, "chunk_type"):
            values["chunk_type"] = getattr(source_chunk, "chunk_type", "text")
        if hasattr(Chunk, "source_image_path"):
            values["source_image_path"] = getattr(source_chunk, "source_image_path", None)
        target_chunk = Chunk(**values)
        target_db.add(target_chunk)
        target_db.flush()
        chunk_id_map[source_chunk.id] = target_chunk.id
        pending_parent_links.append((target_chunk, source_chunk.parent_chunk_id))
        result.chunks.inserted += 1

    for target_chunk, source_parent_id in pending_parent_links:
        mapped_parent_id = chunk_id_map.get(source_parent_id) if source_parent_id is not None else None
        if target_chunk.parent_chunk_id != mapped_parent_id:
            target_chunk.parent_chunk_id = mapped_parent_id
            result.chunks.updated += 1
    target_db.flush()
    return chunk_id_map


def migrate_sources(
    source_db: Session,
    target_db: Session,
    document_id_map: dict[int, int],
    result: MigrationResult,
) -> None:
    sources = list(source_db.scalars(select(Source).order_by(Source.id)).all())
    existing_by_source_id = {
        source.source_id: source
        for source in target_db.scalars(select(Source).order_by(Source.id)).all()
    }
    for source in sources:
        mapped_document_id = (
            document_id_map[source.document_id]
            if source.document_id is not None and source.document_id in document_id_map
            else None
        )
        if source.source_id in existing_by_source_id:
            result.sources.skipped += 1
            continue
        target_source = Source(
            source_id=source.source_id,
            title=source.title,
            normalized_title=source.normalized_title,
            authors=source.authors,
            year=source.year,
            venue=source.venue,
            category=source.category,
            discovered_via=source.discovered_via,
            doi=source.doi,
            normalized_doi=source.normalized_doi,
            url=source.url,
            normalized_url=source.normalized_url,
            pdf_url=source.pdf_url,
            abstract=source.abstract,
            keywords=source.keywords,
            language=source.language,
            citation_count=source.citation_count,
            source_type=source.source_type,
            trust_level=source.trust_level,
            access_rights=source.access_rights,
            fulltext_permission=source.fulltext_permission,
            license_or_terms=source.license_or_terms,
            local_path=source.local_path,
            status=source.status,
            notes=source.notes,
            document_id=mapped_document_id,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )
        target_db.add(target_source)
        existing_by_source_id[target_source.source_id] = target_source
        result.sources.inserted += 1


def migrate_chunk_embeddings(
    source_db: Session,
    target_db: Session,
    chunk_id_map: dict[int, int],
    result: MigrationResult,
) -> None:
    embeddings = list(source_db.scalars(select(ChunkEmbedding).order_by(ChunkEmbedding.id)).all())
    for embedding in embeddings:
        target_chunk_id = chunk_id_map.get(embedding.chunk_id)
        if target_chunk_id is None:
            result.chunk_embeddings.skipped += 1
            continue
        existing = target_db.scalar(
            select(ChunkEmbedding).where(
                ChunkEmbedding.chunk_id == target_chunk_id,
                ChunkEmbedding.provider == embedding.provider,
                ChunkEmbedding.model_name == embedding.model_name,
            )
        )
        if existing is not None:
            result.chunk_embeddings.skipped += 1
            continue
        target_embedding = ChunkEmbedding(
            chunk_id=target_chunk_id,
            provider=embedding.provider,
            model_name=embedding.model_name,
            dimension=embedding.dimension,
            embedding_json=embedding.embedding_json,
            content_hash=embedding.content_hash,
            created_at=embedding.created_at,
            updated_at=embedding.updated_at,
        )
        target_db.add(target_embedding)
        result.chunk_embeddings.inserted += 1


def migrate_qa_logs(
    source_db: Session,
    target_db: Session,
    result: MigrationResult,
) -> None:
    logs = list(source_db.scalars(select(QuestionAnswerLog).order_by(QuestionAnswerLog.id)).all())
    for log in logs:
        existing = target_db.scalar(
            select(QuestionAnswerLog).where(
                and_(
                    QuestionAnswerLog.question == log.question,
                    QuestionAnswerLog.answer == log.answer,
                    QuestionAnswerLog.model_provider == log.model_provider,
                    QuestionAnswerLog.model_name == log.model_name,
                    QuestionAnswerLog.retrieval_mode == log.retrieval_mode,
                    QuestionAnswerLog.created_at == log.created_at,
                )
            )
        )
        if existing is not None:
            result.qa_logs.skipped += 1
            continue
        target_log = QuestionAnswerLog(
            question=log.question,
            answer=log.answer,
            retrieved_chunk_ids=log.retrieved_chunk_ids,
            citations=log.citations,
            model_provider=log.model_provider,
            model_name=log.model_name,
            retrieval_mode=log.retrieval_mode,
            refused=log.refused,
            refusal_reason=log.refusal_reason,
            created_at=log.created_at,
        )
        target_db.add(target_log)
        result.qa_logs.inserted += 1


def format_result(result: MigrationResult) -> str:
    rows = []
    for name in ["documents", "sources", "chunks", "chunk_embeddings", "qa_logs"]:
        stats = getattr(result, name)
        rows.append(
            f"{name}: inserted={stats.inserted} skipped={stats.skipped} updated={stats.updated}"
        )
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incrementally migrate RFC-RAG local SQLite data into PostgreSQL."
    )
    parser.add_argument("--source-sqlite-url", required=True)
    parser.add_argument("--target-database-url", required=True)
    parser.add_argument("--create-schema", action="store_true")
    args = parser.parse_args()

    result = migrate_sqlite_to_target(
        source_sqlite_url=args.source_sqlite_url,
        target_database_url=args.target_database_url,
        create_schema=args.create_schema,
    )
    print(format_result(result))


if __name__ == "__main__":
    main()
