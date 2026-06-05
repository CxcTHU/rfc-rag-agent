from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.search import get_embedding_provider
from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService


@contextmanager
def make_test_client(tmp_path, build_index: bool = True) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "vector_search_api.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    provider = DeterministicEmbeddingProvider(dimension=32)

    with TestingSessionLocal() as db:
        seed_vector_search_document(db)
        if build_index:
            VectorIndexService(db, provider).build_index()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_embedding_provider() -> DeterministicEmbeddingProvider:
        return provider

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_provider] = override_embedding_provider
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def seed_vector_search_document(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Vector search source",
            source_type="local_file",
            source_path="vector-source.md",
            file_name="vector-source.md",
            file_extension=".md",
            content_hash="vector-search-api-hash",
            raw_path="data/raw/vector-source.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Thermal control and hydration heat are important in rock filled concrete.",
                char_count=72,
                heading_path="Thermal",
                start_char=0,
                end_char=72,
            ),
            ChunkCreate(
                chunk_index=1,
                content="Flowability improves filling capacity in self compacting concrete.",
                char_count=64,
                heading_path="Filling",
                start_char=73,
                end_char=137,
            ),
        ],
    )


def test_vector_search_api_returns_indexed_chunks(tmp_path) -> None:
    with make_test_client(tmp_path, build_index=True) as client:
        response = client.post("/search/vector", json={"query": "thermal control", "top_k": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "thermal control"
    assert payload["top_k"] == 2
    assert payload["provider"] == "deterministic"
    assert payload["model_name"] == "hash-token-v1"
    assert len(payload["results"]) >= 1
    assert payload["results"][0]["document_title"] == "Vector search source"
    assert payload["results"][0]["file_name"] == "vector-source.md"
    assert payload["results"][0]["chunk_index"] == 0
    assert payload["results"][0]["score"] > 0


def test_vector_search_api_returns_empty_when_index_is_missing(tmp_path) -> None:
    with make_test_client(tmp_path, build_index=False) as client:
        response = client.post("/search/vector", json={"query": "thermal control", "top_k": 2})

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_hybrid_search_api_combines_keyword_and_vector_results(tmp_path) -> None:
    with make_test_client(tmp_path, build_index=True) as client:
        response = client.post("/search/hybrid", json={"query": "filling capacity", "top_k": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "filling capacity"
    assert payload["top_k"] == 2
    assert payload["provider"] == "deterministic"
    assert payload["model_name"] == "hash-token-v1"
    assert payload["results"]
    assert payload["results"][0]["document_title"] == "Vector search source"
    assert payload["results"][0]["chunk_index"] == 1
