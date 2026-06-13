from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.agent.react_service import ReActAgentService, ReActRuntimeEvent
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService


def make_session(tmp_path):
    database_path = tmp_path / "react_agent.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_react_documents(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Rock-filled concrete filling guide",
            source_type="local_file",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="react-agent-filling-hash",
            raw_path="data/raw/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Filling capacity depends on self-compacting concrete "
                    "flowability in rock-filled concrete voids."
                ),
                char_count=98,
                heading_path="Filling",
                start_char=0,
                end_char=98,
            )
        ],
    )


def make_service(db: Session) -> ReActAgentService:
    provider = DeterministicEmbeddingProvider(dimension=32)
    VectorIndexService(db, provider).build_index()
    return ReActAgentService(
        db=db,
        embedding_provider=provider,
        chat_model_provider=DeterministicChatModelProvider(),
        log_answers=False,
    )


class FailingEmbeddingProvider:
    provider_name = "failing-embedding"
    model_name = "failing-embedding-v1"
    dimension = 32

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("Embedding provider unavailable")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Embedding provider unavailable")


def test_react_agent_service_searches_then_answers_with_citations(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_react_documents(db)
        result = make_service(db).query(
            "What affects filling capacity in rock-filled concrete?",
            top_k=2,
            max_tool_calls=3,
        )

    assert not result.refused
    assert result.citations == [1]
    assert result.sources
    assert [call.tool_name for call in result.tool_calls] == [
        "hybrid_search_knowledge",
        "answer_with_citations",
    ]
    assert "react_agent" in result.reasoning_summary


def test_react_agent_service_emits_safe_runtime_events(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    events: list[ReActRuntimeEvent] = []

    with TestingSessionLocal() as db:
        seed_react_documents(db)
        result = make_service(db).query(
            "What affects filling capacity?",
            top_k=2,
            max_tool_calls=3,
            event_sink=events.append,
        )

    assert not result.refused
    event_names = [event.event for event in events]
    assert "agent_step" in event_names
    assert "tool_call_start" in event_names
    assert "tool_call_result" in event_names
    serialized_payloads = " ".join(str(event.payload) for event in events)
    assert "raw_response" not in serialized_payloads
    assert "Bearer" not in serialized_payloads


def test_react_agent_service_converges_when_search_provider_fails(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    events: list[ReActRuntimeEvent] = []

    with TestingSessionLocal() as db:
        seed_react_documents(db)
        result = ReActAgentService(
            db=db,
            embedding_provider=FailingEmbeddingProvider(),
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        ).query(
            "What affects filling capacity?",
            top_k=2,
            max_tool_calls=3,
            event_sink=events.append,
        )

    assert result.refused
    assert result.refusal_reason == "Tool execution failed before reliable evidence was available."
    assert result.tool_calls[0].tool_name == "hybrid_search_knowledge"
    assert result.tool_calls[0].error == "Embedding provider unavailable"
    event_names = [event.event for event in events]
    assert "tool_call_result" in event_names


def test_react_agent_service_refuses_when_iteration_limit_is_reached(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = make_service(db).query(
            "completely unsupported topic",
            top_k=2,
            max_tool_calls=1,
        )

    assert result.refused
    assert result.refusal_reason == "ReAct iteration limit reached."


def test_react_agent_service_rejects_invalid_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        service = make_service(db)

        try:
            service.query("   ")
        except ValueError as exc:
            assert "question" in str(exc)
        else:
            raise AssertionError("blank question should fail")

        try:
            service.query("question", max_tool_calls=0)
        except ValueError as exc:
            assert "max_tool_calls" in str(exc)
        else:
            raise AssertionError("invalid max_tool_calls should fail")
