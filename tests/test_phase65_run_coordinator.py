from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.services.agent.evidence_state_machine import EvidenceStateMachine
from app.services.agent.run_coordinator import RunCoordinator
from app.services.agent.runtime import AgentRuntimeState, RuntimeContext
from app.services.agent.runtime_contracts import (
    CoordinatorRequest,
    FinalAnswerRequest,
    PreToolGateDecision,
    RunBudget,
)
from app.services.agent.runtime_events import RuntimeEvent, RuntimeEventBus
from app.services.agent.tools import AgentToolCallRecord
from app.services.observability.latency_trace import (
    LatencyTrace,
    get_current_latency_trace,
)
from app.services.retrieval.route_context import current_phase64_route_kind
from app.services.retrieval.runtime import current_retrieval_plan
from app.services.retrieval.hybrid_search import current_hyde_vector_query


def test_coordinator_calls_modules_in_order() -> None:
    calls: list[str] = []
    planning = SimpleNamespace(
        plan=lambda request: calls.append("plan")
        or SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
        )
    )
    checkpoints = SimpleNamespace(
        start=lambda request, decision: calls.append("checkpoint_start") or "run-1",
        persist_state=lambda run, **kwargs: calls.append(f"checkpoint_{kwargs['node']}"),
        complete=lambda run, outcome: calls.append("checkpoint_complete"),
    )
    executor = SimpleNamespace(
        execute=lambda request: calls.append("execute") or SimpleNamespace(result="tool-result"),
    )
    evidence = SimpleNamespace(
        evaluate=lambda **_: calls.append("evidence")
        or SimpleNamespace(action="answer"),
    )
    finals = SimpleNamespace(
        generate=lambda request: calls.append("finalize")
        or SimpleNamespace(result="final-result"),
    )
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=executor,
        evidence_machine=evidence,
        final_answers=finals,
        final_request_builder=lambda *args: "final-request",
    )

    result = coordinator.run(
        CoordinatorRequest(
            question="问题",
            budget=RunBudget(max_tool_calls=1, max_iterations=1),
            history=(),
            event_sink=None,
            conversation_id=None,
            resume_policy="auto",
            resume_run_id=None,
            image_path=None,
            latency_trace=LatencyTrace(),
        )
    )

    assert result == "final-result"
    assert calls == [
        "plan",
        "checkpoint_start",
        "execute",
        "checkpoint_tool_execution_completed",
        "evidence",
        "finalize",
        "checkpoint_final_answer_completed",
        "checkpoint_complete",
    ]


def test_coordinator_resets_latency_trace_when_planning_raises() -> None:
    coordinator = RunCoordinator(
        planning_policy=SimpleNamespace(
            plan=lambda _: (_ for _ in ()).throw(ValueError("invalid planner output"))
        ),
        checkpoints=SimpleNamespace(start=lambda *_: "run-1", complete=lambda *_: None),
        tool_executor=SimpleNamespace(execute=lambda _: SimpleNamespace(result="tool-result")),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: SimpleNamespace(action="answer")),
        final_answers=SimpleNamespace(generate=lambda _: SimpleNamespace(result="final-result")),
        final_request_builder=lambda *args: "final-request",
    )

    with pytest.raises(ValueError, match="invalid planner output"):
        coordinator.run(_request_with_trace(LatencyTrace()))

    assert get_current_latency_trace() is None


def test_coordinator_refuses_without_final_generation_when_evidence_is_insufficient() -> None:
    calls: list[str] = []
    planning = SimpleNamespace(
        plan=lambda request: calls.append("plan")
        or SimpleNamespace(action=SimpleNamespace(required_tool="search_tables", forbidden_tools=()), canonical_task="任务")
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: calls.append("checkpoint_start") or "run-1",
        complete=lambda *_: calls.append("checkpoint_complete"),
    )
    executor = SimpleNamespace(execute=lambda _: calls.append("execute") or SimpleNamespace(result="tool-result"))
    evidence = SimpleNamespace(evaluate=lambda **_: calls.append("evidence") or SimpleNamespace(action="refuse"))
    finals = SimpleNamespace(
        generate=lambda _: (_ for _ in ()).throw(AssertionError("must not generate")),
        refuse=lambda _: calls.append("refuse") or SimpleNamespace(result="refused-result"),
    )
    coordinator = RunCoordinator(
        planning_policy=planning, checkpoints=checkpoints, tool_executor=executor,
        evidence_machine=evidence, final_answers=finals,
        final_request_builder=lambda *args: "final-request",
    )

    result = coordinator.run(_request())

    assert result == "refused-result"
    assert calls == ["plan", "checkpoint_start", "execute", "evidence", "refuse", "checkpoint_complete"]


def test_coordinator_performs_only_the_policy_owned_escalation_before_answering() -> None:
    calls: list[str] = []
    iterations: list[int] = []
    deadlines: list[float | None] = []
    initial = SimpleNamespace(action=SimpleNamespace(required_tool=None, forbidden_tools=()), canonical_task="初始")
    escalated = SimpleNamespace(action=SimpleNamespace(required_tool=None, forbidden_tools=()), canonical_task="升级")
    planning = SimpleNamespace(
        plan=lambda _: calls.append("plan") or initial,
        escalate_fast_route=lambda *_: calls.append("escalate") or escalated,
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: calls.append("checkpoint_start") or "run-1",
        complete=lambda *_: calls.append("checkpoint_complete"),
    )
    def execute(request):
        calls.append("execute")
        iterations.append(request.iteration)
        deadlines.append(request.deadline_monotonic)
        return SimpleNamespace(result="tool-result")

    executor = SimpleNamespace(execute=execute)
    decisions = iter((SimpleNamespace(action="escalate"), SimpleNamespace(action="answer")))
    evidence = SimpleNamespace(evaluate=lambda **_: calls.append("evidence") or next(decisions))
    finals = SimpleNamespace(generate=lambda _: calls.append("finalize") or SimpleNamespace(result="final-result"))
    coordinator = RunCoordinator(
        planning_policy=planning, checkpoints=checkpoints, tool_executor=executor,
        evidence_machine=evidence, final_answers=finals,
        final_request_builder=lambda *args: "final-request",
    )

    request = _request(deadline_monotonic=123.0)

    assert coordinator.run(request) == "final-result"
    assert calls == ["plan", "checkpoint_start", "execute", "evidence", "escalate", "execute", "evidence", "finalize", "checkpoint_complete"]
    assert iterations == [1, 2]
    assert deadlines == [123.0, 123.0]


def test_coordinator_passes_completed_tool_ids_from_checkpoint() -> None:
    completed_snapshots: list[frozenset[str]] = []
    completed_sequence = [
            frozenset({"runtime-retrieval-0"}),
            frozenset({"runtime-retrieval-0"}),
            frozenset({"runtime-retrieval-0", "runtime-retrieval-1"}),
            frozenset({"runtime-retrieval-0", "runtime-retrieval-1"}),
    ]

    def completed_tool_ids(_run):
        if len(completed_sequence) > 1:
            return completed_sequence.pop(0)
        return completed_sequence[0]
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="初始",
        ),
        escalate_fast_route=lambda *_: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="升级",
        ),
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: "run-1",
        persist_state=lambda *_args, **_kwargs: None,
        completed_tool_ids=completed_tool_ids,
        complete=lambda *_: None,
    )

    def execute(request):
        completed_snapshots.append(request.completed_tool_ids)
        return SimpleNamespace(result="tool-result")

    decisions = iter((SimpleNamespace(action="escalate"), SimpleNamespace(action="answer")))
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=SimpleNamespace(execute=execute),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: next(decisions)),
        final_answers=SimpleNamespace(generate=lambda _: SimpleNamespace(result="final-result")),
        final_request_builder=lambda *args: "final-request",
    )

    assert coordinator.run(_request()) == "final-result"
    assert completed_snapshots == [
        frozenset({"runtime-retrieval-0"}),
        frozenset({"runtime-retrieval-0", "runtime-retrieval-1"}),
    ]


def test_coordinator_records_tool_execution_latency_breakdown() -> None:
    trace = LatencyTrace()
    elapsed_by_tool = {
        "search_figures": 12000.0,
        "hybrid_search_knowledge": 2200.0,
    }
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(
                required_tool="search_figures",
                forbidden_tools=(),
                tool_sequence=("search_figures", "hybrid_search_knowledge"),
            ),
            canonical_task="图示证据",
        )
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: "run-1",
        persist_state=lambda *_args, **_kwargs: None,
        completed_tool_ids=lambda *_: frozenset(),
        complete=lambda *_: None,
    )

    def execute(request):
        tool_name = request.call.name
        return SimpleNamespace(
            elapsed_ms=elapsed_by_tool[tool_name],
            result=SimpleNamespace(
                tool_name=tool_name,
                call=AgentToolCallRecord(
                    tool_name=tool_name,
                    input_summary=tool_name,
                    output_summary="ok",
                    succeeded=True,
                ),
                search_results=["result"],
                sources=["source"],
            ),
        )

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=SimpleNamespace(execute=execute),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: SimpleNamespace(action="answer")),
        final_answers=SimpleNamespace(generate=lambda _: SimpleNamespace(result="final-result")),
        final_request_builder=lambda *args: "final-request",
    )

    assert coordinator.run(_request_with_trace(trace)) == "final-result"
    assert trace.values["tool_execution_latency_ms"] == 14200.0
    assert trace.values["tool_latency_ms"] == 14200.0
    assert trace.values["search_figures_latency_ms"] == 12000.0
    assert trace.values["hybrid_search_knowledge_latency_ms"] == 2200.0


def test_coordinator_skips_hybrid_supplement_for_pure_figure_lookup() -> None:
    executed_tools: list[str] = []
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(
                required_tool="search_figures",
                forbidden_tools=(),
                tool_sequence=("search_figures", "hybrid_search_knowledge"),
            ),
            canonical_task="figure evidence",
        )
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: "run-1",
        persist_state=lambda *_args, **_kwargs: None,
        completed_tool_ids=lambda *_: frozenset(),
        complete=lambda *_: None,
    )

    def execute(request):
        executed_tools.append(request.call.name)
        return SimpleNamespace(
            elapsed_ms=1.0,
            result=SimpleNamespace(
                tool_name=request.call.name,
                call=AgentToolCallRecord(
                    tool_name=request.call.name,
                    input_summary=request.call.name,
                    output_summary="ok",
                    succeeded=True,
                ),
                search_results=["result"],
                sources=["source"],
            ),
        )

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=SimpleNamespace(execute=execute),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: SimpleNamespace(action="answer")),
        final_answers=SimpleNamespace(generate=lambda _: SimpleNamespace(result="final-result")),
        final_request_builder=lambda *args: "final-request",
    )
    request = _request_with_trace(LatencyTrace())
    request = replace(request, question="请展示相关图片证据")

    assert coordinator.run(request) == "final-result"
    assert executed_tools == ["search_figures"]
    assert request.latency_trace.values["runtime_tool_sequence_optimized"] is True


def test_coordinator_uses_existing_checkpoint_run_for_explicit_resume_id() -> None:
    calls: list[str] = []
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
        )
    )

    class ResumableCheckpoints:
        def resume(self, request, planning_decision):
            assert request.resume_run_id == "run-existing"
            assert planning_decision.canonical_task == "任务"
            calls.append("checkpoint_resume")
            return "run-existing"

        def start(self, *_args):
            raise AssertionError("explicit resume id must not create a fresh run")

        def persist_state(self, _run, **kwargs):
            calls.append(f"checkpoint_{kwargs['node']}")

        def completed_tool_ids(self, _run):
            return frozenset()

        def complete(self, _run, _outcome):
            calls.append("checkpoint_complete")

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=ResumableCheckpoints(),
        tool_executor=SimpleNamespace(
            execute=lambda _: calls.append("execute")
            or SimpleNamespace(result=SimpleNamespace(sources=["source"]))
        ),
        evidence_machine=SimpleNamespace(
            evaluate=lambda **_: calls.append("evidence")
            or SimpleNamespace(action="answer")
        ),
        final_answers=SimpleNamespace(
            generate=lambda _: calls.append("finalize")
            or SimpleNamespace(result="final-result")
        ),
        final_request_builder=lambda *args: "final-request",
    )

    result = coordinator.run(
        CoordinatorRequest(
            question="问题",
            budget=RunBudget(max_tool_calls=1, max_iterations=1),
            history=(),
            event_sink=None,
            conversation_id=5,
            resume_policy="force",
            resume_run_id="run-existing",
            image_path=None,
            latency_trace=LatencyTrace(),
        )
    )

    assert result == "final-result"
    assert calls == [
        "checkpoint_resume",
        "execute",
        "checkpoint_tool_execution_completed",
        "evidence",
        "finalize",
        "checkpoint_final_answer_completed",
        "checkpoint_complete",
    ]


def test_coordinator_accumulates_completed_tool_ids_across_escalation_checkpoints() -> None:
    persisted_tool_states: list[dict[str, object]] = []

    class AccumulatingCheckpoints:
        def __init__(self) -> None:
            self.state: dict[str, object] = {}

        def start(self, *_args):
            return "run-1"

        def persist_state(self, _run, *, node, state, status="running"):
            del status
            if node == "tool_execution_completed":
                persisted_tool_states.append(dict(state))
                self.state = dict(state)

        def completed_tool_ids(self, _run):
            return frozenset(self.state.get("completed_tool_ids", []))

        def complete(self, *_args):
            return None

    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="初始",
        ),
        escalate_fast_route=lambda *_: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="升级",
        ),
    )

    def execute(request):
        return SimpleNamespace(
            result=SimpleNamespace(
                call=AgentToolCallRecord(
                    tool_name="hybrid_search_knowledge",
                    input_summary="query",
                    output_summary="selected=1",
                    succeeded=True,
                    step_id=request.call.id,
                ),
                search_results=["search-result"],
            )
        )

    decisions = iter((SimpleNamespace(action="escalate"), SimpleNamespace(action="answer")))
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=AccumulatingCheckpoints(),
        tool_executor=SimpleNamespace(execute=execute),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: next(decisions)),
        final_answers=SimpleNamespace(generate=lambda _: SimpleNamespace(result="final-result")),
        final_request_builder=lambda *args: "final-request",
    )

    assert coordinator.run(_request()) == "final-result"
    assert persisted_tool_states[0]["completed_tool_ids"] == ["runtime-retrieval-1"]
    assert persisted_tool_states[1]["completed_tool_ids"] == [
        "runtime-retrieval-1",
        "runtime-retrieval-2",
    ]


def test_coordinator_binds_runtime_context_during_tool_execution() -> None:
    observed: dict[str, object] = {}
    trace = LatencyTrace()
    retrieval_plan = SimpleNamespace(schema="test-plan")
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
            plan=retrieval_plan,
            route=SimpleNamespace(kind="complex"),
        )
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: "run-1",
        persist_state=lambda *_args, **_kwargs: None,
        complete=lambda *_: None,
    )

    def execute(_request):
        observed["trace"] = get_current_latency_trace()
        observed["retrieval_plan"] = current_retrieval_plan()
        observed["route_kind"] = current_phase64_route_kind()
        return SimpleNamespace(result="tool-result")

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=SimpleNamespace(execute=execute),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: SimpleNamespace(action="answer")),
        final_answers=SimpleNamespace(generate=lambda _: SimpleNamespace(result="final-result")),
        final_request_builder=lambda *args: "final-request",
    )

    assert coordinator.run(_request_with_trace(trace)) == "final-result"
    assert observed == {
        "trace": trace,
        "retrieval_plan": retrieval_plan,
        "route_kind": "complex",
    }
    assert get_current_latency_trace() is None
    assert current_retrieval_plan() is None
    assert current_phase64_route_kind() == "legacy"


def test_coordinator_binds_hyde_vector_query_during_tool_execution() -> None:
    observed: dict[str, object] = {}
    trace = LatencyTrace()
    hyde_query = "任务\n\nHypothetical evidence for vector retrieval only:\n裂缝 缝隙 界面缺陷"
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
            plan=None,
            route=SimpleNamespace(kind="complex"),
        )
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: "run-1",
        persist_state=lambda *_args, **_kwargs: None,
        complete=lambda *_: None,
    )

    def execute(_request):
        observed["hyde_query"] = current_hyde_vector_query()
        return SimpleNamespace(result="tool-result")

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=SimpleNamespace(execute=execute),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: SimpleNamespace(action="answer")),
        final_answers=SimpleNamespace(generate=lambda _: SimpleNamespace(result="final-result")),
        final_request_builder=lambda *args: "final-request",
        hyde_query_builder=lambda _request, _planning: hyde_query,
    )

    assert coordinator.run(_request_with_trace(trace)) == "final-result"
    assert observed["hyde_query"] == hyde_query
    assert current_hyde_vector_query() == ""


def test_coordinator_refreshes_runtime_context_after_escalation() -> None:
    observed: list[tuple[object | None, str]] = []
    initial_plan = SimpleNamespace(schema="fast-plan")
    escalated_plan = SimpleNamespace(schema="complex-plan")
    initial = SimpleNamespace(
        action=SimpleNamespace(required_tool=None, forbidden_tools=()),
        canonical_task="初始",
        plan=initial_plan,
        route=SimpleNamespace(kind="fast"),
    )
    escalated = SimpleNamespace(
        action=SimpleNamespace(required_tool=None, forbidden_tools=()),
        canonical_task="升级",
        plan=escalated_plan,
        route=SimpleNamespace(kind="complex"),
    )
    planning = SimpleNamespace(
        plan=lambda _: initial,
        escalate_fast_route=lambda *_: escalated,
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: "run-1",
        persist_state=lambda *_args, **_kwargs: None,
        complete=lambda *_: None,
    )

    def execute(_request):
        observed.append((current_retrieval_plan(), current_phase64_route_kind()))
        return SimpleNamespace(result="tool-result")

    decisions = iter((SimpleNamespace(action="escalate"), SimpleNamespace(action="answer")))
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=SimpleNamespace(execute=execute),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: next(decisions)),
        final_answers=SimpleNamespace(generate=lambda _: SimpleNamespace(result="final-result")),
        final_request_builder=lambda *args: "final-request",
    )

    assert coordinator.run(_request()) == "final-result"
    assert observed == [(initial_plan, "fast"), (escalated_plan, "complex")]
    assert current_retrieval_plan() is None
    assert current_phase64_route_kind() == "legacy"


def test_coordinator_final_event_uses_escalated_iteration() -> None:
    events: list[RuntimeEvent] = []
    event_bus = RuntimeEventBus(run_id="test")
    event_bus.subscribe(events.append)
    initial = SimpleNamespace(
        action=SimpleNamespace(required_tool=None, forbidden_tools=()),
        canonical_task="初始",
    )
    escalated = SimpleNamespace(
        action=SimpleNamespace(required_tool=None, forbidden_tools=()),
        canonical_task="升级",
    )
    planning = SimpleNamespace(
        plan=lambda _: initial,
        escalate_fast_route=lambda *_: escalated,
    )
    decisions = iter((SimpleNamespace(action="escalate"), SimpleNamespace(action="answer")))
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=SimpleNamespace(start=lambda *_: "run-1", complete=lambda *_: None),
        tool_executor=SimpleNamespace(execute=lambda _: SimpleNamespace(result="tool-result")),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: next(decisions)),
        final_answers=SimpleNamespace(
            generate=lambda _: SimpleNamespace(result="final-result", stop_reason="completed")
        ),
        final_request_builder=lambda *args: "final-request",
    )

    assert coordinator.run(_request_with_event_sink(event_bus)) == "final-result"

    final_events = [
        event
        for event in events
        if event.name == "agent_step"
        and str(event.payload.get("action", "")).startswith("final_")
    ]
    assert final_events
    assert final_events[-1].payload["iteration"] == 2


def test_coordinator_pre_tool_gate_can_return_before_tool_execution() -> None:
    calls: list[str] = []
    events: list[RuntimeEvent] = []
    event_bus = RuntimeEventBus(run_id="test")
    event_bus.subscribe(events.append)
    planning = SimpleNamespace(
        plan=lambda _: calls.append("plan")
        or SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
        )
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: calls.append("checkpoint_start") or "run-1",
        persist_state=lambda run, **kwargs: calls.append(f"checkpoint_{kwargs['node']}"),
        complete=lambda *_: calls.append("checkpoint_complete"),
    )
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=SimpleNamespace(
            execute=lambda _: (_ for _ in ()).throw(
                AssertionError("pre-tool gate must skip tool execution")
            )
        ),
        evidence_machine=SimpleNamespace(
            evaluate=lambda **_: (_ for _ in ()).throw(
                AssertionError("pre-tool gate must skip evidence evaluation")
            )
        ),
        final_answers=SimpleNamespace(),
        pre_tool_gate=lambda *_: calls.append("pre_tool_gate")
        or PreToolGateDecision(
            action="return",
            result="gate-result",
            stop_reason="invalid_request",
            final_decision="refuse",
            sanitized_detail="off_topic",
        ),
    )

    assert coordinator.run(_request()) == "gate-result"
    assert calls == [
        "plan",
        "checkpoint_start",
        "pre_tool_gate",
        "checkpoint_final_answer_refused",
        "checkpoint_complete",
    ]

    event_bus_request = _request_with_event_sink(event_bus)
    calls.clear()
    events.clear()
    assert coordinator.run(event_bus_request) == "gate-result"
    assert [event.name for event in events] == ["agent_step", "agent_step"]
    assert events[0].payload["action"] == "plan"
    assert events[1].payload == {
        "iteration": 0,
        "action": "final_refuse",
        "step_summary": "invalid_request",
    }


def test_coordinator_runs_post_preflight_gate_after_required_tool_success() -> None:
    calls: list[str] = []
    tool_call = AgentToolCallRecord(
        tool_name="search_tables",
        input_summary="query=任务",
        output_summary="selected=1",
        succeeded=True,
        step_id="runtime-retrieval-1",
    )
    planning = SimpleNamespace(
        plan=lambda _: calls.append("plan")
        or SimpleNamespace(
            action=SimpleNamespace(required_tool="search_tables", forbidden_tools=()),
            canonical_task="任务",
        )
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: calls.append("checkpoint_start") or "run-1",
        persist_state=lambda _run, **kwargs: calls.append(f"checkpoint_{kwargs['node']}"),
        complete=lambda *_: calls.append("checkpoint_complete"),
    )

    def post_gate(request, planning_decision, run):
        del request, planning_decision, run
        calls.append("post_preflight_gate")
        return PreToolGateDecision(
            action="return",
            result="post-gate-result",
            stop_reason="completed",
            final_decision="answer",
            sanitized_detail="runtime_resume_completed",
            citations=(1,),
        )

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=SimpleNamespace(
            execute=lambda _: calls.append("execute")
            or SimpleNamespace(
                result=SimpleNamespace(
                    call=tool_call,
                    search_results=["search-result"],
                    sources=["source"],
                )
            )
        ),
        evidence_machine=SimpleNamespace(
            evaluate=lambda **_: (_ for _ in ()).throw(
                AssertionError("post-preflight gate should short-circuit evidence")
            )
        ),
        final_answers=SimpleNamespace(),
        pre_tool_gate=lambda *_: calls.append("pre_tool_gate")
        or PreToolGateDecision(action="continue"),
        post_preflight_gate=post_gate,
    )

    assert coordinator.run(_request()) == "post-gate-result"
    assert calls == [
        "plan",
        "checkpoint_start",
        "pre_tool_gate",
        "execute",
        "checkpoint_tool_execution_completed",
        "post_preflight_gate",
        "checkpoint_final_answer_completed",
        "checkpoint_complete",
    ]


def test_coordinator_executes_runtime_tool_sequence_within_budget() -> None:
    executed: list[tuple[str, int]] = []
    final_requests: list[FinalAnswerRequest] = []
    calls: list[str] = []
    table_call = AgentToolCallRecord(
        tool_name="search_tables",
        input_summary="query=任务",
        output_summary="selected=1",
        succeeded=True,
        step_id="runtime-retrieval-1",
    )
    hybrid_call = AgentToolCallRecord(
        tool_name="hybrid_search_knowledge",
        input_summary="query=任务",
        output_summary="selected=1",
        succeeded=True,
        step_id="runtime-retrieval-2",
    )
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(
                required_tool=None,
                forbidden_tools=(),
                tool_sequence=("search_tables", "hybrid_search_knowledge"),
            ),
            canonical_task="任务",
            runtime_state=AgentRuntimeState(context=RuntimeContext(current_query="任务")),
            final_answer_strategy="structured_final_answer",
            prompt_budgets={},
        )
    )

    def execute(request):
        executed.append((request.call.name, request.iteration))
        call = table_call if request.call.name == "search_tables" else hybrid_call
        return SimpleNamespace(
            result=SimpleNamespace(
                call=call,
                search_results=[f"{request.call.name}-result"],
                sources=[f"{request.call.name}-source"],
            ),
            elapsed_ms=1.0,
            error_category=None,
        )

    def generate(final_request):
        final_requests.append(final_request)
        return SimpleNamespace(result="final-result", stop_reason="completed")

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=SimpleNamespace(
            start=lambda *_: "run-1",
            persist_state=lambda *_args, **_kwargs: calls.append("checkpoint_tool"),
            completed_tool_ids=lambda *_: frozenset(),
            complete=lambda *_: calls.append("checkpoint_complete"),
        ),
        tool_executor=SimpleNamespace(execute=execute),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: SimpleNamespace(action="answer")),
        final_answers=SimpleNamespace(generate=generate),
    )

    result = coordinator.run(
        CoordinatorRequest(
            question="问题",
            budget=RunBudget(max_tool_calls=2, max_iterations=2),
            history=(),
            event_sink=None,
            conversation_id=None,
            resume_policy="auto",
            resume_run_id=None,
            image_path=None,
            latency_trace=LatencyTrace(),
        )
    )

    assert result == "final-result"
    assert executed == [
        ("search_tables", 1),
        ("hybrid_search_knowledge", 2),
    ]
    assert len(final_requests) == 1
    assert final_requests[0].tool_calls == (table_call, hybrid_call)
    assert final_requests[0].workflow_steps == (table_call, hybrid_call)
    assert final_requests[0].search_results == (
        "search_tables-result",
        "hybrid_search_knowledge-result",
    )
    assert final_requests[0].sources == (
        "search_tables-source",
        "hybrid_search_knowledge-source",
    )
    assert calls.count("checkpoint_tool") == 3
    assert calls[-1] == "checkpoint_complete"


def test_coordinator_sequence_keeps_required_tool_missing_fail_closed() -> None:
    executed: list[str] = []
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(
                required_tool="search_figures",
                forbidden_tools=(),
                tool_sequence=("search_figures", "hybrid_search_knowledge"),
            ),
            canonical_task="任务",
            runtime_state=AgentRuntimeState(context=RuntimeContext(current_query="任务")),
            final_answer_strategy="structured_final_answer",
            prompt_budgets={},
        )
    )

    def execute(request):
        executed.append(request.call.name)
        if request.call.name == "search_figures":
            return SimpleNamespace(
                result=SimpleNamespace(
                    tool_name="search_figures",
                    call=AgentToolCallRecord(
                        tool_name="search_figures",
                        input_summary="query=任务",
                        output_summary="selected=0",
                        succeeded=True,
                        step_id=request.call.id,
                    ),
                    search_results=[],
                    sources=[],
                ),
                elapsed_ms=1.0,
                error_category=None,
            )
        return SimpleNamespace(
            result=SimpleNamespace(
                tool_name="hybrid_search_knowledge",
                call=AgentToolCallRecord(
                    tool_name="hybrid_search_knowledge",
                    input_summary="query=任务",
                    output_summary="selected=1",
                    succeeded=True,
                    step_id=request.call.id,
                ),
                search_results=["text-result"],
                sources=["text-source"],
            ),
            elapsed_ms=1.0,
            error_category=None,
        )

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=SimpleNamespace(
            start=lambda *_: "run-1",
            persist_state=lambda *_args, **_kwargs: None,
            completed_tool_ids=lambda *_: frozenset(),
            complete=lambda *_: None,
        ),
        tool_executor=SimpleNamespace(execute=execute),
        evidence_machine=EvidenceStateMachine,
        final_answers=SimpleNamespace(
            generate=lambda _: (_ for _ in ()).throw(AssertionError("must not answer")),
            refuse=lambda _: SimpleNamespace(result="refused-result"),
        ),
    )

    assert coordinator.run(_request()) == "refused-result"
    assert executed == ["search_figures", "hybrid_search_knowledge"]


def test_coordinator_uploaded_image_plus_knowledge_runs_image_then_hybrid() -> None:
    executed: list[str] = []
    final_requests: list[FinalAnswerRequest] = []
    image_call = AgentToolCallRecord(
        tool_name="analyze_user_image",
        input_summary="image_path=<user_upload>",
        output_summary="image described",
        succeeded=True,
        step_id="runtime-retrieval-1",
    )
    hybrid_call = AgentToolCallRecord(
        tool_name="hybrid_search_knowledge",
        input_summary="query=任务",
        output_summary="selected=1",
        succeeded=True,
        step_id="runtime-retrieval-2",
    )
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=(), tool_sequence=()),
            canonical_task="任务",
            runtime_state=AgentRuntimeState(context=RuntimeContext(current_query="任务")),
        )
    )

    def execute(request):
        executed.append(request.call.name)
        if request.call.name == "analyze_user_image":
            return SimpleNamespace(
                result=SimpleNamespace(
                    tool_name="analyze_user_image",
                    call=image_call,
                    answer="图片显示堆石混凝土相关现象。",
                    search_results=[],
                    sources=[],
                ),
                elapsed_ms=1.0,
                error_category=None,
            )
        return SimpleNamespace(
            result=SimpleNamespace(
                tool_name="hybrid_search_knowledge",
                call=hybrid_call,
                search_results=["text-result"],
                sources=["text-source"],
            ),
            elapsed_ms=1.0,
            error_category=None,
        )

    def generate(request: FinalAnswerRequest):
        final_requests.append(request)
        return SimpleNamespace(result="final-result", citations=(1,), stop_reason="completed")

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=SimpleNamespace(
            start=lambda *_: "run-1",
            persist_state=lambda *_args, **_kwargs: None,
            completed_tool_ids=lambda *_: frozenset(),
            complete=lambda *_: None,
        ),
        tool_executor=SimpleNamespace(execute=execute),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: SimpleNamespace(action="answer")),
        final_answers=SimpleNamespace(generate=generate),
    )
    request = replace(
        _request(),
        question="请结合知识库判断这张图是否能支撑 RFC 施工或质量问题。",
        image_path="uploads/user/image.png",
        budget=RunBudget(max_tool_calls=2, max_iterations=2),
    )

    assert coordinator.run(request) == "final-result"
    assert executed == ["analyze_user_image", "hybrid_search_knowledge"]
    assert final_requests
    assert final_requests[0].tool_calls == (image_call, hybrid_call)
    assert final_requests[0].sources == ("text-source",)


def test_coordinator_uploaded_image_plus_figure_lookup_runs_image_then_figures() -> None:
    executed: list[str] = []
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=(), tool_sequence=()),
            canonical_task="任务",
            runtime_state=AgentRuntimeState(context=RuntimeContext(current_query="任务")),
        )
    )

    def execute(request):
        executed.append(request.call.name)
        if request.call.name == "analyze_user_image":
            return SimpleNamespace(
                result=SimpleNamespace(
                    tool_name="analyze_user_image",
                    call=AgentToolCallRecord(
                        tool_name="analyze_user_image",
                        input_summary="image_path=<user_upload>",
                        output_summary="image described",
                        succeeded=True,
                        step_id=request.call.id,
                    ),
                    answer="图片描述。",
                    search_results=[],
                    sources=[],
                ),
                elapsed_ms=1.0,
                error_category=None,
            )
        return SimpleNamespace(
            result=SimpleNamespace(
                tool_name="search_figures",
                call=AgentToolCallRecord(
                    tool_name="search_figures",
                    input_summary="query=任务",
                    output_summary="selected=1",
                    succeeded=True,
                    step_id=request.call.id,
                ),
                search_results=["figure-result"],
                sources=["figure-source"],
                figure_results=["figure-result"],
            ),
            elapsed_ms=1.0,
            error_category=None,
        )

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=SimpleNamespace(
            start=lambda *_: "run-1",
            persist_state=lambda *_args, **_kwargs: None,
            completed_tool_ids=lambda *_: frozenset(),
            complete=lambda *_: None,
        ),
        tool_executor=SimpleNamespace(execute=execute),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: SimpleNamespace(action="answer")),
        final_answers=SimpleNamespace(
            generate=lambda _: SimpleNamespace(result="final-result", citations=(1,), stop_reason="completed")
        ),
    )
    request = replace(
        _request(),
        question="请寻找与这张图相似或相关的资料图片证据。",
        image_path="uploads/user/image.png",
        budget=RunBudget(max_tool_calls=2, max_iterations=2),
    )

    assert coordinator.run(request) == "final-result"
    assert executed == ["analyze_user_image", "search_figures"]


def test_coordinator_event_sink_accepts_runtime_event_callable() -> None:
    events: list[RuntimeEvent] = []
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
        )
    )
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=SimpleNamespace(start=lambda *_: "run-1", complete=lambda *_: None),
        tool_executor=SimpleNamespace(execute=lambda _: SimpleNamespace(result="tool-result")),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: SimpleNamespace(action="answer")),
        final_answers=SimpleNamespace(
            generate=lambda _: SimpleNamespace(result="final-result", stop_reason="completed")
        ),
        final_request_builder=lambda *args: "final-request",
    )

    request = CoordinatorRequest(
        question="问题",
        budget=RunBudget(max_tool_calls=1, max_iterations=1),
        history=(),
        event_sink=events.append,
        conversation_id=None,
        resume_policy="auto",
        resume_run_id=None,
        image_path=None,
        latency_trace=LatencyTrace(),
    )

    assert coordinator.run(request) == "final-result"
    assert [event.name for event in events] == ["agent_step", "agent_step", "agent_step"]
    assert all(event.stage == "planning" for event in events)
    assert events[-1].payload == {
        "iteration": 1,
        "action": "final_answer",
        "step_summary": "completed",
    }


def test_coordinator_fails_closed_when_a_second_escalation_is_requested() -> None:
    calls: list[str] = []
    decision = SimpleNamespace(action=SimpleNamespace(required_tool=None, forbidden_tools=()), canonical_task="任务")
    planning = SimpleNamespace(plan=lambda _: decision, escalate_fast_route=lambda *_: decision)
    checkpoints = SimpleNamespace(start=lambda *_: "run-1", complete=lambda *_: calls.append("complete"))
    executor = SimpleNamespace(execute=lambda _: SimpleNamespace(result="tool-result"))
    evidence = SimpleNamespace(evaluate=lambda **_: SimpleNamespace(action="escalate"))
    finals = SimpleNamespace(
        generate=lambda _: (_ for _ in ()).throw(AssertionError("must not generate")),
        refuse=lambda _: calls.append("refuse") or SimpleNamespace(result="refused-result"),
    )
    coordinator = RunCoordinator(
        planning_policy=planning, checkpoints=checkpoints, tool_executor=executor,
        evidence_machine=evidence, final_answers=finals,
        final_request_builder=lambda *args: "final-request",
    )

    assert coordinator.run(_request()) == "refused-result"
    assert calls == ["refuse", "complete"]


def test_coordinator_refuses_when_escalation_exceeds_tool_budget() -> None:
    calls: list[str] = []
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
        ),
        escalate_fast_route=lambda *_: (_ for _ in ()).throw(
            AssertionError("coordinator must not escalate after tool budget is exhausted")
        ),
    )
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=SimpleNamespace(
            start=lambda *_: "run-1",
            complete=lambda *_: calls.append("complete"),
        ),
        tool_executor=SimpleNamespace(
            execute=lambda _: calls.append("execute")
            or SimpleNamespace(result="tool-result")
        ),
        evidence_machine=SimpleNamespace(
            evaluate=lambda **_: SimpleNamespace(
                action="escalate",
                sanitized_detail="single_escalation",
            )
        ),
        final_answers=SimpleNamespace(
            generate=lambda _: (_ for _ in ()).throw(AssertionError("must not generate")),
            refuse=lambda _: calls.append("refuse") or SimpleNamespace(result="refused-result"),
        ),
        final_request_builder=lambda *args: "final-request",
    )

    request = CoordinatorRequest(
        question="问题",
        budget=RunBudget(max_tool_calls=1, max_iterations=1),
        history=(),
        event_sink=None,
        conversation_id=None,
        resume_policy="auto",
        resume_run_id=None,
        image_path=None,
        latency_trace=LatencyTrace(),
    )

    assert coordinator.run(request) == "refused-result"
    assert calls == ["execute", "refuse", "complete"]


def test_coordinator_refuses_completed_tool_replay_without_escalation() -> None:
    calls: list[str] = []
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
            escalation_count=0,
        ),
        escalate_fast_route=lambda *_: (_ for _ in ()).throw(
            AssertionError("completed tool replay must not escalate")
        ),
    )
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=SimpleNamespace(
            start=lambda *_: "run-1",
            complete=lambda *_: calls.append("complete"),
        ),
        tool_executor=SimpleNamespace(
            execute=lambda _: calls.append("execute")
            or SimpleNamespace(
                result=SimpleNamespace(sources=[]),
                error_category="completed_tool",
                skipped_completed_tool=True,
            )
        ),
        evidence_machine=EvidenceStateMachine,
        final_answers=SimpleNamespace(
            generate=lambda _: (_ for _ in ()).throw(AssertionError("must not generate")),
            refuse=lambda _: calls.append("refuse") or SimpleNamespace(result="refused-result"),
        ),
        final_request_builder=lambda *args: "final-request",
    )

    assert coordinator.run(_request()) == "refused-result"
    assert calls == ["execute", "refuse", "complete"]


def test_coordinator_persists_refusal_before_completion_when_supported() -> None:
    calls: list[str] = []
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
        )
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: calls.append("checkpoint_start") or "run-1",
        persist_state=lambda run, **kwargs: calls.append(f"checkpoint_{kwargs['node']}"),
        complete=lambda *_: calls.append("checkpoint_complete"),
    )
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=SimpleNamespace(execute=lambda _: SimpleNamespace(result="tool-result")),
        evidence_machine=SimpleNamespace(
            evaluate=lambda **_: SimpleNamespace(
                action="refuse",
                stop_reason="insufficient_evidence",
                sanitized_detail="evidence_exhausted",
            )
        ),
        final_answers=SimpleNamespace(
            refuse=lambda _: calls.append("refuse") or SimpleNamespace(result="refused-result")
        ),
        final_request_builder=lambda *args: "final-request",
    )

    assert coordinator.run(_request()) == "refused-result"
    assert calls == [
        "checkpoint_start",
        "checkpoint_tool_execution_completed",
        "refuse",
        "checkpoint_final_answer_refused",
        "checkpoint_complete",
    ]


def test_coordinator_final_refusal_checkpoint_keeps_safe_detail() -> None:
    persisted: list[dict[str, object]] = []
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
        )
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: "run-1",
        persist_state=lambda _run, **kwargs: persisted.append(kwargs),
        complete=lambda *_: None,
    )
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=SimpleNamespace(execute=lambda _: SimpleNamespace(result="tool-result")),
        evidence_machine=SimpleNamespace(
            evaluate=lambda **_: SimpleNamespace(
                action="refuse",
                stop_reason="insufficient_evidence",
                sanitized_detail="reranking_failed",
            )
        ),
        final_answers=SimpleNamespace(
            refuse=lambda _: SimpleNamespace(
                result="refused-result",
                stop_reason="insufficient_evidence",
                citations=(),
            )
        ),
        final_request_builder=lambda *args: "final-request",
    )

    assert coordinator.run(_request()) == "refused-result"
    final_state = [
        item["state"]
        for item in persisted
        if item["node"] == "final_answer_refused"
    ][0]
    assert final_state == {
        "final_action": "refuse",
        "stop_reason": "insufficient_evidence",
        "evidence_detail": "reranking_failed",
        "citation_count": 0,
        "citation_repair_count": 0,
    }


def test_coordinator_does_not_escalate_after_deadline_exhaustion() -> None:
    calls: list[str] = []
    decision = SimpleNamespace(
        action=SimpleNamespace(required_tool=None, forbidden_tools=()),
        canonical_task="任务",
        escalation_count=0,
    )
    planning = SimpleNamespace(
        plan=lambda _: decision,
        escalate_fast_route=lambda *_: (_ for _ in ()).throw(
            AssertionError("deadline exhaustion must not escalate")
        ),
    )
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=SimpleNamespace(start=lambda *_: "run-1", complete=lambda *_: calls.append("complete")),
        tool_executor=SimpleNamespace(
            execute=lambda _: SimpleNamespace(
                result=SimpleNamespace(sources=[]),
                error_category="deadline_exhausted",
            )
        ),
        evidence_machine=EvidenceStateMachine,
        final_answers=SimpleNamespace(
            generate=lambda _: (_ for _ in ()).throw(AssertionError("must not generate")),
            refuse=lambda _: calls.append("refuse") or SimpleNamespace(result="refused-result"),
        ),
        final_request_builder=lambda *args: "final-request",
    )

    assert coordinator.run(_request(deadline_monotonic=1.0)) == "refused-result"
    assert calls == ["refuse", "complete"]


def test_coordinator_preserves_refusal_detail_on_final_request_runtime_state() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="任务"))
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
            runtime_state=runtime_state,
        )
    )

    def refuse(final_request):
        assert final_request.runtime_state.stop_reason == "reranking_failed"
        assert final_request.runtime_state.normalized_stop_reason == "insufficient_evidence"
        assert final_request.runtime_state.final_decision == "refuse"
        return SimpleNamespace(result="refused-result", stop_reason="insufficient_evidence")

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=SimpleNamespace(start=lambda *_: "run-1", complete=lambda *_: None),
        tool_executor=SimpleNamespace(execute=lambda _: SimpleNamespace(result="tool-result")),
        evidence_machine=SimpleNamespace(
            evaluate=lambda **_: SimpleNamespace(
                action="refuse",
                stop_reason="insufficient_evidence",
                sanitized_detail="reranking_failed",
            )
        ),
        final_answers=SimpleNamespace(refuse=refuse),
        final_request_builder=lambda request, planning, tool_outcome, evidence: SimpleNamespace(
            runtime_state=runtime_state
        ),
    )

    assert coordinator.run(_request()) == "refused-result"


def test_coordinator_builds_standard_final_answer_request_by_default() -> None:
    runtime_state = SimpleNamespace()
    emitted_tokens: list[str] = []
    token_emitter = emitted_tokens.append
    tool_call = AgentToolCallRecord(
        tool_name="hybrid_search_knowledge",
        input_summary="query=任务",
        output_summary="selected=1",
        succeeded=True,
        step_id="runtime-retrieval-1",
    )
    planning = SimpleNamespace(
        plan=lambda _: SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="任务",
            runtime_state=runtime_state,
            final_answer_strategy="baseline",
            prompt_budgets={"max_context_chars": 100},
        )
    )

    def generate(final_request):
        assert isinstance(final_request, FinalAnswerRequest)
        assert final_request.question == "问题"
        assert final_request.history == ("历史",)
        assert final_request.strategy == "baseline"
        assert final_request.search_results == ("search-result",)
        assert final_request.sources == ("source",)
        assert final_request.tool_calls == (tool_call,)
        assert final_request.workflow_steps == (tool_call,)
        assert final_request.runtime_state is runtime_state
        assert final_request.prompt_budgets == {"max_context_chars": 100}
        assert final_request.token_emitter is token_emitter
        return SimpleNamespace(result="final-result")

    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=SimpleNamespace(start=lambda *_: "run-1", complete=lambda *_: None),
        tool_executor=SimpleNamespace(
            execute=lambda _: SimpleNamespace(
                result=SimpleNamespace(
                    search_results=["search-result"],
                    sources=["source"],
                    call=tool_call,
                )
            )
        ),
        evidence_machine=SimpleNamespace(evaluate=lambda **_: SimpleNamespace(action="answer")),
        final_answers=SimpleNamespace(generate=generate),
    )

    request = CoordinatorRequest(
        question="问题",
        budget=RunBudget(max_tool_calls=1, max_iterations=1),
        history=("历史",),
        event_sink=None,
        conversation_id=None,
        resume_policy="auto",
        resume_run_id=None,
        image_path=None,
        latency_trace=LatencyTrace(),
        token_emitter=token_emitter,
    )

    assert coordinator.run(request) == "final-result"


def _request(deadline_monotonic: float | None = None) -> CoordinatorRequest:
    return CoordinatorRequest(
        question="问题", budget=RunBudget(max_tool_calls=2, max_iterations=2, deadline_monotonic=deadline_monotonic), history=(),
        event_sink=None, conversation_id=None, resume_policy="auto", resume_run_id=None,
        image_path=None, latency_trace=LatencyTrace(),
    )


def _request_with_trace(trace: LatencyTrace) -> CoordinatorRequest:
    return CoordinatorRequest(
        question="问题",
        budget=RunBudget(max_tool_calls=2, max_iterations=2),
        history=(),
        event_sink=None,
        conversation_id=None,
        resume_policy="auto",
        resume_run_id=None,
        image_path=None,
        latency_trace=trace,
    )


def _request_with_event_sink(event_sink) -> CoordinatorRequest:
    return CoordinatorRequest(
        question="问题",
        budget=RunBudget(max_tool_calls=2, max_iterations=2),
        history=(),
        event_sink=event_sink,
        conversation_id=None,
        resume_policy="auto",
        resume_run_id=None,
        image_path=None,
        latency_trace=LatencyTrace(),
    )
