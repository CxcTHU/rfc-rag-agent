from collections.abc import Generator
from contextlib import contextmanager
import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.services.retrieval.faiss_index import FaissIndexMetadata, write_metadata


@contextmanager
def make_test_client(tmp_path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "health_details.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Health details fixture",
                source_type="local_file",
                source_path="fixture.md",
                file_name="fixture.md",
                file_extension=".md",
                content_hash="health-details-fixture",
                raw_path="data/raw/fixture.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="Thermal control reduces hydration heat.",
                    char_count=39,
                    heading_path="Thermal",
                    start_char=0,
                    end_char=39,
                ),
                ChunkCreate(
                    chunk_index=1,
                    content="Filling capacity depends on flowability.",
                    char_count=39,
                    heading_path="Filling",
                    start_char=40,
                    end_char=79,
                ),
            ],
        )

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def write_complete_faiss_metadata(tmp_path) -> None:
    index_dir = tmp_path / "data" / "faiss"
    index_dir.mkdir(parents=True)
    index_path = index_dir / "deterministic_hash-token-v1_dim32.index"
    metadata_path = index_dir / "deterministic_hash-token-v1_dim32_ids.json"
    index_path.write_bytes(b"local-test-index-placeholder")
    write_metadata(
        metadata_path,
        FaissIndexMetadata(
            provider="deterministic",
            model_name="hash-token-v1",
            dimension=32,
            metric="inner_product",
            normalized=True,
            complete=True,
            chunk_ids=(1, 2),
        ),
    )


def test_health_details_reports_local_diagnostics_without_secrets(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_complete_faiss_metadata(tmp_path)

    with make_test_client(tmp_path) as client:
        response = client.get("/health/details")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["database"] == {
        "status": "ok",
        "connected": True,
        "document_count": 1,
        "chunk_count": 2,
        "error": None,
    }
    assert payload["faiss"]["status"] == "ok"
    assert payload["faiss"]["index_count"] == 1
    assert payload["faiss"]["indexes"][0]["vector_count"] == 2
    assert payload["faiss"]["indexes"][0]["complete"] is True
    assert payload["providers"]["deterministic_available"] is True

    serialized = json.dumps(payload, ensure_ascii=False).casefold()
    assert "api_key" not in serialized
    assert "bearer" not in serialized
    assert "authorization" not in serialized


def test_health_details_reports_missing_faiss_without_external_ping(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    with make_test_client(tmp_path) as client:
        response = client.get("/health/details")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"]["connected"] is True
    assert payload["faiss"] == {
        "status": "missing",
        "index_dir": payload["faiss"]["index_dir"],
        "index_count": 0,
        "indexes": [],
    }
    assert payload["faiss"]["index_dir"].replace("\\", "/") == "data/faiss"


def test_basic_health_endpoint_remains_unchanged(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    with make_test_client(tmp_path) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert set(response.json()) == {"status", "service", "environment"}


def test_retrieval_contract_health_is_safe_and_content_free(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RERANKING_ENABLED", "true")
    monkeypatch.setenv("RERANKING_PROVIDER", "zhipu")
    monkeypatch.setenv("RERANKING_MODEL_NAME", "rerank")
    monkeypatch.setenv("SEMANTIC_EVIDENCE_CACHE_ENABLED", "false")
    get_settings.cache_clear()

    with make_test_client(tmp_path) as client:
        response = client.get("/health/retrieval-contract")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_count"] == 1
    assert payload["chunk_count"] == 2
    assert len(payload["corpus_fingerprint"]) == 64
    assert payload["agent_short_loop_enabled"] is False
    assert payload["phase64_route_first_enabled"] is False
    assert payload["phase64_retrieval_fanout_enabled"] is False
    assert payload["phase64_final_non_thinking_enabled"] is False
    assert payload["phase64_execution_graph_schema"]
    assert payload["retrieval_runtime_schema"]
    assert payload["reranking_enabled"] is True
    assert payload["reranking_provider"] == "zhipu"
    assert payload["reranking_model_name"] == "rerank"
    assert payload["semantic_evidence_cache_enabled"] is False
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "Thermal control reduces hydration heat" not in serialized
    assert "Filling capacity depends on flowability" not in serialized
