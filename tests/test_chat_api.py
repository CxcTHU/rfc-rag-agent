from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.chat import get_chat_model_provider, get_embedding_provider
from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService


@contextmanager
def make_test_client(
    tmp_path,
    seed_documents: bool = True,
    build_index: bool = False,
) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "chat_api.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    embedding_provider = DeterministicEmbeddingProvider(dimension=32)

    if seed_documents:
        with TestingSessionLocal() as db:
            seed_chat_document(db)
            if build_index:
                VectorIndexService(db, embedding_provider).build_index()

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
    app.dependency_overrides[get_chat_model_provider] = override_chat_model_provider
    app.dependency_overrides[get_embedding_provider] = override_embedding_provider
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def seed_chat_document(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Chat API thermal source",
            source_type="local_file",
            source_path="chat-thermal.md",
            file_name="chat-thermal.md",
            file_extension=".md",
            content_hash="chat-api-thermal-hash",
            raw_path="data/raw/chat-thermal.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Thermal control reduces hydration heat in rock-filled concrete dams.",
                char_count=68,
                heading_path="Thermal",
                start_char=0,
                end_char=68,
            ),
            ChunkCreate(
                chunk_index=1,
                content="Flowability improves filling capacity in self-compacting concrete.",
                char_count=66,
                heading_path="Filling",
                start_char=69,
                end_char=135,
            ),
        ],
    )


def test_chat_api_returns_answer_sources_and_model_metadata(tmp_path) -> None:
    with make_test_client(tmp_path, seed_documents=True, build_index=True) as client:
        response = client.post(
            "/chat",
            json={
                "question": "thermal control",
                "top_k": 2,
                "retrieval_mode": "vector",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "thermal control"
    assert payload["refused"] is False
    assert payload["refusal_reason"] is None
    assert payload["retrieval_mode"] == "vector"
    assert payload["model_provider"] == "deterministic"
    assert payload["model_name"] == "rule-based-chat-v1"
    assert payload["citations"] == [1]
    assert len(payload["sources"]) >= 1
    source = payload["sources"][0]
    assert source["source_id"] == 1
    assert source["document_title"] == "Chat API thermal source"
    assert source["source_type"] == "local_file"
    assert source["source_path"] == "chat-thermal.md"
    assert source["file_name"] == "chat-thermal.md"
    assert source["chunk_id"] > 0
    assert source["chunk_index"] == 0
    assert source["heading_path"] == "Thermal"
    assert "Thermal control" in source["content"]
    assert source["score"] > 0


def test_chat_api_falls_back_to_keyword_in_auto_mode(tmp_path) -> None:
    with make_test_client(tmp_path, seed_documents=True, build_index=False) as client:
        response = client.post(
            "/chat",
            json={"question": "thermal control", "retrieval_mode": "auto"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is False
    assert payload["retrieval_mode"] == "keyword"
    assert payload["citations"] == [1]
    assert payload["sources"][0]["document_title"] == "Chat API thermal source"


def test_chat_api_refuses_when_context_is_missing(tmp_path) -> None:
    with make_test_client(tmp_path, seed_documents=False) as client:
        response = client.post(
            "/chat",
            json={"question": "没有资料的问题", "retrieval_mode": "keyword"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is True
    assert payload["answer"] == "当前资料库中没有找到足够可靠的依据。"
    assert payload["sources"] == []
    assert payload["citations"] == []
    assert payload["retrieval_mode"] == "keyword"
    assert "No retrieved chunks" in payload["refusal_reason"]


def test_chat_api_rejects_blank_question_with_422(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post("/chat", json={"question": "   "})

    assert response.status_code == 422


def test_chat_api_rejects_invalid_retrieval_mode_with_422(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/chat",
            json={"question": "thermal control", "retrieval_mode": "hybrid"},
        )

    assert response.status_code == 422
