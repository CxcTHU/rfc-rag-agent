from dataclasses import dataclass

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.generation.answer_service import (
    DEFAULT_REFUSAL_ANSWER,
    CitationAnswerService,
    extract_citations,
)
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelResult,
    DeterministicChatModelProvider,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService


def make_session(tmp_path):
    database_path = tmp_path / "answer_service.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_answer_documents(db) -> None:
    repository = DocumentRepository(db)
    repository.create_with_chunks(
        DocumentCreate(
            title="Thermal control guide",
            source_type="local_file",
            source_path="thermal.md",
            file_name="thermal.md",
            file_extension=".md",
            content_hash="answer-service-thermal-hash",
            raw_path="data/raw/thermal.md",
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
                content="Filling capacity depends on self-compacting concrete flowability.",
                char_count=65,
                heading_path="Filling",
                start_char=69,
                end_char=134,
            ),
        ],
    )


@dataclass(frozen=True)
class FixedChatModelProvider:
    answer: str
    provider_name: str = "fixed"
    model_name: str = "fixed-chat-v1"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer=self.answer,
            provider=self.provider_name,
            model_name=self.model_name,
        )


def test_answer_service_generates_answer_with_vector_sources(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        embedding_provider = DeterministicEmbeddingProvider(dimension=32)
        seed_answer_documents(db)
        VectorIndexService(db, embedding_provider).build_index()

        result = CitationAnswerService(
            db=db,
            chat_model_provider=DeterministicChatModelProvider(),
            embedding_provider=embedding_provider,
        ).answer("thermal control", retrieval_mode="vector", top_k=2)

    assert not result.refused
    assert result.retrieval_mode == "vector"
    assert result.model_provider == "deterministic"
    assert result.model_name == "rule-based-chat-v1"
    assert result.citations == [1]
    assert len(result.sources) >= 1
    assert result.sources[0].source_id == 1
    assert result.sources[0].document_title == "Thermal control guide"


def test_answer_service_refuses_when_no_chunks_are_retrieved(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = CitationAnswerService(
            db=db,
            chat_model_provider=DeterministicChatModelProvider(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=16),
        ).answer("不存在的主题", retrieval_mode="keyword")

    assert result.refused
    assert result.answer == DEFAULT_REFUSAL_ANSWER
    assert result.sources == []
    assert result.citations == []
    assert result.retrieval_mode == "keyword"
    assert "No retrieved chunks" in (result.refusal_reason or "")


def test_answer_service_refuses_when_results_are_below_min_score(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        embedding_provider = DeterministicEmbeddingProvider(dimension=32)
        seed_answer_documents(db)
        VectorIndexService(db, embedding_provider).build_index()

        result = CitationAnswerService(
            db=db,
            chat_model_provider=DeterministicChatModelProvider(),
            embedding_provider=embedding_provider,
        ).answer(
            "thermal control",
            retrieval_mode="vector",
            min_score=2.0,
        )

    assert result.refused
    assert result.sources == []
    assert "minimum score" in (result.refusal_reason or "")


def test_answer_service_falls_back_to_keyword_when_vector_index_is_missing(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_answer_documents(db)

        result = CitationAnswerService(
            db=db,
            chat_model_provider=DeterministicChatModelProvider(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        ).answer("thermal control", retrieval_mode="auto")

    assert not result.refused
    assert result.retrieval_mode == "keyword"
    assert result.citations == [1]
    assert result.sources[0].document_title == "Thermal control guide"


def test_answer_service_filters_invalid_citations(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_answer_documents(db)

        result = CitationAnswerService(
            db=db,
            chat_model_provider=FixedChatModelProvider("This answer cites [99]."),
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        ).answer("thermal control", retrieval_mode="keyword")

    assert not result.refused
    assert result.citations == []
    assert len(result.sources) == 1


def test_answer_service_rejects_invalid_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        service = CitationAnswerService(
            db=db,
            chat_model_provider=DeterministicChatModelProvider(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=16),
        )

        with pytest.raises(ValueError, match="question must not be empty"):
            service.answer("   ")
        with pytest.raises(ValueError, match="top_k"):
            service.answer("question", top_k=0)
        with pytest.raises(ValueError, match="min_score"):
            service.answer("question", min_score=-1.0)
        with pytest.raises(ValueError, match="Unsupported retrieval mode"):
            service.answer("question", retrieval_mode="hybrid")  # type: ignore[arg-type]


def test_extract_citations_returns_unique_allowed_source_ids() -> None:
    assert extract_citations("Use [2], [1], [2], and [99].", [1, 2]) == [2, 1]
