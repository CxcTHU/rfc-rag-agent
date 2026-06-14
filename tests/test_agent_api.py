from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.agent import (
    get_agent_chat_model_provider,
    get_agent_embedding_provider,
    get_agent_planner_chat_model_provider,
)
import app.api.agent as agent_api_module
from app.api.chat import get_chat_model_provider
from app.api.chat import get_embedding_provider as get_chat_embedding_provider
from app.db.models import Base
from app.db.repositories import (
    ChunkCreate,
    ConversationRepository,
    DocumentCreate,
    DocumentRepository,
    MessageCreate,
    SourceCreate,
    SourceRepository,
)
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelResult,
    DeterministicChatModelProvider,
)
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
    app.dependency_overrides[get_agent_planner_chat_model_provider] = lambda: None
    app.dependency_overrides[get_chat_model_provider] = override_chat_model_provider
    app.dependency_overrides[get_chat_embedding_provider] = override_embedding_provider
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


class FailingChatModelProvider:
    provider_name = "failing"
    model_name = "failing-model"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        raise RuntimeError("provider timeout with sensitive raw body")


class AnswerThenFailSummaryProvider:
    provider_name = "partial"
    model_name = "partial-model"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        self.calls += 1
        if self.calls == 1:
            return ChatModelResult(
                answer="Filling capacity depends on SCC flowability [1].",
                provider=self.provider_name,
                model_name=self.model_name,
            )
        raise RuntimeError("summary timeout with sensitive raw body")


class FollowupTransformProvider(DeterministicChatModelProvider):
    provider_name = "transform-test"
    model_name = "transform-test-v1"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        latest = messages[-1].content
        if "Previous assistant answer:" in latest:
            return ChatModelResult(
                answer="中文改写：填充能力取决于 SCC 流动性 [1].",
                provider=self.provider_name,
                model_name=self.model_name,
            )
        return super().generate(messages)


def seed_agent_conversation_messages(conversation_id: int, count: int) -> None:
    override_get_db = app.dependency_overrides[get_db]
    db_generator = override_get_db()
    db = next(db_generator)
    try:
        repository = ConversationRepository(db)
        for index in range(count):
            repository.add_message(
                MessageCreate(
                    conversation_id=conversation_id,
                    role="user" if index % 2 == 0 else "assistant",
                    content=f"历史消息 {index}",
                    mode="default" if index % 2 else None,
                )
            )
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


def seed_refused_assistant_message(conversation_id: int) -> None:
    override_get_db = app.dependency_overrides[get_db]
    db_generator = override_get_db()
    db = next(db_generator)
    try:
        ConversationRepository(db).add_message(
            MessageCreate(
                conversation_id=conversation_id,
                role="assistant",
                content="Refused.",
                mode="agentic",
                metadata={
                    "refused": True,
                    "refusal_category": "off_topic",
                    "refusal_reason": "Question appears off-topic.",
                },
            )
        )
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


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
    assert payload["mode"] == "default"
    assert payload["workflow_steps"] == []
    assert payload["iteration_count"] == 0
    assert payload["invalid_citations"] == []
    assert payload["refusal_category"] is None
    assert "引用式问答" in payload["reasoning_summary"]


def test_agent_api_answers_model_meta_without_retrieval(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post("/agent/query", json={"question": "你用的什么大模型？"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is False
    assert payload["tool_calls"] == []
    assert payload["sources"] == []
    assert payload["mode"] == "meta"
    assert "deterministic / rule-based-chat-v1" in payload["answer"]
    assert "deterministic / hash-token-v1" in payload["answer"]
    assert "agent_meta" in payload["reasoning_summary"]


def test_agent_api_explains_previous_refusal_reason(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        conversation = client.post("/conversations", json={"title": "refusal"}).json()
        seed_refused_assistant_message(conversation["id"])
        response = client.post(
            "/agent/query",
            json={"question": "为什么拒答？", "conversation_id": conversation["id"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is False
    assert payload["tool_calls"] == []
    assert payload["mode"] == "meta"
    assert "Category: off_topic" in payload["answer"]
    assert "Question appears off-topic." in payload["answer"]
    assert "refusal_explanation" in payload["reasoning_summary"]


def test_agent_api_transforms_previous_answer_without_retrieval(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        conversation = client.post("/conversations", json={"title": "followup"}).json()
        first = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity?",
                "top_k": 2,
                "conversation_id": conversation["id"],
            },
        )
        app.dependency_overrides[get_agent_chat_model_provider] = (
            lambda: FollowupTransformProvider()
        )
        second = client.post(
            "/agent/query",
            json={"question": "用中文回答我", "conversation_id": conversation["id"]},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    payload = second.json()
    assert payload["refused"] is False
    assert payload["answer"] == "中文改写：填充能力取决于 SCC 流动性 [1]."
    assert payload["citations"] == [1]
    assert payload["sources"]
    assert payload["tool_calls"][0]["tool_name"] == "answer_with_citations"
    assert "followup_transform" in payload["reasoning_summary"]


def test_agent_api_handles_chitchat_without_refusal_or_tools(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        responses = [
            client.post("/agent/query", json={"question": question, "top_k": 2})
            for question in ["你好", "谢谢", "再见", "好的"]
        ]

    for response in responses:
        assert response.status_code == 200
        payload = response.json()
        assert payload["refused"] is False
        assert payload["tool_calls"] == []
        assert payload["sources"] == []
        assert payload["citations"] == []
        assert payload["mode"] == "default"
        assert "闲聊短路" in payload["reasoning_summary"]


def test_agent_api_short_circuits_chitchat_before_complexity_routing(tmp_path, monkeypatch) -> None:
    def fail_routing(question: str):
        raise AssertionError("routing should not be called for chitchat")

    monkeypatch.setattr(agent_api_module, "classify_query_complexity", fail_routing)

    with make_test_client(tmp_path) as client:
        response = client.post("/agent/query", json={"question": "hello"})

    assert response.status_code == 200
    assert response.json()["tool_calls"] == []


def test_agent_api_persists_chitchat_without_summary(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        conversation = client.post("/conversations", json={"title": "闲聊"}).json()
        seed_agent_conversation_messages(conversation["id"], count=16)
        response = client.post(
            "/agent/query",
            json={
                "question": "谢谢",
                "conversation_id": conversation["id"],
            },
        )
        messages_response = client.get(f"/conversations/{conversation['id']}/messages")

    assert response.status_code == 200
    messages = messages_response.json()["messages"]
    assert messages[-2]["role"] == "user"
    assert messages[-2]["content"] == "谢谢"
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["metadata"]["mode"] == "default"
    assert [message["role"] for message in messages].count("summary") == 0


def test_agent_api_accepts_optional_history_for_contextual_answer(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": "它有哪些研究？",
                "top_k": 2,
                "history": ["filling capacity in rock-filled concrete"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "它有哪些研究？"
    assert payload["refused"] is False
    assert payload["tool_calls"][0]["tool_name"] == "answer_with_citations"
    assert payload["sources"][0]["title"] == "Agent API filling source"


def test_agent_api_persists_messages_when_conversation_id_is_provided(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        conversation = client.post("/conversations", json={"title": "新对话"}).json()
        response = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity?",
                "top_k": 2,
                "conversation_id": conversation["id"],
            },
        )
        messages_response = client.get(f"/conversations/{conversation['id']}/messages")

    assert response.status_code == 200
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "What affects filling capacity?"
    assert messages[1]["mode"] == "default"
    assert messages[1]["content"] == response.json()["answer"]
    assert messages[1]["metadata"]["citations"] == [1]
    assert messages[1]["metadata"]["mode"] == "default"
    assert messages_response.json()["conversation"]["title"] == "What affects filling capacity?"


def test_agent_api_summarizes_long_conversation_after_query(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        conversation = client.post("/conversations", json={"title": "长对话"}).json()
        seed_agent_conversation_messages(conversation["id"], count=16)
        response = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity?",
                "top_k": 2,
                "conversation_id": conversation["id"],
            },
        )
        messages_response = client.get(f"/conversations/{conversation['id']}/messages")

    assert response.status_code == 200
    messages = messages_response.json()["messages"]
    roles = [message["role"] for message in messages]
    assert roles.count("summary") == 1
    summary = next(message for message in messages if message["role"] == "summary")
    assert summary["metadata"]["kept_recent_non_summary_messages"] == 6
    assert len(summary["metadata"]["summary_of_message_ids"]) == 12


def test_agent_api_returns_404_for_missing_conversation_id(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity?",
                "conversation_id": 999,
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "conversation not found"


def test_agent_api_returns_503_when_chat_provider_times_out(tmp_path) -> None:
    failing_provider = FailingChatModelProvider()
    with make_test_client(tmp_path) as client:
        app.dependency_overrides[get_agent_chat_model_provider] = lambda: failing_provider
        response = client.post(
            "/agent/query",
            json={"question": "What affects filling capacity?", "top_k": 2},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "chat model provider is unavailable or timed out"
    assert "sensitive" not in response.text


def test_agent_api_keeps_answer_when_summary_provider_times_out(tmp_path) -> None:
    partial_provider = AnswerThenFailSummaryProvider()
    with make_test_client(tmp_path) as client:
        app.dependency_overrides[get_agent_chat_model_provider] = lambda: partial_provider
        conversation = client.post("/conversations", json={"title": "长对话"}).json()
        seed_agent_conversation_messages(conversation["id"], count=16)
        response = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity?",
                "top_k": 2,
                "conversation_id": conversation["id"],
            },
        )
        messages_response = client.get(f"/conversations/{conversation['id']}/messages")

    assert response.status_code == 200
    assert response.json()["answer"] == "Filling capacity depends on SCC flowability [1]."
    messages = messages_response.json()["messages"]
    assert [message["role"] for message in messages].count("summary") == 0
    assert messages[-2]["role"] == "user"
    assert messages[-1]["role"] == "assistant"


def test_agent_api_agentic_mode_exposes_observability_fields(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 2,
                "mode": "agentic",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "agentic"
    assert isinstance(payload["workflow_steps"], list)
    assert payload["workflow_steps"]
    step_names = [step["name"] for step in payload["workflow_steps"]]
    assert step_names[0] == "retrieve"
    assert "grade" in step_names
    assert "generate" in step_names
    assert step_names[-1] == "citation_check"
    assert payload["tool_calls"][0]["tool_name"] == payload["workflow_steps"][0]["name"]
    assert isinstance(payload["iteration_count"], int)
    assert payload["invalid_citations"] == []
    assert payload["refusal_category"] is None


def test_agent_api_auto_routes_complex_query_to_agentic(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": (
                    "Search and compare filling capacity and thermal control "
                    "mechanisms in rock-filled concrete."
                ),
                "top_k": 2,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "agentic"
    assert payload["workflow_steps"]
    assert payload["tool_calls"][0]["tool_name"] == payload["workflow_steps"][0]["name"]


def test_agent_api_explicit_default_overrides_auto_complex_route(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": (
                    "Search and compare filling capacity and thermal control "
                    "mechanisms in rock-filled concrete."
                ),
                "top_k": 2,
                "mode": "default",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "default"
    assert payload["workflow_steps"] == []
    assert payload["tool_calls"][0]["tool_name"] == "hybrid_search_knowledge"


def test_agent_api_explicit_agentic_overrides_auto_simple_route(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 2,
                "mode": "agentic",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "agentic"
    assert payload["workflow_steps"]


def test_agent_api_explicit_react_agent_mode_uses_react_service(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 2,
                "max_tool_calls": 3,
                "mode": "react_agent",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "react_agent"
    assert payload["citations"] == [1]
    assert [call["tool_name"] for call in payload["tool_calls"]] == [
        "hybrid_search_knowledge",
        "answer_with_citations",
    ]
    assert payload["workflow_steps"]
    assert payload["iteration_count"] >= 2
    assert "react_agent" in payload["reasoning_summary"]


def test_agent_api_agentic_refusal_category_marks_responsibility_gate(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": "请判定本工程的堆石混凝土配合比设计是否符合规范要求？",
                "mode": "agentic",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "agentic"
    assert payload["refused"] is True
    assert payload["refusal_category"] == "responsibility_gate_triggered"


def test_refusal_category_marks_tool_service_error() -> None:
    assert (
        agent_api_module.refusal_category_from_refusal(
            refused=True,
            refusal_reason="Tool execution failed before reliable evidence was available.",
        )
        == "service_error"
    )
    assert (
        agent_api_module.refusal_category_from_refusal(
            refused=True,
            refusal_reason="Embedding model request failed: [SSL: UNEXPECTED_EOF_WHILE_READING]",
        )
        == "service_error"
    )
    assert (
        agent_api_module.refusal_category_from_refusal(
            refused=True,
            refusal_reason="Retrieved chunks did not provide enough evidence.",
        )
        == "evidence_insufficient"
    )


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
