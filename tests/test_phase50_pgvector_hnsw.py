from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.models import Base
from app.db.session import create_sqlite_engine
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.pgvector_search import PgVectorSearchService, format_pgvector_literal
from app.services.retrieval.vector_cache import VectorIndexEntry, VectorIndexMatch
from app.services.retrieval.vector_search import VectorSearchService


class FakeProvider:
    provider_name = "paratera"
    model_name = "GLM-Embedding-3"
    dimension = 2048

    def embed_texts(self, texts):
        return [[1.0] + [0.0] * 2047 for _text in texts]

    def embed_query(self, query):
        return [1.0] + [0.0] * 2047


class FakeQueryEmbeddingCache:
    def get_or_embed(self, provider, query):
        return provider.embed_query(query)


class FakePgVectorSearch:
    def __init__(self, matches):
        self.matches = matches
        self.called = False

    def search(self, query_embedding, top_k):
        self.called = True
        return self.matches


class FakeFallbackIndex:
    load_mode = "faiss_only"

    def __init__(self, matches):
        self.matches = matches
        self.called = False

    def search(self, query_embedding, top_k):
        self.called = True
        return self.matches


def make_match(score: float = 0.9) -> VectorIndexMatch:
    return VectorIndexMatch(
        entry=VectorIndexEntry(
            document_id=1,
            document_title="Vector guide",
            source_type="local_file",
            source_path="vector.md",
            file_name="vector.md",
            chunk_id=10,
            chunk_index=0,
            content="HNSW search keeps vector retrieval in PostgreSQL.",
            heading_path="Vector",
        ),
        score=score,
    )


def test_phase50_compose_uses_pgvector_postgres_image() -> None:
    dev_compose = Path("docker-compose.dev.yml").read_text(encoding="utf-8")
    prod_compose = Path("docker-compose.prod.yml").read_text(encoding="utf-8")

    assert "pgvector/pgvector:pg16" in dev_compose
    assert "pgvector/pgvector:pg16" in prod_compose
    assert "postgres:16-alpine" not in dev_compose
    assert "postgres:16-alpine" not in prod_compose


def test_phase50_pgvector_config_defaults_are_safe() -> None:
    settings = Settings()

    assert settings.pgvector_search_enabled is True
    assert settings.hnsw_ef_search == 100


def test_phase50_pgvector_migration_creates_vector_column_and_hnsw_index() -> None:
    migration = Path("alembic/versions/20260621_0007_pgvector_hnsw.py").read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "embedding_vector" in migration
    assert "Vector(2048)" in migration
    assert "USING hnsw" in migration
    assert "halfvec_cosine_ops" in migration
    assert "m = 16" in migration
    assert "ef_construction = 200" in migration


def test_format_pgvector_literal_validates_dimension_and_non_finite_values() -> None:
    assert format_pgvector_literal([1, 0.25], expected_dimension=2) == "[1,0.25]"

    with pytest.raises(ValueError):
        format_pgvector_literal([1.0], expected_dimension=2)
    with pytest.raises(ValueError):
        format_pgvector_literal([float("nan"), 1.0], expected_dimension=2)


def test_pgvector_search_is_disabled_for_sqlite(tmp_path) -> None:
    database_path = tmp_path / "pgvector.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        service = PgVectorSearchService(
            db,
            FakeProvider(),
            Settings(pgvector_search_enabled=True),
        )

        status = service.status()

    assert status.enabled is False
    assert "unsupported_dialect:sqlite" == status.reason


def test_vector_search_prefers_pgvector_when_available() -> None:
    match = make_match(score=0.95)
    pgvector = FakePgVectorSearch([match])
    fallback = FakeFallbackIndex([])
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        service = VectorSearchService(
            object(),
            FakeProvider(),
            index_cache=fallback,
            query_embedding_cache=FakeQueryEmbeddingCache(),
            pgvector_search=pgvector,
            settings=Settings(pgvector_search_enabled=True),
        )
        results = service.search("hnsw search", top_k=1)
    finally:
        reset_current_latency_trace(token)

    assert pgvector.called is True
    assert fallback.called is False
    assert results[0].chunk_id == 10
    assert trace.values["vector_search_backend"] == "pgvector_hnsw"


def test_vector_search_falls_back_to_faiss_when_pgvector_skips() -> None:
    match = make_match(score=0.88)
    pgvector = FakePgVectorSearch(None)
    fallback = FakeFallbackIndex([match])
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        service = VectorSearchService(
            object(),
            FakeProvider(),
            index_cache=fallback,
            query_embedding_cache=FakeQueryEmbeddingCache(),
            pgvector_search=pgvector,
            settings=Settings(pgvector_search_enabled=True),
        )
        results = service.search("hnsw search", top_k=1)
    finally:
        reset_current_latency_trace(token)

    assert pgvector.called is True
    assert fallback.called is True
    assert results[0].chunk_id == 10
    assert trace.values["vector_search_backend"] == "faiss"
