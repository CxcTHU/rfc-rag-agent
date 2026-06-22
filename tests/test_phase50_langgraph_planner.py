from __future__ import annotations

from collections.abc import Sequence

from app.services.agent.graph_builder import LangGraphAgentService
from app.services.agent.graph_nodes import (
    initialize_state,
    reset_current_planner_provider,
    planner_node,
    set_current_planner_provider,
)
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelResult,
    DeterministicChatModelProvider,
)
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from tests.test_phase50_langgraph_nodes import FakeToolbox
from tests.test_phase50_langgraph_nodes import source_reference


class FakePlannerProvider:
    provider_name = "fast"
    model_name = "mock-planner"

    def __init__(self, answer: str | Sequence[str]) -> None:
        self.answers = [answer] if isinstance(answer, str) else list(answer)
        self.messages: list[ChatMessage] = []
        self.call_count = 0

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        self.messages = list(messages)
        index = min(self.call_count, len(self.answers) - 1)
        self.call_count += 1
        return ChatModelResult(
            answer=self.answers[index],
            provider=self.provider_name,
            model_name=self.model_name,
            raw_response=None,
        )


def test_planner_node_uses_planner_llm_json_action() -> None:
    planner = FakePlannerProvider(
        [
            '{"action":"search_figures","query":"crack examples","reasoning_summary":"visual request"}',
            '{"action":"answer_with_citations","reasoning_summary":"figure evidence is available"}',
        ]
    )
    trace = LatencyTrace()
    latency_token = set_current_latency_trace(trace)
    planner_token = set_current_planner_provider(planner)
    try:
        updates = planner_node(initialize_state(question="Show crack examples"))
    finally:
        reset_current_planner_provider(planner_token)
        reset_current_latency_trace(latency_token)

    assert updates["next_action"] == "search_figures"
    assert updates["current_query"] == "crack examples"
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"
    assert updates["workflow_steps"][0]["output_summary"] == "selected action=search_figures"
    assert trace.values["planner_model"] == "fast/mock-planner"
    assert trace.values["planner_latency_ms"] >= 0
    assert "Allowed actions" in planner.messages[1].content


def test_planner_node_llm_prompt_includes_prior_evidence() -> None:
    planner = FakePlannerProvider(
        '{"action":"answer_with_citations","reasoning_summary":"prior evidence is enough"}'
    )
    state = initialize_state(question="请详细回答")
    state["prior_sources"] = [
        source_reference(chunk_id=1).__dict__,
        source_reference(chunk_id=2).__dict__,
        source_reference(chunk_id=3).__dict__,
    ]
    state["prior_answer_summary"] = "上一轮回答说明填充性能受颗粒和流体阻塞影响。"
    planner_token = set_current_planner_provider(planner)
    try:
        updates = planner_node(state)
    finally:
        reset_current_planner_provider(planner_token)

    assert updates["next_action"] == "answer_with_citations"
    assert "Prior evidence from the same conversation" in planner.messages[1].content
    assert "fixture source evidence" in planner.messages[1].content
    assert "上一轮回答说明" in planner.messages[1].content


def test_planner_node_falls_back_to_deterministic_on_invalid_planner_json() -> None:
    planner = FakePlannerProvider("not json")
    trace = LatencyTrace()
    latency_token = set_current_latency_trace(trace)
    planner_token = set_current_planner_provider(planner)
    try:
        updates = planner_node(initialize_state(question="What affects filling capacity?"))
    finally:
        reset_current_planner_provider(planner_token)
        reset_current_latency_trace(latency_token)

    assert updates["next_action"] == "search_knowledge"
    assert updates["current_query"] == "What affects filling capacity?"
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"
    assert trace.values["planner_model"] == "deterministic"


def test_planner_node_without_planner_preserves_deterministic_behavior() -> None:
    trace = LatencyTrace()
    latency_token = set_current_latency_trace(trace)
    try:
        updates = planner_node(initialize_state(question="What affects filling capacity?"))
    finally:
        reset_current_latency_trace(latency_token)

    assert updates["next_action"] == "search_knowledge"
    assert updates["current_query"] == "What affects filling capacity?"
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"
    assert trace.values["planner_model"] == "deterministic"
    assert trace.values["planner_latency_ms"] == 0.0


def test_langgraph_agent_service_injects_and_resets_planner_provider() -> None:
    planner = FakePlannerProvider(
        [
            '{"action":"search_figures","query":"crack examples","reasoning_summary":"visual request"}',
            '{"action":"answer_with_citations","reasoning_summary":"figure evidence is available"}',
        ]
    )

    class FakeSession:
        pass

    service = LangGraphAgentService(
        db=FakeSession(),  # type: ignore[arg-type]
        embedding_provider=DeterministicEmbeddingProvider(),
        chat_model_provider=DeterministicChatModelProvider(),
        planner_chat_provider=planner,
    )
    service.toolbox = FakeToolbox()  # type: ignore[assignment]

    result = service.query("Show crack examples", top_k=2)
    assert result.workflow_steps[0].tool_name == "llm_with_tools"
    assert result.workflow_steps[1].tool_name == "search_figures"
    assert result.latency_trace["planner_model"] == "fast/mock-planner"

    updates = planner_node(initialize_state(question="What affects filling capacity?"))
    assert updates["next_action"] == "search_knowledge"
