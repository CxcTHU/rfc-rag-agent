from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, ChunkEmbedding, Document
from app.db.session import create_sqlite_engine
from scripts.collect_stage30_engineering_health import collect_engineering_health


def make_session(tmp_path):
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'stage30-health.sqlite').as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_index(db) -> None:
    document = Document(
        title="Stage 30 health source",
        source_type="web_page",
        source_path="https://example.com",
        file_name="health.md",
        file_extension=".md",
        content_hash="stage30-health-document",
        raw_path="data/raw/health.md",
    )
    chunk = Chunk(
        document=document,
        chunk_index=0,
        content="health content",
        char_count=14,
    )
    db.add(document)
    db.flush()
    db.add_all(
        [
            ChunkEmbedding(
                chunk=chunk,
                provider="jina",
                model_name="jina-embeddings-v3",
                dimension=1024,
                embedding_json="[0.1]",
                content_hash="stage30-health-chunk",
            ),
            ChunkEmbedding(
                chunk=chunk,
                provider="deterministic",
                model_name="hash-token-v1",
                dimension=64,
                embedding_json="[0.2]",
                content_hash="stage30-health-chunk",
            ),
        ]
    )
    db.commit()


def test_collect_stage30_engineering_health_is_read_only_summary(tmp_path) -> None:
    SessionLocal = make_session(tmp_path)
    with SessionLocal() as db:
        seed_index(db)
        health = collect_engineering_health(
            db,
            full_tests_status="1 passed",
            quality_report_smoke="passed",
        )

    assert health["chunk_count"] == 1
    assert health["embedding_count"] == 2
    assert health["jina_embedding_count"] == 1
    assert health["deterministic_embedding_count"] == 1
    assert health["orphan_embeddings"] == 0
    assert health["duplicate_provider_model_groups"] == 0
    assert health["collector_limits"] == {
        "runs_pytest": False,
        "rebuilds_embeddings": False,
        "writes_database": False,
        "calls_real_api": False,
    }
