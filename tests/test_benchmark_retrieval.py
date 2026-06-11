from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService
from scripts.benchmark_retrieval import benchmark_query, escape_table_cell, time_operation


def make_session(tmp_path):
    database_path = tmp_path / "benchmark_retrieval.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_benchmark_documents(db) -> None:
    repository = DocumentRepository(db)
    repository.create_with_chunks(
        DocumentCreate(
            title="Filling capacity guide",
            source_type="local_file",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="benchmark-filling-hash",
            raw_path="data/raw/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Filling capacity depends on self compacting concrete flowability.",
                char_count=65,
                heading_path="Filling",
                start_char=0,
                end_char=65,
            ),
        ],
    )


def test_benchmark_query_returns_layer_timings(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        seed_benchmark_documents(db)
        VectorIndexService(db, provider).build_index()

        result = benchmark_query(
            db=db,
            provider=provider,
            query="filling capacity",
            top_k=1,
            runs=1,
        )

    assert result.chunk_count == 1
    assert result.embedding_count == 1
    assert result.provider == "deterministic"
    assert result.model_name == "hash-token-v1"
    assert {timing.name for timing in result.timings} == {
        "query_embedding",
        "keyword_search",
        "vector_search",
        "hybrid_search",
        "rerank_only",
        "agent_query",
    }
    assert all(timing.runs == 1 for timing in result.timings)
    assert all(timing.min_ms >= 0 for timing in result.timings)


def test_time_operation_rejects_invalid_runs() -> None:
    try:
        time_operation("noop", 0, lambda: None)
    except ValueError as exc:
        assert "runs" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid runs")


def test_escape_table_cell_escapes_markdown_separators() -> None:
    assert escape_table_cell("a|b\nc") == "a\\|b c"
