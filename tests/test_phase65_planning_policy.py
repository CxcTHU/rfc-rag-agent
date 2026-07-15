from __future__ import annotations

from app.core.config import Settings
from app.services.agent.planning_policy import PlanningPolicy, PlanningRequest
from app.services.generation.chat_model import ChatModelResult
from app.services.observability.latency_trace import LatencyTrace


class CountingInvalidPlanner:
    provider_name = "phase65-invalid-planner"
    model_name = "phase65-invalid-planner-v1"

    def __init__(self) -> None:
        self.generate_calls = 0

    def generate(self, _messages: object) -> ChatModelResult:
        self.generate_calls += 1
        return ChatModelResult(
            answer="not-json",
            provider=self.provider_name,
            model_name=self.model_name,
        )


def phase65_settings() -> Settings:
    return Settings(
        agent_short_loop_enabled=True,
        phase64_route_first_enabled=True,
        retrieval_runtime_enabled=True,
    )


def test_fast_route_uses_deterministic_identity_without_model_call() -> None:
    provider = CountingInvalidPlanner()
    trace = LatencyTrace()

    decision = PlanningPolicy(provider, settings=phase65_settings()).plan(
        PlanningRequest(
            question="堆石混凝土优势",
            history=(),
            image_path=None,
            trace=trace,
        )
    )

    assert decision.route is not None and decision.route.kind == "fast"
    assert decision.planner_call_count == 0
    assert decision.action.required_tool is None
    assert provider.generate_calls == 0


def test_invalid_complex_planner_falls_back_to_deterministic_identity() -> None:
    provider = CountingInvalidPlanner()
    trace = LatencyTrace()

    decision = PlanningPolicy(provider, settings=phase65_settings()).plan(
        PlanningRequest(
            question="施工参数如何影响密实度？",
            history=(),
            image_path=None,
            trace=trace,
        )
    )

    assert decision.route is not None and decision.route.kind == "complex"
    assert decision.identity.reason == "llm_identity_invalid_json"
    assert decision.used_fallback is True
    assert decision.escalation_count == 0
    assert decision.planner_call_count == 1
    assert provider.generate_calls == 1


def test_fast_route_can_escalate_once_without_reassembling_runtime_state() -> None:
    provider = CountingInvalidPlanner()
    trace = LatencyTrace()
    policy = PlanningPolicy(provider, settings=phase65_settings())
    request = PlanningRequest(
        question="堆石混凝土优势",
        history=(),
        image_path=None,
        trace=trace,
    )
    initial = policy.plan(request)

    escalated = policy.escalate_fast_route(request, initial)

    assert initial.runtime_state is escalated.runtime_state
    assert escalated.escalation_count == 1
    assert escalated.planner_call_count == 1
    assert provider.generate_calls == 1
    assert trace.values["phase64_execution_graph"] == "phase64_complex"
