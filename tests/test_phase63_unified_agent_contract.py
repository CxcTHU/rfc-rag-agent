from __future__ import annotations

import inspect

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


def test_agent_request_drops_retired_retrieval_controls() -> None:
    assert "mode" not in AgentQueryRequest.model_fields
    assert "top_k" not in AgentQueryRequest.model_fields
    assert "source_id" not in AgentQueryRequest.model_fields

    request = AgentQueryRequest(
        question="堆石混凝土",
        mode="react_agent",
        top_k=1,
        source_id="legacy-source",
    )
    assert "mode" not in request.model_dump()
    assert "top_k" not in request.model_dump()
    assert "source_id" not in request.model_dump()


def test_high_level_tool_schemas_and_service_do_not_expose_top_k() -> None:
    for definition in tool_calling_tool_definitions():
        assert set(definition.function.parameters["properties"]) == {"query"}

    assert "top_k" not in inspect.signature(ToolCallingAgentService.query).parameters


def test_unified_agent_api_ignores_legacy_mode_and_top_k(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        mode_response = client.post(
            "/agent/query",
            json={"question": "What affects filling capacity?", "mode": "agentic"},
        )
        top_k_response = client.post(
            "/agent/query/stream",
            json={"question": "What affects filling capacity?", "top_k": 1},
        )

    assert mode_response.status_code == 200
    assert top_k_response.status_code == 200
    assert mode_response.json()["mode"] == "tool_calling_agent"


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
