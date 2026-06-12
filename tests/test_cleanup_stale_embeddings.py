from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, ChunkEmbedding
from app.db.repositories import (
    ChunkCreate,
    ChunkEmbeddingCreate,
    ChunkEmbeddingRepository,
    DocumentCreate,
    DocumentRepository,
)
from app.db.session import create_sqlite_engine
from scripts.cleanup_stale_embeddings import (
    cleanup_embeddings,
    collect_embedding_cleanup_stats,
    format_stats,
)


def make_session(tmp_path):
    database_path = tmp_path / "cleanup_embeddings.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_embeddings(db) -> None:
    document = DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="阶段 29 清理测试资料",
            source_type="local_file",
            source_path="cleanup.md",
            file_name="cleanup.md",
            file_extension=".md",
            content_hash="cleanup-document-hash",
            raw_path="data/raw/cleanup.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="堆石混凝土真实 embedding 重建测试。",
                char_count=22,
                heading_path="Embedding",
                start_char=0,
                end_char=22,
            ),
            ChunkCreate(
                chunk_index=1,
                content="Deterministic embedding 用于 CI 回归。",
                char_count=34,
                heading_path="Deterministic",
                start_char=23,
                end_char=57,
            ),
        ],
    )
    chunks = DocumentRepository(db).list_chunks(document.id)
    repository = ChunkEmbeddingRepository(db)
    repository.save_embedding(
        ChunkEmbeddingCreate(
            chunk_id=chunks[0].id,
            provider="jina",
            model_name="jina-embeddings-v3",
            dimension=1024,
            embedding=[0.1, 0.2],
            content_hash="chunk-0",
        )
    )
    repository.save_embedding(
        ChunkEmbeddingCreate(
            chunk_id=chunks[1].id,
            provider="deterministic",
            model_name="hash-token-v1",
            dimension=64,
            embedding=[0.3, 0.4],
            content_hash="chunk-1",
        )
    )
    db.add(
        ChunkEmbedding(
            chunk_id=999999,
            provider="jina",
            model_name="jina-embeddings-v3",
            dimension=1024,
            embedding_json="[0.5,0.6]",
            content_hash="missing-chunk",
        )
    )
    db.commit()


def count_embeddings(db) -> int:
    return int(db.scalar(select(func.count(ChunkEmbedding.id))) or 0)


def test_dry_run_reports_counts_without_deleting(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_embeddings(db)
        stats = cleanup_embeddings(db, execute=False)
        remaining = count_embeddings(db)

    assert stats.total_chunks == 2
    assert stats.total_embeddings == 3
    assert stats.orphan_embeddings == 1
    assert stats.selected_embeddings == 3
    assert stats.deleted_embeddings == 0
    assert stats.executed is False
    assert remaining == 3


def test_execute_deletes_all_embeddings_without_deleting_chunks(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_embeddings(db)
        stats = cleanup_embeddings(db, execute=True)
        remaining = count_embeddings(db)
        chunk_count = stats.total_chunks

    assert stats.deleted_embeddings == 3
    assert remaining == 0
    assert chunk_count == 2


def test_provider_filter_deletes_only_selected_provider(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_embeddings(db)
        stats = cleanup_embeddings(db, provider="jina", execute=True)
        remaining = count_embeddings(db)
        deterministic_stats = collect_embedding_cleanup_stats(db, provider="deterministic")

    assert stats.selected_embeddings == 2
    assert stats.deleted_embeddings == 2
    assert remaining == 1
    assert deterministic_stats.selected_embeddings == 1


def test_format_stats_includes_provider_distribution(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_embeddings(db)
        stats = collect_embedding_cleanup_stats(db)

    output = format_stats(stats)

    assert "provider=jina" in output
    assert "provider=deterministic" in output
    assert "orphan_embeddings=1" in output
