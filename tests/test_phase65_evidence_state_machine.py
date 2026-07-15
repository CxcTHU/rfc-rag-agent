from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.services.agent.evidence_state_machine import EvidenceStateMachine
from app.services.agent.runtime_contracts import RunBudget


@pytest.mark.parametrize(
    ("required_tool", "result_count", "rerank_failed", "escalations", "expected"),
    [
        (None, 4, False, 0, "answer"),
        ("search_figures", 0, False, 0, "refuse"),
        (None, 0, False, 0, "escalate"),
        (None, 0, False, 1, "refuse"),
        (None, 4, True, 0, "refuse"),
    ],
)
def test_evidence_transition_table(
    required_tool: str | None,
    result_count: int,
    rerank_failed: bool,
    escalations: int,
    expected: str,
) -> None:
    decision = EvidenceStateMachine(
        required_tool=required_tool,
        result_count=result_count,
        rerank_failed=rerank_failed,
        escalation_count=escalations,
        budget=RunBudget(max_tool_calls=2, max_iterations=2),
    ).decide()

    assert decision.action == expected


def test_deadline_exhaustion_fails_closed_without_escalation() -> None:
    decision = EvidenceStateMachine.evaluate(
        planning=SimpleNamespace(action=SimpleNamespace(required_tool=None), escalation_count=0),
        outcome=SimpleNamespace(
            result=SimpleNamespace(sources=[]),
            error_category="deadline_exhausted",
        ),
        budget=RunBudget(max_tool_calls=2, max_iterations=2, deadline_monotonic=123.0),
    )

    assert decision.action == "refuse"
    assert decision.stop_reason == "deadline_exhausted"
    assert decision.sanitized_detail == "deadline_exhausted"


def test_completed_tool_replay_fails_closed_without_escalation() -> None:
    decision = EvidenceStateMachine.evaluate(
        planning=SimpleNamespace(action=SimpleNamespace(required_tool=None), escalation_count=0),
        outcome=SimpleNamespace(
            result=SimpleNamespace(sources=[]),
            error_category="completed_tool",
            skipped_completed_tool=True,
        ),
        budget=RunBudget(max_tool_calls=2, max_iterations=2),
    )

    assert decision.action == "refuse"
    assert decision.stop_reason == "checkpoint_unavailable"
    assert decision.sanitized_detail == "completed_tool_replay_prevented"


def test_required_tool_must_have_required_tool_results_even_when_other_sources_exist() -> None:
    decision = EvidenceStateMachine.evaluate(
        planning=SimpleNamespace(
            action=SimpleNamespace(required_tool="search_figures"),
            escalation_count=0,
        ),
        outcome=SimpleNamespace(
            result=SimpleNamespace(
                sources=["text-source"],
                required_tool_result_count=0,
            ),
            error_category=None,
        ),
        budget=RunBudget(max_tool_calls=2, max_iterations=2),
    )

    assert decision.action == "refuse"
    assert decision.stop_reason == "insufficient_evidence"
    assert decision.sanitized_detail == "required_evidence_missing"


def test_evidence_state_machine_requires_iteration_budget_for_escalation() -> None:
    decision = EvidenceStateMachine(
        required_tool=None,
        result_count=0,
        rerank_failed=False,
        escalation_count=0,
        budget=RunBudget(max_tool_calls=2, max_iterations=1),
    ).decide()

    assert decision.action == "refuse"
    assert decision.stop_reason == "insufficient_evidence"
    assert decision.sanitized_detail == "evidence_exhausted"


def test_evaluate_uses_planning_action_and_tool_outcome() -> None:
    decision = EvidenceStateMachine.evaluate(
        planning=SimpleNamespace(action=SimpleNamespace(required_tool="search_tables")),
        outcome=SimpleNamespace(
            result=SimpleNamespace(sources=[]),
            error_category=None,
        ),
        budget=RunBudget(max_tool_calls=2, max_iterations=2),
    )

    assert decision.action == "refuse"
    assert decision.sanitized_detail == "required_evidence_missing"
