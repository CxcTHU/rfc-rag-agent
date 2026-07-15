"""Explicit, side-effect-free evidence transition policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.agent.runtime_contracts import RunBudget, RuntimeStopReason


EvidenceAction = Literal["continue", "answer", "refuse", "escalate"]


@dataclass(frozen=True)
class EvidenceDecision:
    action: EvidenceAction
    stop_reason: RuntimeStopReason | None
    sanitized_detail: str


class EvidenceStateMachine:
    def __init__(
        self,
        *,
        required_tool: str | None,
        result_count: int,
        rerank_failed: bool,
        escalation_count: int,
        budget: RunBudget,
        deadline_exhausted: bool = False,
        completed_tool_replay: bool = False,
    ) -> None:
        self.required_tool = required_tool
        self.result_count = max(0, result_count)
        self.rerank_failed = rerank_failed
        self.deadline_exhausted = deadline_exhausted
        self.completed_tool_replay = completed_tool_replay
        self.escalation_count = max(0, escalation_count)
        self.budget = budget

    def decide(self) -> EvidenceDecision:
        if self.deadline_exhausted:
            return EvidenceDecision("refuse", "deadline_exhausted", "deadline_exhausted")
        if self.completed_tool_replay:
            return EvidenceDecision(
                "refuse",
                "checkpoint_unavailable",
                "completed_tool_replay_prevented",
            )
        if self.rerank_failed:
            return EvidenceDecision("refuse", "insufficient_evidence", "reranking_failed")
        if getattr(self, "tool_execution_failed", False):
            return EvidenceDecision("refuse", "insufficient_evidence", "tool_execution_failed")
        if self.required_tool is not None and self.result_count == 0:
            return EvidenceDecision(
                "refuse",
                "insufficient_evidence",
                "required_evidence_missing",
            )
        if self.result_count > 0:
            return EvidenceDecision("answer", None, "evidence_sufficient")
        if (
            self.escalation_count == 0
            and self.budget.max_tool_calls > 1
            and self.budget.max_iterations > 1
        ):
            return EvidenceDecision("escalate", None, "single_escalation")
        return EvidenceDecision("refuse", "insufficient_evidence", "evidence_exhausted")

    @classmethod
    def evaluate(
        cls,
        *,
        planning: object,
        outcome: object,
        budget: RunBudget,
    ) -> EvidenceDecision:
        action = getattr(planning, "action")
        result = getattr(outcome, "result")
        error_category = getattr(outcome, "error_category", None)
        required_tool = getattr(action, "required_tool", None)
        source_count = len(getattr(result, "sources", ()) or ())
        required_tool_result_count = getattr(result, "required_tool_result_count", None)
        tool_result_counts = getattr(result, "tool_result_counts", None)
        if (
            required_tool is not None
            and required_tool_result_count is None
            and isinstance(tool_result_counts, dict)
        ):
            required_tool_result_count = tool_result_counts.get(required_tool)
        result_count = (
            max(0, int(required_tool_result_count))
            if required_tool is not None and required_tool_result_count is not None
            else source_count
        )
        return cls(
            required_tool=required_tool,
            result_count=result_count,
            rerank_failed=error_category == "reranking_failed",
            deadline_exhausted=error_category == "deadline_exhausted",
            completed_tool_replay=bool(
                getattr(outcome, "skipped_completed_tool", False)
                or error_category == "completed_tool"
            ),
            escalation_count=max(0, int(getattr(planning, "escalation_count", 0))),
            budget=budget,
        )._with_tool_execution_failed(
            error_category in {"tool_execution_failed", "unsupported_tool", "forbidden_tool"}
        ).decide()

    def _with_tool_execution_failed(self, value: bool) -> "EvidenceStateMachine":
        object.__setattr__(self, "tool_execution_failed", bool(value))
        return self
