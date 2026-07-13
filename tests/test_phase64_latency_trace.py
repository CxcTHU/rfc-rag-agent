from __future__ import annotations

from types import SimpleNamespace

import app.api.agent as agent_api
import app.services.observability.latency_trace as latency_trace_module
from app.schemas.agent import AgentQueryRequest
from app.services.observability.latency_trace import LatencyTrace


class FakePerfCounter:
    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


def test_trace_includes_context_and_planner_before_service_dispatch(monkeypatch) -> None:
    clock = FakePerfCounter([10.0, 10.1, 10.3, 10.7, 11.0])
    monkeypatch.setattr(latency_trace_module.time, "perf_counter", clock)
    trace = LatencyTrace(started_at=clock())

    with trace.span("context_assembly_latency_ms"):
        pass
    trace.mark_progress()
    trace.mark_answer_token()

    assert trace.values["context_assembly_latency_ms"] == 200.0
    assert trace.values["time_to_first_progress_ms"] == 700.0
    assert trace.values["time_to_first_answer_token_ms"] == 1000.0
    assert trace.values["time_to_first_token_ms"] == 1000.0


def test_trace_exposes_unambiguous_phase64_component_timings() -> None:
    trace = LatencyTrace()

    assert {
        "planner_ttft_ms",
        "retrieval_total_latency_ms",
        "glm_rerank_latency_ms",
        "final_model_ttft_ms",
        "final_generation_latency_ms",
        "citation_validation_latency_ms",
    }.issubset(trace.values)


def test_api_passes_the_supplied_trace_to_service(monkeypatch) -> None:
    seen: list[LatencyTrace] = []

    class CapturingService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def query(self, **kwargs: object) -> object:
            seen.append(kwargs["latency_trace"])
            return object()

    response = SimpleNamespace(latency_trace={})
    monkeypatch.setattr(agent_api, "ToolCallingAgentService", CapturingService)
    monkeypatch.setattr(agent_api, "agent_response_from_result", lambda _result: response)
    monkeypatch.setattr(agent_api, "log_agent_response_event", lambda _response: None)
    trace = LatencyTrace()

    actual = agent_api.build_agent_query_response(
        request=AgentQueryRequest(question="trace boundary"),
        db=object(),
        conversation_history=[],
        chat_model_provider=object(),
        embedding_provider=object(),
        latency_trace=trace,
    )

    assert actual is response
    assert seen == [trace]
