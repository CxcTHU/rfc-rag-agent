from __future__ import annotations

import inspect

from app.core.config import get_settings
from app.schemas.agent import AgentQueryRequest
from app.services.agent.tool_calling_service import (
    ToolCallingAgentService,
    tool_calling_tool_definitions,
)
from app.services.agent.tools import AgentToolCallRecord, AgentToolResult
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from tests.test_agent_api import make_test_client
from tests.test_tool_calling_agent_service import make_session, seed_tool_calling_documents


class CountingPhase63ToolPlanningProvider:
    provider_name = "phase63-tool-loop"
    model_name = "phase63-tool-loop-v1"

    def __init__(self) -> None:
        self.delegate = DeterministicChatModelProvider(
            provider_name=self.provider_name,
            model_name=self.model_name,
        )
        self.generate_with_tools_calls = 0

    def generate(self, messages):
        return self.delegate.generate(messages)

    def stream_generate(self, messages):
        yield from self.delegate.stream_generate(messages)

    def generate_with_tools(self, messages, tools):
        self.generate_with_tools_calls += 1
        return self.delegate.generate_with_tools(messages, tools)


def test_agent_request_exposes_only_the_production_mode() -> None:
    assert AgentQueryRequest.model_fields["mode"].annotation is not None
    assert "top_k" not in AgentQueryRequest.model_fields
    assert "source_id" not in AgentQueryRequest.model_fields

    request = AgentQueryRequest(
        question="堆石混凝土",
        mode="tool_calling_agent",
        top_k=1,
        source_id="legacy-source",
    )
    assert request.mode == "tool_calling_agent"
    assert "top_k" not in request.model_dump()
    assert "source_id" not in request.model_dump()


def test_high_level_tool_schemas_and_service_do_not_expose_top_k() -> None:
    for definition in tool_calling_tool_definitions():
        assert set(definition.function.parameters["properties"]) == {"query"}

    assert "top_k" not in inspect.signature(ToolCallingAgentService.query).parameters


def test_retired_run_coordinator_flag_keeps_runtime_owned_tool_selection(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "false")
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "false")
    monkeypatch.setenv("SEMANTIC_EVIDENCE_CACHE_ENABLED", "false")
    get_settings.cache_clear()
    session_factory = make_session(tmp_path)
    with session_factory() as db:
        seed_tool_calling_documents(db)
        provider = CountingPhase63ToolPlanningProvider()
        service = ToolCallingAgentService(
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=provider,
            log_answers=False,
        )
        result = service.query("What affects filling capacity?")

    assert provider.generate_with_tools_calls == 0
    assert result.latency_trace["run_coordinator_enabled"] is True
    assert result.latency_trace["executed_tool_call_count"] == 1


def test_unified_agent_api_rejects_retired_mode_and_ignores_top_k(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        mode_response = client.post(
            "/agent/query",
            json={"question": "What affects filling capacity?", "mode": "agentic"},
        )
        top_k_response = client.post(
            "/agent/query/stream",
            json={"question": "What affects filling capacity?", "top_k": 1},
        )

    assert mode_response.status_code == 422
    assert top_k_response.status_code == 200


def test_tool_calling_agent_handles_uploaded_image_without_react_mode(tmp_path, monkeypatch) -> None:
    testing_session = make_session(tmp_path)
    with testing_session() as db:
        seed_tool_calling_documents(db)
        service = ToolCallingAgentService(
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        image_result = AgentToolResult(
            tool_name="analyze_user_image",
            call=AgentToolCallRecord(
                tool_name="analyze_user_image",
                input_summary="image_path=<user_upload>",
                output_summary="image analyzed",
                succeeded=True,
            ),
            answer="图片分析要点：发现混凝土裂缝。",
            image_analysis={"domain_relevance": "in_scope"},
        )
        monkeypatch.setattr(service.toolbox, "analyze_user_image", lambda *args, **kwargs: image_result)
        result = service.query(
            "请分析这张混凝土裂缝图片。",
            image_path="data/user_uploads/2026-07-12/crack.png",
        )

    assert result.mode == "tool_calling_agent"
    assert result.answer == "图片分析要点：发现混凝土裂缝。"
    assert result.image_analysis == {"domain_relevance": "in_scope"}
    assert [call.tool_name for call in result.tool_calls] == ["analyze_user_image"]
