from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import (
    ChunkCreate,
    DocumentCreate,
    DocumentRepository,
    QuestionAnswerLogCreate,
    QuestionAnswerLogRepository,
    deserialize_int_list,
)
from app.db.session import create_sqlite_engine
from app.services.generation.answer_service import (
    DEFAULT_REFUSAL_ANSWER,
    CitationAnswerService,
)
from app.services.generation.chat_model import ChatMessage, ChatModelResult
from app.services.retrieval.embedding import DeterministicEmbeddingProvider


def make_session(tmp_path):
    database_path = tmp_path / "chat_logging.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_logging_document(db) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Logging thermal source",
            source_type="local_file",
            source_path="logging-thermal.md",
            file_name="logging-thermal.md",
            file_extension=".md",
            content_hash="logging-thermal-hash",
            raw_path="data/raw/logging-thermal.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Thermal control reduces hydration heat in rock-filled concrete dams.",
                char_count=68,
                heading_path="Thermal",
                start_char=0,
                end_char=68,
            )
        ],
    )


@dataclass(frozen=True)
class RawResponseChatModelProvider:
    answer: str
    provider_name: str = "raw-response-test"
    model_name: str = "raw-response-model"

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer=self.answer,
            provider=self.provider_name,
            model_name=self.model_name,
            raw_response={
                "api_key": "secret-api-key",
                "provider_trace": "do-not-store-this-raw-response",
            },
        )


def test_question_answer_log_repository_saves_and_lists_logs(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        repository = QuestionAnswerLogRepository(db)
        saved_log = repository.save_log(
            QuestionAnswerLogCreate(
                question="What is thermal control?",
                answer="Use source [1].",
                retrieved_chunk_ids=[10, 12],
                citations=[1],
                model_provider="deterministic",
                model_name="rule-based-chat-v1",
                retrieval_mode="keyword",
                refused=False,
            )
        )
        queried_log = repository.get_by_id(saved_log.id)
        logs = repository.list_logs()

    assert queried_log is not None
    assert queried_log.id == saved_log.id
    assert [log.id for log in logs] == [saved_log.id]
    assert deserialize_int_list(queried_log.retrieved_chunk_ids) == [10, 12]
    assert deserialize_int_list(queried_log.citations) == [1]
    assert queried_log.created_at is not None


def test_answer_service_saves_successful_log_without_raw_model_response(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_logging_document(db)
        result = CitationAnswerService(
            db=db,
            chat_model_provider=RawResponseChatModelProvider("Thermal answer [1]."),
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        ).answer("thermal control", retrieval_mode="keyword")

        logs = QuestionAnswerLogRepository(db).list_logs()

    assert not result.refused
    assert len(logs) == 1
    log = logs[0]
    assert log.question == "thermal control"
    assert log.answer == "Thermal answer [1]."
    assert deserialize_int_list(log.retrieved_chunk_ids) == [
        source.chunk_id for source in result.sources
    ]
    assert deserialize_int_list(log.citations) == [1]
    assert log.model_provider == "raw-response-test"
    assert log.model_name == "raw-response-model"
    assert log.retrieval_mode == "keyword"
    stored_text = "\n".join(
        [
            log.question,
            log.answer,
            log.retrieved_chunk_ids,
            log.citations,
            log.model_provider,
            log.model_name,
            log.retrieval_mode,
            log.refusal_reason or "",
        ]
    )
    assert "secret-api-key" not in stored_text
    assert "do-not-store-this-raw-response" not in stored_text


def test_answer_service_saves_refusal_log(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = CitationAnswerService(
            db=db,
            chat_model_provider=RawResponseChatModelProvider("Should not be called."),
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        ).answer("missing context", retrieval_mode="keyword")

        logs = QuestionAnswerLogRepository(db).list_logs()

    assert result.refused
    assert result.answer == DEFAULT_REFUSAL_ANSWER
    assert len(logs) == 1
    log = logs[0]
    assert log.refused is True
    assert log.answer == DEFAULT_REFUSAL_ANSWER
    assert deserialize_int_list(log.retrieved_chunk_ids) == []
    assert deserialize_int_list(log.citations) == []
    assert "No retrieved chunks" in (log.refusal_reason or "")


def test_answer_service_can_disable_logging(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_logging_document(db)
        CitationAnswerService(
            db=db,
            chat_model_provider=RawResponseChatModelProvider("Thermal answer [1]."),
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            log_answers=False,
        ).answer("thermal control", retrieval_mode="keyword")

        assert QuestionAnswerLogRepository(db).count_logs() == 0
