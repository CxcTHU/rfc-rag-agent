import json

import time

from sqlalchemy.orm import sessionmaker

from app.api.agent import stream_agent_query_events
from app.db.models import Base
from app.db.repositories import ConversationRepository
from app.db.session import create_sqlite_engine
from app.schemas.agent import AgentQueryRequest
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelResult,
    ChatToolCall,
    ChatToolDefinition,
    ToolCallingChatModelResult,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from tests.test_agent_api import make_test_client, seed_agent_api_document, source_record
from app.db.repositories import SourceRepository


def parse_sse_events(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for raw_event in body.strip().split("\n\n"):
        event_name = ""
        data = "{}"
        for line in raw_event.splitlines():
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data = line.removeprefix("data:").strip()
        if event_name:
            events.append((event_name, json.loads(data)))
    return events


def test_agent_stream_api_defaults_to_tool_calling_metadata_done(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query/stream",
            json={"question": "What affects filling capacity?", "top_k": 2},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse_events(response.text)
    event_names = [name for name, _payload in events]
    assert "agent_step" in event_names
    assert "tool_call_start" in event_names
    assert "tool_call_result" in event_names
    assert event_names[-2:] == ["metadata", "done"]

    streamed_answer = "".join(payload["text"] for name, payload in events if name == "token")
    metadata = next(payload for name, payload in events if name == "metadata")
    assert metadata["answer"] == streamed_answer
    assert metadata["mode"] == "tool_calling_agent"
    assert metadata["citations"] == [1]
    assert metadata["sources"]


def test_agent_stream_api_short_circuits_chitchat(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query/stream",
            json={"question": "谢谢", "top_k": 2},
        )

    assert response.status_code == 200
    events = parse_sse_events(response.text)
    event_names = [name for name, _payload in events]
    assert event_names[0] == "token"
    assert event_names[-2:] == ["metadata", "done"]
    metadata = events[-2][1]
    streamed_answer = "".join(payload["text"] for name, payload in events if name == "token")
    assert metadata["answer"] == streamed_answer
    assert metadata["tool_calls"] == []
    assert metadata["sources"] == []
    assert "闲聊短路" in metadata["reasoning_summary"]


def test_agent_stream_api_short_circuits_model_meta(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query/stream",
            json={"question": "你用的什么大模型？", "top_k": 2},
        )

    assert response.status_code == 200
    events = parse_sse_events(response.text)
    event_names = [name for name, _payload in events]
    assert event_names[0] == "token"
    assert event_names[-2:] == ["metadata", "done"]
    metadata = events[-2][1]
    streamed_answer = "".join(payload["text"] for name, payload in events if name == "token")
    assert metadata["answer"] == streamed_answer
    assert metadata["tool_calls"] == []
    assert metadata["sources"] == []
    assert metadata["mode"] == "meta"
    assert "deterministic / rule-based-chat-v1" in metadata["answer"]
    assert "agent_meta" in metadata["reasoning_summary"]


def test_agent_stream_api_persists_completed_conversation_messages(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        conversation = client.post("/conversations", json={"title": "流式"}).json()
        response = client.post(
            "/agent/query/stream",
            json={
                "question": "What affects filling capacity?",
                "top_k": 2,
                "conversation_id": conversation["id"],
            },
        )
        messages_response = client.get(f"/conversations/{conversation['id']}/messages")

    assert response.status_code == 200
    messages = messages_response.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "What affects filling capacity?"
    assert messages[1]["metadata"]["citations"] == [1]


def test_agent_stream_api_default_routes_to_tool_calling(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query/stream",
            json={
                "question": (
                    "Search and compare filling capacity and thermal control "
                    "mechanisms in rock-filled concrete."
                ),
                "top_k": 2,
            },
        )

    assert response.status_code == 200
    events = parse_sse_events(response.text)
    metadata = next(payload for name, payload in events if name == "metadata")
    assert metadata["mode"] == "tool_calling_agent"
    assert events[-1][0] == "done"


def test_agent_stream_api_supports_tool_calling_agent_mode(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query/stream",
            json={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 2,
                "max_tool_calls": 3,
                "mode": "tool_calling_agent",
            },
        )

    assert response.status_code == 200
    events = parse_sse_events(response.text)
    event_names = [name for name, _payload in events]
    assert "agent_step" in event_names
    assert "tool_call_start" in event_names
    assert "tool_call_result" in event_names
    assert event_names[-2:] == ["metadata", "done"]
    metadata = next(payload for name, payload in events if name == "metadata")
    assert metadata["mode"] == "tool_calling_agent"
    assert metadata["citations"] == [1]
    assert metadata["tool_calls"][0]["tool_name"] == "hybrid_search_knowledge"
    assert metadata["latency_trace"]["llm_call_count"] == 2
    serialized = response.text.casefold()
    assert "raw_response" not in serialized
    assert "reasoning_content" not in serialized
    assert "bearer" not in serialized


def test_agent_stream_api_supports_langgraph_agent_mode(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query/stream",
            json={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 2,
                "max_tool_calls": 3,
                "mode": "langgraph_agent",
            },
        )

    assert response.status_code == 200
    events = parse_sse_events(response.text)
    event_names = [name for name, _payload in events]
    assert "agent_step" in event_names
    assert "tool_call_start" in event_names
    assert "tool_call_result" in event_names
    assert event_names[-2:] == ["metadata", "done"]
    metadata = next(payload for name, payload in events if name == "metadata")
    assert metadata["mode"] == "langgraph_agent"
    assert metadata["citations"] == [1]
    assert [call["tool_name"] for call in metadata["tool_calls"]] == [
        "hybrid_search_knowledge",
        "answer_with_citations",
    ]
    serialized = response.text.casefold()
    assert "raw_response" not in serialized
    assert "reasoning_content" not in serialized
    assert "bearer" not in serialized


def test_agent_stream_api_returns_404_for_missing_conversation_id(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query/stream",
            json={"question": "你好", "conversation_id": 999},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "conversation not found"


class SlowStreamingChatModelProvider:
    provider_name = "slow-stream"
    model_name = "slow-stream-model"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer="".join(self.stream_generate(messages)),
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def stream_generate(self, messages: list[ChatMessage]):
        yield "Filling "
        time.sleep(0.4)
        yield "capacity depends on SCC flowability [1]."


class SlowToolCallingStreamingChatModelProvider:
    provider_name = "slow-tool-stream"
    model_name = "slow-tool-stream-model"

    def generate_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ChatToolDefinition],
    ) -> ToolCallingChatModelResult:
        if not any(message.role == "tool" for message in messages):
            return ToolCallingChatModelResult(
                content="",
                tool_calls=[
                    ChatToolCall(
                        id="call_1",
                        name="hybrid_search_knowledge",
                        arguments={"query": "filling capacity", "top_k": 2},
                    )
                ],
                provider=self.provider_name,
                model_name=self.model_name,
            )
        return ToolCallingChatModelResult(
            content="",
            tool_calls=[
                ChatToolCall(
                    id="call_2",
                    name="hybrid_search_knowledge",
                    arguments={"query": "filling capacity", "top_k": 2},
                )
            ],
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer="".join(self.stream_generate(messages)),
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def stream_generate(self, messages: list[ChatMessage]):
        yield "Filling "
        time.sleep(0.4)
        yield "capacity depends on SCC flowability [1]."


def test_agent_stream_yields_first_token_before_model_finishes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.create_reranking_provider",
        lambda **_kwargs: None,
    )
    database_path = tmp_path / "agent_stream_timing.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    embedding_provider = DeterministicEmbeddingProvider(dimension=32)

    with TestingSessionLocal() as db:
        seed_agent_api_document(db)
        SourceRepository(db).create_source(source_record())

        with TestingSessionLocal() as db:
            event_stream = stream_agent_query_events(
                request=AgentQueryRequest(
                    question="What affects filling capacity?",
                    top_k=2,
                    mode="default",
                ),
                db=db,
                conversation_repository=ConversationRepository(db),
            conversation_history=[],
            chat_model_provider=SlowStreamingChatModelProvider(),
            embedding_provider=embedding_provider,
        )

        started_at = time.perf_counter()
        first_event = next(event_stream)
        elapsed = time.perf_counter() - started_at
        remaining_events = list(event_stream)

    assert elapsed < 0.25
    assert first_event.startswith("event: token\n")
    assert '"Filling "' in first_event
    assert any("event: metadata" in event for event in remaining_events)


def test_tool_calling_agent_streams_final_answer_before_model_finishes(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.create_reranking_provider",
        lambda **_kwargs: None,
    )
    database_path = tmp_path / "tool_calling_stream_timing.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    embedding_provider = DeterministicEmbeddingProvider(dimension=32)

    with TestingSessionLocal() as db:
        seed_agent_api_document(db)
        SourceRepository(db).create_source(source_record())

        with TestingSessionLocal() as db:
            event_stream = stream_agent_query_events(
                request=AgentQueryRequest(
                    question="What affects filling capacity?",
                    top_k=2,
                    mode="tool_calling_agent",
                ),
                db=db,
                conversation_repository=ConversationRepository(db),
                conversation_history=[],
                chat_model_provider=SlowToolCallingStreamingChatModelProvider(),
                embedding_provider=embedding_provider,
            )

            started_at = time.perf_counter()
            first_token_event = ""
            for event in event_stream:
                if event.startswith("event: token\n"):
                    first_token_event = event
                    break
            elapsed = time.perf_counter() - started_at
            remaining_events = list(event_stream)

    assert elapsed < 0.35
    assert '"Filling "' in first_token_event
    assert any("event: metadata" in event for event in remaining_events)
