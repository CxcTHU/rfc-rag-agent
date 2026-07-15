"""Lifecycle composition root for the modular Agent Runtime."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from app.services.agent.planning_policy import PlanningRequest
from app.services.agent.runtime_contracts import (
    CoordinatorRequest,
    FinalAnswerRequest,
    FinalAnswerOutcome,
    RuntimeStopReason,
    PreToolGateDecision,
    ToolExecutionRequest,
    ToolCallingFinalAnswerStrategy,
)
from app.services.generation.chat_model import ChatToolCall
from app.services.observability.latency_trace import (
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.agent.runtime_events import (
    RuntimeEvent,
    RuntimeEventName,
    sanitize_event_payload,
)
from app.services.retrieval.route_context import (
    reset_phase64_route_kind,
    set_phase64_route_kind,
)
from app.services.retrieval.runtime import (
    reset_current_retrieval_plan,
    retrieval_tool_for_action,
    set_current_retrieval_plan,
)
from app.services.retrieval.hybrid_search import (
    reset_current_hyde_vector_query,
    set_current_hyde_vector_query,
)


def _safe_tool_checkpoint_state(outcome: Any) -> dict[str, object]:
    result = getattr(outcome, "result", None)
    call = getattr(result, "call", None)
    tool_name = str(
        getattr(result, "tool_name", None)
        or getattr(call, "tool_name", None)
        or getattr(call, "name", None)
        or ""
    )[:80]
    step_id = str(
        getattr(call, "step_id", None)
        or getattr(call, "id", None)
        or tool_name
        or ""
    )[:80]
    search_results = getattr(result, "search_results", None)
    selected_count = len(search_results) if isinstance(search_results, list | tuple) else 0
    succeeded = getattr(call, "succeeded", None)
    state: dict[str, object] = {
        "completed_tool_ids": [step_id] if step_id else [],
        "tool_name": tool_name,
        "selected_count": selected_count,
    }
    if succeeded is not None:
        state["succeeded"] = bool(succeeded)
    return state


def _persist_tool_checkpoint(checkpoints: Any, run: Any, outcome: Any) -> None:
    persist_state = getattr(checkpoints, "persist_state", None)
    if not callable(persist_state):
        return
    state = _safe_tool_checkpoint_state(outcome)
    merged_completed_tool_ids = sorted(_completed_tool_ids(checkpoints, run))
    for step_id in state.get("completed_tool_ids", []):
        step_id_text = str(step_id)[:120]
        if step_id_text and step_id_text not in merged_completed_tool_ids:
            merged_completed_tool_ids.append(step_id_text)
    state["completed_tool_ids"] = merged_completed_tool_ids[:20]
    persist_state(
        run,
        node="tool_execution_completed",
        state=state,
        status="running",
    )


def _completed_tool_ids(checkpoints: Any, run: Any) -> frozenset[str]:
    completed_tool_ids = getattr(checkpoints, "completed_tool_ids", None)
    if not callable(completed_tool_ids):
        return frozenset()
    values = completed_tool_ids(run)
    if isinstance(values, frozenset):
        return values
    if isinstance(values, set | list | tuple):
        return frozenset(str(value)[:120] for value in values if str(value).strip())
    return frozenset()


def _start_or_resume_checkpoint(checkpoints: Any, request: Any, planning: Any) -> Any:
    resume_run_id = str(getattr(request, "resume_run_id", "") or "").strip()
    resume = getattr(checkpoints, "resume", None)
    if resume_run_id and callable(resume):
        return resume(request, planning)
    return checkpoints.start(request, planning)


def _persist_final_checkpoint(
    checkpoints: Any,
    run: Any,
    *,
    evidence: Any,
    final_outcome: Any,
) -> None:
    persist_state = getattr(checkpoints, "persist_state", None)
    if not callable(persist_state):
        return
    action = str(getattr(evidence, "action", "refuse") or "refuse")
    node = "final_answer_completed" if action == "answer" else "final_answer_refused"
    stop_reason = str(
        getattr(final_outcome, "stop_reason", None)
        or getattr(evidence, "stop_reason", None)
        or ("completed" if action == "answer" else "insufficient_evidence")
    )[:80]
    persist_state(
        run,
        node=node,
        state={
            "final_action": action[:40],
            "stop_reason": stop_reason,
            "evidence_detail": str(getattr(evidence, "sanitized_detail", ""))[:120],
            "citation_count": len(getattr(final_outcome, "citations", ()) or ()),
            "citation_repair_count": int(
                getattr(final_outcome, "citation_repair_count", 0) or 0
            ),
        },
        status="completed" if action == "answer" else "failed",
    )


def _normalize_final_outcome(value: Any, evidence: Any) -> FinalAnswerOutcome:
    if isinstance(value, FinalAnswerOutcome):
        return value
    action = str(getattr(evidence, "action", "refuse") or "refuse")
    default_stop_reason: RuntimeStopReason = (
        "completed" if action == "answer" else "insufficient_evidence"
    )
    stop_reason = getattr(value, "stop_reason", None) or getattr(
        evidence, "stop_reason", None
    ) or default_stop_reason
    if stop_reason not in RuntimeStopReason.__args__:
        stop_reason = default_stop_reason
    return FinalAnswerOutcome(
        result=getattr(value, "result", value),
        citations=tuple(getattr(value, "citations", ()) or ()),
        citation_repair_count=max(0, int(getattr(value, "citation_repair_count", 0) or 0)),
        stop_reason=stop_reason,
    )


def _pre_tool_gate_final_outcome(decision: PreToolGateDecision) -> FinalAnswerOutcome:
    if decision.result is None:
        raise ValueError("pre-tool gate return decision requires a result")
    return FinalAnswerOutcome(
        result=decision.result,
        citations=tuple(decision.citations),
        citation_repair_count=max(0, int(decision.citation_repair_count)),
        stop_reason=decision.stop_reason,
    )


def _record_tool_outcome_for_gate(gate: Any, outcome: Any) -> None:
    """Expose a completed preflight tool call to legacy-compatible gate adapters."""
    result = getattr(outcome, "result", None)
    call = getattr(result, "call", None)
    if call is None:
        return
    for attr in ("workflow_steps", "tool_calls"):
        records = getattr(gate, attr, None)
        if not isinstance(records, list):
            continue
        step_id = getattr(call, "step_id", None)
        if step_id and any(getattr(item, "step_id", None) == step_id for item in records):
            continue
        records.append(call)


def _apply_refusal_runtime_state(final_request: Any, evidence: Any) -> None:
    runtime_state = getattr(final_request, "runtime_state", None)
    set_stop_reason = getattr(runtime_state, "set_stop_reason", None)
    if not callable(set_stop_reason):
        return
    action = str(getattr(evidence, "action", "refuse") or "refuse")
    stop_reason = str(getattr(evidence, "stop_reason", "") or "")
    sanitized_detail = str(getattr(evidence, "sanitized_detail", "") or "")
    if action == "refuse":
        detail = sanitized_detail or stop_reason or "insufficient_evidence"
    else:
        detail = stop_reason or "insufficient_evidence"
    set_stop_reason(detail)
    if hasattr(runtime_state, "final_decision"):
        runtime_state.final_decision = "refuse"


def _emit_runtime_event(
    sink: Any,
    *,
    stage: str,
    name: RuntimeEventName,
    payload: dict[str, object],
) -> None:
    emit = getattr(sink, "emit", None)
    if callable(emit):
        emit(stage, name, payload)
        return
    if callable(sink):
        sink(
            RuntimeEvent(
                run_id="",
                sequence=0,
                stage=stage,
                name=name,
                elapsed_ms=0.0,
                payload=sanitize_event_payload(name, payload),
            )
        )


def _emit_agent_step(
    request: CoordinatorRequest,
    *,
    iteration: int,
    action: str,
    step_summary: str,
) -> None:
    _emit_runtime_event(
        request.event_sink,
        stage="planning",
        name="agent_step",
        payload={
            "iteration": max(0, int(iteration)),
            "action": action[:80],
            "step_summary": step_summary[:240],
        },
    )


def _emit_required_tool_legacy_result_alias(
    request: CoordinatorRequest,
    *,
    required_tool: str | None,
    outcome: Any,
) -> None:
    """Emit the legacy preflight step id without changing runtime checkpoint ids."""
    tool_name = str(required_tool or "")
    if tool_name not in {"search_tables", "search_figures"}:
        return
    result = getattr(outcome, "result", None)
    call = getattr(result, "call", None)
    if str(getattr(call, "tool_name", "") or "") != tool_name:
        return
    _emit_runtime_event(
        request.event_sink,
        stage="retrieval",
        name="tool_call_result",
        payload={
            "iteration": 1,
            "step_id": f"runtime-{tool_name}",
            "tool_name": tool_name,
            "observation_summary": str(getattr(call, "output_summary", ""))[:240],
            "succeeded": bool(getattr(call, "succeeded", False)),
            "skipped": False,
            "selected_count": len(getattr(result, "search_results", ()) or ()),
        },
    )


def _route_context_kind(planning: Any) -> str:
    route = getattr(planning, "route", None)
    if route is not None:
        kind = str(getattr(route, "kind", "") or "")
        if kind in {"fast", "complex"}:
            return kind
    return "legacy"


def _bind_hyde_vector_query(
    hyde_query_builder: Callable[[CoordinatorRequest, Any], str] | None,
    request: CoordinatorRequest,
    planning: Any,
) -> Any | None:
    if hyde_query_builder is None:
        return None
    hyde_query = str(hyde_query_builder(request, planning) or "").strip()
    if not hyde_query:
        return None
    return set_current_hyde_vector_query(hyde_query)


def _tool_sequence_for_planning(planning: Any) -> tuple[str, ...]:
    action = getattr(planning, "action", None)
    raw_sequence = getattr(action, "tool_sequence", None)
    allowed_tools = {"hybrid_search_knowledge", "search_figures", "search_tables"}
    if isinstance(raw_sequence, (list, tuple)):
        sequence = tuple(
            str(tool)
            for tool in raw_sequence
            if str(tool) in allowed_tools
        )
        if sequence:
            return tuple(dict.fromkeys(sequence))
    return (retrieval_tool_for_action(action),)


def _combine_tool_outcomes(outcomes: list[Any]) -> Any:
    if len(outcomes) == 1:
        return outcomes[0]
    calls: list[Any] = []
    search_results: list[Any] = []
    sources: list[Any] = []
    figure_results: list[Any] = []
    citations: list[int] = []
    tool_result_counts: dict[str, int] = {}
    elapsed_ms = 0.0
    error_category = None
    refusal_reason = None
    for outcome in outcomes:
        elapsed_ms += float(getattr(outcome, "elapsed_ms", 0.0) or 0.0)
        if error_category is None:
            error_category = getattr(outcome, "error_category", None)
        result = getattr(outcome, "result", None)
        if not refusal_reason:
            refusal_reason = getattr(result, "refusal_reason", None)
        tool_name = str(getattr(result, "tool_name", "") or "")
        call = getattr(result, "call", None)
        if call is not None:
            calls.append(call)
            tool_name = tool_name or str(getattr(call, "tool_name", "") or "")
        result_sources = list(getattr(result, "sources", ()) or ())
        search_results.extend(list(getattr(result, "search_results", ()) or ()))
        sources.extend(result_sources)
        figure_results.extend(list(getattr(result, "figure_results", ()) or ()))
        if tool_name:
            tool_result_counts[tool_name] = tool_result_counts.get(tool_name, 0) + len(
                result_sources
            )
        citations.extend(
            int(value)
            for value in (getattr(result, "citations", ()) or ())
            if isinstance(value, int)
        )
    last_result = getattr(outcomes[-1], "result", None)
    combined_result = SimpleNamespace(
        tool_name="runtime_multi_tool",
        call=calls[-1] if calls else getattr(last_result, "call", None),
        tool_calls=tuple(calls),
        workflow_steps=tuple(calls),
        search_results=search_results,
        sources=sources,
        tool_result_counts=tool_result_counts,
        figure_results=figure_results,
        citations=citations,
        refused=not bool(sources),
        refusal_reason=refusal_reason or getattr(last_result, "refusal_reason", None),
    )
    return SimpleNamespace(
        result=combined_result,
        elapsed_ms=elapsed_ms,
        error_category=error_category,
        skipped_completed_tool=any(
            bool(getattr(outcome, "skipped_completed_tool", False))
            for outcome in outcomes
        ),
    )


def _record_runtime_evidence(planning: Any, outcome: Any) -> None:
    runtime_state = getattr(planning, "runtime_state", None)
    evidence = getattr(runtime_state, "evidence", None)
    add = getattr(evidence, "add", None)
    if not callable(add):
        return
    result = getattr(outcome, "result", None)
    call = getattr(result, "call", None)
    tool_name = str(
        getattr(result, "tool_name", None) or getattr(call, "tool_name", "") or ""
    )
    if not tool_name:
        return
    add(
        tool_name=tool_name,
        query=str(getattr(planning, "canonical_task", "") or ""),
        result_count=len(getattr(result, "search_results", ()) or ()),
        succeeded=bool(getattr(call, "succeeded", False)),
    )


def _fast_route_insufficient_evidence(request: CoordinatorRequest, planning: Any, outcome: Any) -> bool:
    route = getattr(planning, "route", None)
    if str(getattr(route, "kind", "") or "") != "fast":
        return False
    result = getattr(outcome, "result", None)
    source_count = len(getattr(result, "sources", ()) or ())
    minimum = max(1, int(getattr(planning, "fast_path_min_selected_sources", 1) or 1))
    if source_count < minimum:
        request.latency_trace.set_value("phase64_fast_escalated", True)
        request.latency_trace.set_value(
            "phase64_fast_escalation_reason",
            "insufficient_selected_sources",
        )
        return True
    request.latency_trace.set_value("phase64_fast_escalated", False)
    request.latency_trace.set_value("phase64_fast_escalation_reason", "")
    return False


class RunCoordinator:
    def __init__(
        self,
        *,
        planning_policy: Any,
        checkpoints: Any,
        tool_executor: Any,
        evidence_machine: Any,
        final_answers: Any,
        final_request_builder: Callable[[Any, Any, Any, Any], Any] | None = None,
        pre_tool_gate: Callable[[CoordinatorRequest, Any, Any], PreToolGateDecision]
        | None = None,
        post_preflight_gate: Callable[[CoordinatorRequest, Any, Any], PreToolGateDecision]
        | None = None,
        hyde_query_builder: Callable[[CoordinatorRequest, Any], str] | None = None,
    ) -> None:
        self._planning_policy = planning_policy
        self._checkpoints = checkpoints
        self._tool_executor = tool_executor
        self._evidence_machine = evidence_machine
        self._final_answers = final_answers
        self._final_request_builder = final_request_builder or build_final_answer_request
        self._pre_tool_gate = pre_tool_gate
        self._post_preflight_gate = post_preflight_gate
        self._hyde_query_builder = hyde_query_builder

    def run(self, request: CoordinatorRequest) -> Any:
        latency_token = set_current_latency_trace(request.latency_trace)
        retrieval_token = None
        route_token = None
        hyde_token = None
        try:
            planning = self._planning_policy.plan(
                PlanningRequest(
                    question=request.question,
                    history=request.history,
                    image_path=request.image_path,
                    trace=request.latency_trace,
                )
            )
            _emit_agent_step(
                request,
                iteration=0,
                action="plan",
                step_summary=f"canonical_task={str(getattr(planning, 'canonical_task', ''))[:160]}",
            )
            retrieval_token = set_current_retrieval_plan(getattr(planning, "plan", None))
            route_token = set_phase64_route_kind(_route_context_kind(planning))
            run = _start_or_resume_checkpoint(self._checkpoints, request, planning)
            if self._pre_tool_gate is not None:
                gate_decision = self._pre_tool_gate(request, planning, run)
                if gate_decision.action == "return":
                    final_outcome = _pre_tool_gate_final_outcome(gate_decision)
                    _persist_final_checkpoint(
                        self._checkpoints,
                        run,
                        evidence=SimpleNamespace(
                            action=gate_decision.final_decision,
                            stop_reason=gate_decision.stop_reason,
                            sanitized_detail=gate_decision.sanitized_detail,
                        ),
                        final_outcome=final_outcome,
                    )
                    _emit_agent_step(
                        request,
                        iteration=0,
                        action=f"final_{gate_decision.final_decision}",
                        step_summary=gate_decision.stop_reason,
                    )
                    self._checkpoints.complete(run, final_outcome)
                    return final_outcome.result
            final_iteration = 1
            required_tool = getattr(getattr(planning, "action", None), "required_tool", None)
            if not str(required_tool or "").strip():
                hyde_token = _bind_hyde_vector_query(
                    self._hyde_query_builder,
                    request,
                    planning,
                )
            tool_outcomes: list[Any] = []
            for index, tool_name in enumerate(
                _tool_sequence_for_planning(planning)[
                    : min(request.budget.max_tool_calls, request.budget.max_iterations)
                ],
                start=1,
            ):
                tool_outcome = self._tool_executor.execute(
                    ToolExecutionRequest(
                        call=ChatToolCall(
                            id=f"runtime-retrieval-{index}",
                            name=tool_name,
                            arguments={"query": planning.canonical_task},
                        ),
                        default_query=planning.canonical_task,
                        forbidden_tools=tuple(planning.action.forbidden_tools),
                        iteration=index,
                        completed_tool_ids=_completed_tool_ids(self._checkpoints, run),
                        deadline_monotonic=request.budget.deadline_monotonic,
                    )
                )
                _persist_tool_checkpoint(self._checkpoints, run, tool_outcome)
                _record_runtime_evidence(planning, tool_outcome)
                tool_outcomes.append(tool_outcome)
            tool_outcome = _combine_tool_outcomes(tool_outcomes)
            if tool_outcomes:
                _emit_required_tool_legacy_result_alias(
                    request,
                    required_tool=required_tool,
                    outcome=tool_outcomes[0],
                )
            final_iteration = max(1, len(tool_outcomes))
            tool_result = getattr(tool_outcome, "result", None)
            if (
                self._post_preflight_gate is not None
                and str(required_tool or "").strip()
                and bool(getattr(tool_result, "search_results", None))
            ):
                _record_tool_outcome_for_gate(self._post_preflight_gate, tool_outcome)
                gate_decision = self._post_preflight_gate(request, planning, run)
                if gate_decision.action == "return":
                    final_outcome = _pre_tool_gate_final_outcome(gate_decision)
                    _persist_final_checkpoint(
                        self._checkpoints,
                        run,
                        evidence=SimpleNamespace(
                            action=gate_decision.final_decision,
                            stop_reason=gate_decision.stop_reason,
                            sanitized_detail=gate_decision.sanitized_detail,
                        ),
                        final_outcome=final_outcome,
                    )
                    _emit_agent_step(
                        request,
                        iteration=1,
                        action=f"final_{gate_decision.final_decision}",
                        step_summary=gate_decision.stop_reason,
                    )
                    self._checkpoints.complete(run, final_outcome)
                    return final_outcome.result
            evidence = self._evidence_machine.evaluate(
                planning=planning,
                outcome=tool_outcome,
                budget=request.budget,
            )
            if (
                getattr(evidence, "action", None) == "answer"
                and _fast_route_insufficient_evidence(request, planning, tool_outcome)
            ):
                evidence = SimpleNamespace(
                    action="escalate",
                    stop_reason=None,
                    sanitized_detail="fast_route_insufficient_selected_sources",
                )
            _emit_agent_step(
                request,
                iteration=1,
                action=f"evidence_{str(getattr(evidence, 'action', ''))[:40]}",
                step_summary=str(getattr(evidence, "sanitized_detail", ""))[:160],
            )
            if (
                evidence.action == "escalate"
                and (
                    request.budget.max_tool_calls <= 1
                    or request.budget.max_iterations <= 1
                )
            ):
                evidence = SimpleNamespace(
                    action="refuse",
                    stop_reason="tool_budget_exhausted",
                    sanitized_detail="tool_budget_exhausted",
                )
            if evidence.action == "escalate":
                planning = self._planning_policy.escalate_fast_route(
                    PlanningRequest(
                        question=request.question,
                        history=request.history,
                        image_path=request.image_path,
                        trace=request.latency_trace,
                    ),
                    planning,
                )
                if retrieval_token is not None:
                    reset_current_retrieval_plan(retrieval_token)
                retrieval_token = set_current_retrieval_plan(getattr(planning, "plan", None))
                if route_token is not None:
                    reset_phase64_route_kind(route_token)
                route_token = set_phase64_route_kind(_route_context_kind(planning))
                if hyde_token is not None:
                    reset_current_hyde_vector_query(hyde_token)
                    hyde_token = None
                hyde_token = _bind_hyde_vector_query(
                    self._hyde_query_builder,
                    request,
                    planning,
                )
                tool_outcome = self._tool_executor.execute(
                    ToolExecutionRequest(
                        call=ChatToolCall(
                            id="runtime-retrieval-2",
                            name=retrieval_tool_for_action(planning.action),
                            arguments={"query": planning.canonical_task},
                        ),
                        default_query=planning.canonical_task,
                        forbidden_tools=tuple(planning.action.forbidden_tools),
                        iteration=2,
                        completed_tool_ids=_completed_tool_ids(self._checkpoints, run),
                        deadline_monotonic=request.budget.deadline_monotonic,
                    )
                )
                _persist_tool_checkpoint(self._checkpoints, run, tool_outcome)
                _record_runtime_evidence(planning, tool_outcome)
                evidence = self._evidence_machine.evaluate(
                    planning=planning,
                    outcome=tool_outcome,
                    budget=request.budget,
                )
                final_iteration = 2
                _emit_agent_step(
                    request,
                    iteration=2,
                    action=f"evidence_{str(getattr(evidence, 'action', ''))[:40]}",
                    step_summary=str(getattr(evidence, "sanitized_detail", ""))[:160],
                )
            final_request = self._final_request_builder(
                request, planning, tool_outcome, evidence
            )
            if evidence.action in {"refuse", "escalate"}:
                _apply_refusal_runtime_state(final_request, evidence)
                final_outcome = _normalize_final_outcome(
                    self._final_answers.refuse(final_request),
                    evidence,
                )
            else:
                final_outcome = _normalize_final_outcome(
                    self._final_answers.generate(final_request),
                    evidence,
                )
            _persist_final_checkpoint(
                self._checkpoints,
                run,
                evidence=evidence,
                final_outcome=final_outcome,
            )
            _emit_agent_step(
                request,
                iteration=final_iteration,
                action=f"final_{str(getattr(evidence, 'action', ''))[:40]}",
                step_summary=str(getattr(final_outcome, "stop_reason", ""))[:160],
            )
            self._checkpoints.complete(run, final_outcome)
            return final_outcome.result
        finally:
            if hyde_token is not None:
                reset_current_hyde_vector_query(hyde_token)
            if route_token is not None:
                reset_phase64_route_kind(route_token)
            if retrieval_token is not None:
                reset_current_retrieval_plan(retrieval_token)
            reset_current_latency_trace(latency_token)


def build_final_answer_request(
    request: CoordinatorRequest,
    planning: Any,
    tool_outcome: Any,
    evidence: Any,
) -> FinalAnswerRequest:
    result = getattr(tool_outcome, "result", None)
    call = getattr(result, "call", None)
    runtime_state = getattr(planning, "runtime_state", None)
    if runtime_state is None:
        raise ValueError("planning.runtime_state is required to build final answer request")
    strategy = str(getattr(planning, "final_answer_strategy", "structured_final_answer"))
    if strategy not in ("baseline", "structured_final_answer"):
        strategy = "structured_final_answer"
    tool_calls = tuple(getattr(result, "tool_calls", ()) or ())
    if not tool_calls:
        tool_calls = (call,) if call is not None else ()
    workflow_steps = tuple(getattr(result, "workflow_steps", ()) or ()) or tool_calls
    refusal_reason = str(getattr(result, "refusal_reason", "") or "").strip()
    if refusal_reason:
        request.latency_trace.set_value("runtime_tool_refusal_reason", refusal_reason[:240])
    return FinalAnswerRequest(
        question=request.question,
        history=request.history,
        strategy=cast_final_answer_strategy(strategy),
        search_results=tuple(getattr(result, "search_results", ()) or ()),
        sources=tuple(getattr(result, "sources", ()) or ()),
        tool_calls=tool_calls,
        workflow_steps=workflow_steps,
        runtime_state=runtime_state,
        latency_trace=request.latency_trace,
        prompt_budgets=dict(getattr(planning, "prompt_budgets", {}) or {}),
        token_emitter=request.token_emitter,
    )


def cast_final_answer_strategy(value: str) -> ToolCallingFinalAnswerStrategy:
    return "baseline" if value == "baseline" else "structured_final_answer"
