import subprocess
import sys

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, ChunkEmbedding, Document, QuestionAnswerLog, Source
from app.db.session import create_sqlite_engine
from app.services.retrieval.vector_index import calculate_text_hash
from scripts.migrate_sqlite_to_postgres import migrate_sqlite_to_target


def create_temp_session(database_url: str):
    engine = create_sqlite_engine(database_url)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_source_database(database_url: str) -> None:
    SessionLocal = create_temp_session(database_url)
    with SessionLocal() as db:
        document = Document(
            title="阶段45迁移测试文档",
            source_type="open_access_pdf",
            source_path="data/raw/source.pdf",
            file_name="source.pdf",
            file_extension=".pdf",
            content_hash="stage45-doc-hash",
            raw_path="data/raw/stage45-doc-hash.pdf",
        )
        parent = Chunk(
            document=document,
            chunk_index=0,
            content="parent context",
            char_count=14,
            heading_path="parent",
            start_char=0,
            end_char=14,
        )
        child = Chunk(
            document=document,
            chunk_index=1,
            content="child retrieval content",
            char_count=23,
            heading_path="parent",
            start_char=0,
            end_char=23,
            parent_chunk=parent,
        )
        db.add(document)
        db.flush()
        db.add(
            Source(
                source_id="stage45-source",
                title="阶段45来源",
                normalized_title="阶段45来源",
                source_type="paper",
                trust_level="high",
                access_rights="open",
                fulltext_permission="open_access",
                status="imported",
                document_id=document.id,
            )
        )
        db.add(
            ChunkEmbedding(
                chunk_id=child.id,
                provider="deterministic",
                model_name="hash-token-v1",
                dimension=2,
                embedding_json="[0.0,1.0]",
                content_hash=calculate_text_hash(child.content),
            )
        )
        db.add(
            QuestionAnswerLog(
                question="阶段45迁移是否可重复？",
                answer="可以。",
                retrieved_chunk_ids=f"[{child.id}]",
                citations="[1]",
                model_provider="deterministic",
                model_name="test-chat",
                retrieval_mode="hybrid",
                refused=False,
            )
        )
        db.commit()


def test_migrate_sqlite_to_target_is_incremental_and_maps_references(tmp_path) -> None:
    source_url = f"sqlite:///{(tmp_path / 'source.sqlite').as_posix()}"
    target_url = f"sqlite:///{(tmp_path / 'target.sqlite').as_posix()}"
    seed_source_database(source_url)

    first = migrate_sqlite_to_target(source_url, target_url, create_schema=True)
    second = migrate_sqlite_to_target(source_url, target_url, create_schema=True)

    assert first.documents.inserted == 1
    assert first.sources.inserted == 1
    assert first.chunks.inserted == 2
    assert first.chunk_embeddings.inserted == 1
    assert first.qa_logs.inserted == 1
    assert second.documents.skipped == 1
    assert second.sources.skipped == 1
    assert second.chunks.skipped == 2
    assert second.chunk_embeddings.skipped == 1
    assert second.qa_logs.skipped == 1

    TargetSession = create_temp_session(target_url)
    with TargetSession() as db:
        target_document = db.scalar(select(Document).where(Document.content_hash == "stage45-doc-hash"))
        target_chunks = list(db.scalars(select(Chunk).order_by(Chunk.chunk_index)).all())
        target_source = db.scalar(select(Source).where(Source.source_id == "stage45-source"))
        target_embedding = db.scalar(select(ChunkEmbedding))
        qa_logs = list(db.scalars(select(QuestionAnswerLog)).all())

    assert target_document is not None
    assert len(target_chunks) == 2
    assert target_chunks[1].parent_chunk_id == target_chunks[0].id
    assert target_source is not None
    assert target_source.document_id == target_document.id
    assert target_embedding is not None
    assert target_embedding.chunk_id == target_chunks[1].id
    assert len(qa_logs) == 1


def test_build_faiss_index_accepts_explicit_database_url(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'faiss-source.sqlite').as_posix()}"
    seed_source_database(database_url)
    output_dir = tmp_path / "faiss"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_faiss_index.py",
            "--provider",
            "deterministic",
            "--model-name",
            "hash-token-v1",
            "--dimension",
            "2",
            "--database-url",
            database_url,
            "--output-dir",
            output_dir.as_posix(),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "vectors=1" in completed.stdout
    assert (output_dir / "deterministic_hash-token-v1_dim2.index").exists()
    assert (output_dir / "deterministic_hash-token-v1_dim2_ids.json").exists()
