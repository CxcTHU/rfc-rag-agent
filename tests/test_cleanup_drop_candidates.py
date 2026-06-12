from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, ChunkEmbedding, Document, Source
from app.db.session import create_sqlite_engine
from scripts.cleanup_drop_candidates import (
    build_cleanup_plan,
    cleanup_drop_candidates,
    read_candidate_document_ids,
)


def make_session(tmp_path):
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'cleanup.sqlite').as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_read_candidate_document_ids_deduplicates(tmp_path) -> None:
    csv_path = tmp_path / "drop.csv"
    csv_path.write_text("document_id,title\n1,a\n2,b\n1,a-again\n", encoding="utf-8")

    assert read_candidate_document_ids(csv_path) == [1, 2]


def test_cleanup_drop_candidates_dry_run_keeps_database_and_file(tmp_path) -> None:
    SessionLocal = make_session(tmp_path)
    raw_root = tmp_path / "data" / "raw" / "web_crawl"
    raw_root.mkdir(parents=True)
    raw_path = raw_root / "web_a.md"
    raw_path.write_text("low quality page", encoding="utf-8")

    with SessionLocal() as db:
        document = Document(
            title="NAV",
            source_type="web_page",
            source_path="https://example.test/",
            file_name="web_a.md",
            file_extension=".md",
            content_hash="cleanup-hash",
            raw_path=str(raw_path),
            status="imported",
            chunks=[
                Chunk(
                    chunk_index=0,
                    content="low quality page",
                    char_count=16,
                    heading_path=None,
                    start_char=0,
                    end_char=16,
                    embeddings=[
                        ChunkEmbedding(
                            provider="deterministic",
                            model_name="hash-token-v1",
                            dimension=2,
                            embedding_json="[0.0,1.0]",
                            content_hash="chunk-hash",
                        )
                    ],
                )
            ],
        )
        db.add(document)
        db.flush()
        source = Source(
            source_id="crawl_a",
            title="NAV",
            normalized_title="nav",
            source_type="web_page",
            trust_level="medium",
            access_rights="open_web",
            fulltext_permission="open_access",
            status="imported",
            document_id=document.id,
        )
        db.add(source)
        db.commit()
        document_id = document.id

        result = cleanup_drop_candidates(
            db=db,
            candidate_ids=[document_id],
            raw_root=raw_root,
            dry_run=True,
        )

        assert result.plan.chunks_to_delete == 1
        assert result.plan.embeddings_to_delete == 1
        assert result.plan.sources_to_unlink == 1
        assert result.after.documents == result.before.documents
        assert raw_path.exists()
        assert db.get(Document, document_id) is not None


def test_cleanup_drop_candidates_deletes_web_page_and_unlinks_source(tmp_path) -> None:
    SessionLocal = make_session(tmp_path)
    raw_root = tmp_path / "data" / "raw" / "web_crawl"
    raw_root.mkdir(parents=True)
    raw_path = raw_root / "web_b.md"
    raw_path.write_text("drop me", encoding="utf-8")

    with SessionLocal() as db:
        document = Document(
            title="Directory",
            source_type="web_page",
            source_path="https://example.test/directory",
            file_name="web_b.md",
            file_extension=".md",
            content_hash="cleanup-hash-b",
            raw_path=str(raw_path),
            status="imported",
            chunks=[
                Chunk(
                    chunk_index=0,
                    content="drop me",
                    char_count=7,
                    heading_path=None,
                    start_char=0,
                    end_char=7,
                    embeddings=[
                        ChunkEmbedding(
                            provider="deterministic",
                            model_name="hash-token-v1",
                            dimension=2,
                            embedding_json="[1.0,0.0]",
                            content_hash="chunk-hash-b",
                        )
                    ],
                )
            ],
        )
        db.add(document)
        db.flush()
        source = Source(
            source_id="crawl_b",
            title="Directory",
            normalized_title="directory",
            source_type="web_page",
            trust_level="medium",
            access_rights="open_web",
            fulltext_permission="open_access",
            status="imported",
            document_id=document.id,
        )
        db.add(source)
        db.commit()
        document_id = document.id
        source_id = source.id

        plan = build_cleanup_plan(db, [document_id], raw_root)
        assert plan.existing_document_ids == [document_id]

        result = cleanup_drop_candidates(
            db=db,
            candidate_ids=[document_id],
            raw_root=raw_root,
            dry_run=False,
        )

        assert result.deleted_documents == 1
        assert result.deleted_raw_files == 1
        assert not raw_path.exists()
        assert db.get(Document, document_id) is None
        assert db.scalar(select(Chunk).where(Chunk.document_id == document_id)) is None
        assert db.scalar(select(ChunkEmbedding)) is None
        assert db.get(Source, source_id).document_id is None
