from dataclasses import fields
from typing import get_args

import pytest

from app.services.agent.runtime_contracts import (
    CoordinatorRequest,
    FinalAnswerOutcome,
    FinalAnswerRequest,
    PreToolGateDecision,
    RunBudget,
    RuntimeFinalDecision,
    RuntimeStopReason,
    ToolExecutionOutcome,
    ToolExecutionRequest,
)
from app.services.agent.runtime import AgentRuntimeState, RuntimeContext


def test_run_budget_rejects_non_positive_limits() -> None:
    with pytest.raises(ValueError, match="max_tool_calls"):
        RunBudget(max_tool_calls=0, max_iterations=3, deadline_monotonic=None)
    with pytest.raises(ValueError, match="max_iterations"):
        RunBudget(max_tool_calls=3, max_iterations=0, deadline_monotonic=None)


def test_stop_reason_and_final_decision_are_safe_closed_vocabularies() -> None:
    assert get_args(RuntimeStopReason) == (
        "completed",
        "invalid_request",
        "insufficient_evidence",
        "planner_fallback_exhausted",
        "tool_budget_exhausted",
        "deadline_exhausted",
        "cancelled",
        "checkpoint_unavailable",
        "internal_error",
    )
    assert get_args(RuntimeFinalDecision) == ("pending", "answer", "refuse")


def test_runtime_contracts_expose_only_data_fields() -> None:
    assert [field.name for field in fields(CoordinatorRequest)] == [
        "question",
        "budget",
        "history",
        "event_sink",
        "conversation_id",
        "resume_policy",
        "resume_run_id",
        "image_path",
        "latency_trace",
        "token_emitter",
    ]
    assert [field.name for field in fields(ToolExecutionRequest)] == [
        "call",
        "default_query",
        "forbidden_tools",
        "iteration",
        "completed_tool_ids",
        "deadline_monotonic",
        "image_path",
    ]
    assert [field.name for field in fields(ToolExecutionOutcome)] == [
        "result",
        "elapsed_ms",
        "error_category",
        "skipped_completed_tool",
    ]
    assert [field.name for field in fields(PreToolGateDecision)] == [
        "action",
        "result",
        "stop_reason",
        "final_decision",
        "sanitized_detail",
        "citations",
        "citation_repair_count",
    ]
    assert [field.name for field in fields(FinalAnswerRequest)] == [
        "question",
        "history",
        "strategy",
        "search_results",
        "sources",
        "tool_calls",
        "workflow_steps",
        "runtime_state",
        "latency_trace",
        "prompt_budgets",
        "token_emitter",
    ]
    assert [field.name for field in fields(FinalAnswerOutcome)] == [
        "result",
        "citations",
        "citation_repair_count",
        "stop_reason",
    ]


def test_runtime_state_keeps_legacy_detail_but_normalizes_stop_reason() -> None:
    state = AgentRuntimeState(context=RuntimeContext(current_query="q"))

    state.set_stop_reason("figure_evidence_not_found")

    assert state.stop_reason == "figure_evidence_not_found"
    assert state.normalized_stop_reason == "insufficient_evidence"
    assert state.diagnostics()["runtime_stop_reason"] == "figure_evidence_not_found"


def test_runtime_state_preserves_deadline_exhaustion_as_closed_stop_reason() -> None:
    state = AgentRuntimeState(context=RuntimeContext(current_query="q"))

    state.set_stop_reason("deadline_exhausted")

    assert state.stop_reason == "deadline_exhausted"
    assert state.normalized_stop_reason == "deadline_exhausted"
    assert state.diagnostics()["runtime_normalized_stop_reason"] == "deadline_exhausted"
