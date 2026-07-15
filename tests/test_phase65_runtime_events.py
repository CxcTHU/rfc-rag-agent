from app.services.agent.runtime_events import (
    RuntimeEventBus,
    publish_tool_call_result,
    project_tool_calling_event,
)
from app.services.agent.tools import AgentToolCallRecord
from app.services.agent.tool_calling_service import (
    ToolCallingAgentService,
    ToolCallingRuntimeEvent,
)
from app.services.observability.latency_trace import LatencyTrace


def test_event_bus_assigns_monotonic_sequence_and_redacts_forbidden_keys() -> None:
    received = []
    bus = RuntimeEventBus(run_id="run-1", clock=lambda: 10.0)
    bus.subscribe(received.append)

    bus.emit(
        "retrieval",
        "tool_call_start",
        {"tool_name": "search_tables", "raw_response": "must-not-leak"},
    )

    assert received[0].sequence == 1
    assert received[0].payload == {"tool_name": "search_tables"}


def test_progress_event_does_not_mark_answer_token() -> None:
    trace = LatencyTrace(started_at=10.0)

    RuntimeEventBus(run_id="run-1", trace=trace, clock=lambda: 11.0).emit(
        "planning", "agent_step", {}
    )

    assert trace.values["time_to_first_answer_token_ms"] is None
    assert isinstance(trace.values["time_to_first_progress_ms"], float)


def test_projection_preserves_legacy_sse_shape() -> None:
    event = RuntimeEventBus(run_id="run-1", clock=lambda: 10.0).emit(
        "retrieval", "tool_call_result", {"tool_name": "search_tables", "succeeded": True}
    )

    projected = project_tool_calling_event(event)

    assert isinstance(projected, ToolCallingRuntimeEvent)
    assert projected.event == "tool_call_result"
    assert projected.payload == {"tool_name": "search_tables", "succeeded": True}


def test_service_emits_through_runtime_bus_without_changing_sse_shape() -> None:
    trace = LatencyTrace()
    received = []
    bus = RuntimeEventBus(run_id="run-1", trace=trace)
    bus.subscribe(received.append)

    ToolCallingAgentService._emit(
        object(),
        bus,
        "agent_step",
        {"iteration": 1, "action": "llm_with_tools", "raw_response": "secret"},
    )

    assert received[0].stage == "planning"
    assert received[0].sequence == 1
    assert received[0].payload == {"iteration": 1, "action": "llm_with_tools"}
    assert project_tool_calling_event(received[0]) == ToolCallingRuntimeEvent(
        event="agent_step",
        payload={"iteration": 1, "action": "llm_with_tools"},
    )


def test_shared_tool_result_publisher_preserves_safe_projection() -> None:
    received = []
    bus = RuntimeEventBus(run_id="run-1")
    bus.subscribe(received.append)

    publish_tool_call_result(
        bus,
        iteration=1,
        record=AgentToolCallRecord(
            tool_name="search_tables",
            input_summary="query=parameters",
            output_summary="selected=2",
            succeeded=True,
            step_id="tool-1",
        ),
        selected_count=2,
    )

    assert received[0].name == "tool_call_result"
    assert received[0].payload == {
        "iteration": 1,
        "step_id": "tool-1",
        "tool_name": "search_tables",
        "observation_summary": "selected=2",
        "succeeded": True,
        "skipped": False,
        "selected_count": 2,
    }
