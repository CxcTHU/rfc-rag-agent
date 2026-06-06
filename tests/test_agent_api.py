from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.agent import get_agent_chat_model_provider, get_agent_embedding_provider
from app.db.models import Base
from app.db.repositories import (
    ChunkCreate,
    DocumentCreate,
    DocumentRepository,
    SourceCreate,
    SourceRepository,
)
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider


@contextmanager
def make_test_client(tmp_path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "agent_api.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    embedding_provider = DeterministicEmbeddingProvider(dimension=32)

    with TestingSessionLocal() as db:
        seed_agent_api_document(db)
        SourceRepository(db).create_source(source_record())

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_chat_model_provider() -> DeterministicChatModelProvider:
        return DeterministicChatModelProvider()

    def override_embedding_provider() -> DeterministicEmbeddingProvider:
        return embedding_provider

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_agent_chat_model_provider] = override_chat_model_provider
    app.dependency_overrides[get_agent_embedding_provider] = override_embedding_provider
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def seed_agent_api_document(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Agent API filling source",
            source_type="local_file",
            source_path="agent-filling.md",
            file_name="agent-filling.md",
            file_extension=".md",
            content_hash="agent-api-filling-hash",
            raw_path="data/raw/agent-filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Filling capacity depends on self-compacting concrete flowability in rock-filled concrete.",
                char_count=86,
                heading_path="Filling",
                start_char=0,
                end_char=86,
            )
        ],
    )


def source_record() -> SourceCreate:
    return SourceCreate(
        source_id="rfc_source_001",
        title="Agent API filling source",
        normalized_title="agent api filling source",
        authors="Example Author",
        year="2014",
        venue="Example Journal",
        category="filling_capacity",
        discovered_via="test",
        doi=None,
        normalized_doi=None,
        url="https://example.org/agent-filling",
        normalized_url="https://example.org/agent-filling",
        pdf_url=None,
        abstract="A source about filling capacity.",
        keywords="rock-filled concrete; filling capacity",
        language="en",
        citation_count=10,
        source_type="metadata_record",
        trust_level="high",
        access_rights="metadata",
        fulltext_permission="metadata_only",
        license_or_terms=None,
        local_path=None,
        status="collected",
        notes="test source",
        document_id=None,
    )


def test_agent_api_answers_with_tool_calls_and_citations(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={"question": "What affects filling capacity?", "top_k": 2},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "What affects filling capacity?"
    assert payload["refused"] is False
    assert payload["tool_calls"][0]["tool_name"] == "answer_with_citations"
    assert payload["citations"] == [1]
    assert payload["sources"]
    assert "引用式问答" in payload["reasoning_summary"]


def test_agent_api_search_query_returns_hybrid_results(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={"question": "检索 filling capacity 相关资料", "top_k": 2},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_calls"][0]["tool_name"] == "hybrid_search_knowledge"
    assert payload["search_results"]
    assert payload["sources"][0]["chunk_id"] is not None


def test_agent_api_source_detail_query_returns_source_record(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={"question": "查看来源详情", "source_id": "rfc_source_001"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_calls"][0]["tool_name"] == "get_source_detail"
    assert payload["sources"][0]["source_id"] == "rfc_source_001"
    assert payload["sources"][0]["fulltext_permission"] == "metadata_only"


def test_agent_api_rejects_blank_question_with_422(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post("/agent/query", json={"question": "   "})

    assert response.status_code == 422


def test_agent_api_keeps_existing_search_and_chat_routes_available(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        search_response = client.post("/search", json={"query": "filling capacity", "top_k": 2})
        chat_response = client.post("/chat", json={"question": "filling capacity", "retrieval_mode": "keyword"})
        sources_response = client.get("/sources")

    assert search_response.status_code == 200
    assert chat_response.status_code == 200
    assert sources_response.status_code == 200
