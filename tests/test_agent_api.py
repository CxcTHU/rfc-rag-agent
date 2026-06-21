from collections.abc import Generator
from contextlib import contextmanager
from types import SimpleNamespace

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
from app.schemas.agent import AgentQueryRequest
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
            ),
            ChunkCreate(
                chunk_index=1,
                content="Figure evidence showing interface microstructure and filling paths in rock-filled concrete.",
                char_count=86,
                heading_path="Figure",
                start_char=None,
                end_char=None,
                chunk_type="image_description",
                source_image_path="data/images/1/page2_img3.png",
                caption="Fig. 1 Interface microstructure",
            ),
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


class OverproducingFollowupTransformProvider(DeterministicChatModelProvider):
    provider_name = "overproduce-transform-test"
    model_name = "overproduce-transform-test-v1"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer=(
                "1. 温控措施：堆石混凝土可减少温控需求 [1]。\n"
                "2. 经济性：材料成本较低 [1]。\n"
                "3. 施工工艺：可先抛填块石再灌注 [2]。\n"
                "4. 流动性要求：需要更高流动性的自密实混凝土 [3]。"
            ),
            provider=self.provider_name,
            model_name=self.model_name,
        )


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


def test_agent_api_defaults_to_tool_calling_with_citations(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={"question": "What affects filling capacity?", "top_k": 2},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "What affects filling capacity?"
    assert payload["refused"] is False
    assert payload["tool_calls"][0]["tool_name"] == "hybrid_search_knowledge"
    assert payload["citations"] == [1]
    assert payload["sources"]
    assert any(source["chunk_type"] == "image_description" for source in payload["sources"])
    assert any(source["image_url"] == "/assets/images/1/page2_img3.png" for source in payload["sources"])
    assert any(source["caption"] == "Fig. 1 Interface microstructure" for source in payload["sources"])
    assert payload["mode"] == "tool_calling_agent"
    assert [step["name"] for step in payload["workflow_steps"]] == [
        "hybrid_search_knowledge",
        "final_answer",
    ]
    assert payload["iteration_count"] == 2
    assert payload["invalid_citations"] == []
    assert payload["refusal_category"] is None
    assert "tool_calling_agent" in payload["reasoning_summary"]


def test_agent_query_request_accepts_langgraph_agent_mode() -> None:
    request = AgentQueryRequest(
        question="What affects filling capacity?",
        mode="LANGGRAPH_AGENT",
    )

    assert request.mode == "langgraph_agent"


def test_agent_api_answers_model_meta_without_retrieval(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post("/agent/query", json={"question": "你用的什么大模型？"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is False
    assert payload["tool_calls"] == []
    assert payload["sources"] == []
    assert payload["mode"] == "meta"
    assert "当前运行模型配置" in payload["answer"]
    assert "对话模型" in payload["answer"]
    assert "向量模型" in payload["answer"]
    assert "deterministic / rule-based-chat-v1" in payload["answer"]
    assert "deterministic / hash-token-v1" in payload["answer"]
    assert "Runtime model configuration" not in payload["answer"]
    assert "agent_meta" in payload["reasoning_summary"]


def test_agent_api_answers_capability_help_in_chinese_by_default(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post("/agent/query", json={"question": "What can you do?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is False
    assert payload["tool_calls"] == []
    assert payload["sources"] == []
    assert payload["mode"] == "meta"
    assert "我可以围绕本项目资料库回答" in payload["answer"]
    assert "拒答分类" in payload["answer"]
    assert "I can answer" not in payload["answer"]
    assert "capability_help" in payload["reasoning_summary"]


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
    assert "上一轮回答被拒答" in payload["answer"]
    assert "拒答分类：off_topic" in payload["answer"]
    assert "原始原因：Question appears off-topic." in payload["answer"]
    assert "The previous answer was refused" not in payload["answer"]
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
                "mode": "default",
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


def test_agent_api_followup_respects_requested_point_count(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        conversation = client.post("/conversations", json={"title": "point-count"}).json()
        first = client.post(
            "/agent/query",
            json={
                "question": "堆石混凝土与自密实混凝土的区别有哪些？",
                "top_k": 2,
                "conversation_id": conversation["id"],
                "mode": "default",
            },
        )
        app.dependency_overrides[get_agent_chat_model_provider] = (
            lambda: OverproducingFollowupTransformProvider()
        )
        second = client.post(
            "/agent/query",
            json={"question": "再增加三点", "conversation_id": conversation["id"]},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    payload = second.json()
    assert payload["refused"] is False
    assert "1. 温控措施" in payload["answer"]
    assert "2. 经济性" in payload["answer"]
    assert "3. 施工工艺" in payload["answer"]
    assert "4. 流动性要求" not in payload["answer"]
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
    assert payload["tool_calls"][0]["tool_name"] == "hybrid_search_knowledge"
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
    assert messages[1]["mode"] == "tool_calling_agent"
    assert messages[1]["content"] == response.json()["answer"]
    assert messages[1]["metadata"]["citations"] == [1]
    assert messages[1]["metadata"]["mode"] == "tool_calling_agent"
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
                "mode": "default",
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
                "mode": "default",
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


def test_agent_api_default_routes_to_tool_calling(tmp_path) -> None:
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
    assert payload["mode"] == "tool_calling_agent"


def test_agent_api_explicit_default_overrides_tool_calling_default(tmp_path) -> None:
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


def test_agent_api_explicit_tool_calling_agent_mode_uses_tool_loop(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 2,
                "max_tool_calls": 3,
                "mode": "tool_calling_agent",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "tool_calling_agent"
    assert payload["refused"] is False
    assert payload["citations"] == [1]
    assert [call["tool_name"] for call in payload["tool_calls"]] == [
        "hybrid_search_knowledge",
    ]
    assert [step["name"] for step in payload["workflow_steps"]] == [
        "hybrid_search_knowledge",
        "final_answer",
    ]
    assert payload["iteration_count"] == 2
    assert payload["latency_trace"]["llm_call_count"] == 2
    assert payload["latency_trace"]["repeated_query_count"] == 0
    assert "tool_calling_agent" in payload["reasoning_summary"]
    serialized = response.text.casefold()
    assert "raw_response" not in serialized
    assert "reasoning_content" not in serialized


def test_agent_api_explicit_langgraph_agent_mode_uses_graph_service(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 2,
                "max_tool_calls": 3,
                "mode": "langgraph_agent",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "langgraph_agent"
    assert payload["refused"] is False
    assert payload["citations"] == [1]
    assert [call["tool_name"] for call in payload["tool_calls"]] == [
        "hybrid_search_knowledge",
        "answer_with_citations",
    ]
    assert [step["name"] for step in payload["workflow_steps"]] == [
        "llm_with_tools",
        "search_knowledge",
        "llm_with_tools",
        "answer_with_citations",
    ]
    assert payload["iteration_count"] == 4
    assert payload["latency_trace"]["langgraph_checkpointer_backend"] in {
        "memory",
        "redis",
    }
    assert "langgraph_agent" in payload["reasoning_summary"]


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


def test_auto_figure_enrichment_is_disabled_by_default(monkeypatch) -> None:
    response = agent_api_module.AgentQueryResponse(
        question="What affects filling capacity?",
        answer="Answer [1].",
        tool_calls=[],
        search_results=[],
        sources=[],
        citations=[1],
        refused=False,
        refusal_reason=None,
        reasoning_summary="test",
        mode="default",
        workflow_steps=[],
        iteration_count=0,
        invalid_citations=[],
        refusal_category=None,
        latency_trace={},
    )

    def fail_enrich(**kwargs):
        raise AssertionError("automatic figure enrichment should be disabled")

    monkeypatch.setattr(
        agent_api_module,
        "get_settings",
        lambda: SimpleNamespace(enable_auto_figure_enrichment=False),
    )
    monkeypatch.setattr(
        agent_api_module,
        "enrich_agent_response_with_figure_evidence",
        fail_enrich,
    )

    assert (
        agent_api_module.maybe_enrich_agent_response_with_figure_evidence(
            db=None,
            question=response.question,
            response=response,
            effective_mode="default",
        )
        is response
    )


def test_react_agent_never_uses_auto_figure_enrichment(monkeypatch) -> None:
    response = agent_api_module.AgentQueryResponse(
        question="Show the interface microstructure figure.",
        answer="Answer [1].",
        tool_calls=[],
        search_results=[],
        sources=[],
        citations=[1],
        refused=False,
        refusal_reason=None,
        reasoning_summary="test",
        mode="react_agent",
        workflow_steps=[],
        iteration_count=0,
        invalid_citations=[],
        refusal_category=None,
        latency_trace={},
    )

    def fail_enrich(**kwargs):
        raise AssertionError("react_agent must use search_figures instead")

    monkeypatch.setattr(
        agent_api_module,
        "get_settings",
        lambda: SimpleNamespace(enable_auto_figure_enrichment=True),
    )
    monkeypatch.setattr(
        agent_api_module,
        "enrich_agent_response_with_figure_evidence",
        fail_enrich,
    )

    assert (
        agent_api_module.maybe_enrich_agent_response_with_figure_evidence(
            db=None,
            question=response.question,
            response=response,
            effective_mode="react_agent",
        )
        is response
    )


def test_auto_figure_enrichment_records_workflow_step() -> None:
    class FakeQuery:
        def join(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            chunk = SimpleNamespace(
                id=2,
                document_id=1,
                chunk_index=1,
                chunk_type="image_description",
                content="Figure evidence showing interface microstructure.",
                heading_path="Figure",
                source_image_path="data/images/1/page2_img3.png",
                caption="Fig. 1 Interface microstructure",
            )
            document = SimpleNamespace(
                id=1,
                title="Agent API filling source",
                file_name="agent-filling.md",
                source_type="local_file",
                source_path="agent-filling.md",
            )
            return [(chunk, document)]

    class FakeSession:
        def query(self, *args, **kwargs):
            return FakeQuery()

    response = agent_api_module.AgentQueryResponse(
        question="What affects filling capacity?",
        answer="Answer [1].",
        tool_calls=[],
        search_results=[],
        sources=[
            agent_api_module.AgentSourceItem(
                source_id="chunk:1",
                title="Agent API filling source",
                source_type="local_file",
                status=None,
                trust_level=None,
                fulltext_permission=None,
                document_id=1,
                chunk_id=1,
                chunk_index=0,
                url=None,
                doi=None,
                content="Filling capacity text.",
                score=1.0,
                chunk_type="text",
            )
        ],
        citations=[1],
        refused=False,
        refusal_reason=None,
        reasoning_summary="test",
        mode="langgraph_agent",
        workflow_steps=[],
        iteration_count=0,
        invalid_citations=[],
        refusal_category=None,
        latency_trace={},
    )

    enriched = agent_api_module.enrich_agent_response_with_figure_evidence(
        db=FakeSession(),
        question=response.question,
        response=response,
    )

    assert any(source.chunk_type == "image_description" for source in enriched.sources)
    assert enriched.workflow_steps[-1].name == "search_figures"
    assert enriched.workflow_steps[-1].output_summary.startswith("auto-enriched 1")


def test_agent_api_off_topic_refusal_includes_safe_rewrite_suggestion(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={"question": "How should I cook pasta for dinner?", "mode": "default"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is True
    assert payload["refusal_category"] == "off_topic"
    assert "refusal_explanation" in payload["reasoning_summary"]
    assert "可以改写为" in payload["reasoning_summary"]
    assert "CORE_DOMAIN_TERMS" not in payload["reasoning_summary"]
    assert "prompt" not in payload["reasoning_summary"].casefold()


def test_agent_api_evidence_insufficient_includes_sanitized_retrieval_summary(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": (
                    "filling capacity alpha beta gamma delta epsilon zeta eta theta iota kappa"
                ),
                "mode": "default",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is True
    assert payload["refusal_category"] == "evidence_insufficient"
    assert "refusal_explanation" in payload["reasoning_summary"]
    assert "Agent API filling source" in payload["reasoning_summary"]
    assert "Filling capacity depends on self-compacting concrete flowability" in payload[
        "reasoning_summary"
    ]
    assert len(payload["reasoning_summary"]) < 1000
    assert "API key" not in payload["reasoning_summary"]
    assert "Bearer token" not in payload["reasoning_summary"]


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
            json={
                "question": "查看来源详情",
                "source_id": "rfc_source_001",
                "mode": "default",
            },
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
