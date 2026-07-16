"""Lifecycle composition root for the modular Agent Runtime."""

from __future__ import annotations

from typing import Callable

from app.services.agent.runtime_contracts import (
    CoordinatorRequest,
    FinalAnswerRequest,
    PreToolGateDecision,
    ToolCallingFinalAnswerStrategy,
)
from app.services.agent.run_coordinator_support import run_coordinator_once


class RunCoordinator:
    def __init__(
        self,
        *,
        planning_policy: object,
        checkpoints: object,
        tool_executor: object,
        evidence_machine: object,
        final_answers: object,
        final_request_builder: Callable[
            [CoordinatorRequest, object, object, object],
            FinalAnswerRequest,
        ]
        | None = None,
        pre_tool_gate: Callable[[CoordinatorRequest, object, object], PreToolGateDecision]
        | None = None,
        post_preflight_gate: Callable[
            [CoordinatorRequest, object, object],
            PreToolGateDecision,
        ]
        | None = None,
        hyde_query_builder: Callable[[CoordinatorRequest, object], str] | None = None,
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

    def run(self, request: CoordinatorRequest) -> object:
        return run_coordinator_once(self, request)


def build_final_answer_request(
    request: CoordinatorRequest,
    planning: object,
    tool_outcome: object,
    evidence: object,
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
