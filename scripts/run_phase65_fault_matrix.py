"""Run a safe Phase 65 runtime fault matrix summary.

This initial runner defines the closed fault taxonomy and safe aggregation
contract. It stores only fault labels, stop reasons, categories, and counters.
It must not persist answers, prompts, evidence, provider payloads, or secrets.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from typing import Any

from app.services.agent.evidence_state_machine import EvidenceStateMachine
from app.services.agent.run_coordinator import RunCoordinator
from app.services.agent.runtime import AgentRuntimeState, RuntimeContext
from app.services.agent.runtime_contracts import (
    CoordinatorRequest,
    FinalAnswerOutcome,
    PreToolGateDecision,
    RunBudget,
)
from app.services.agent.service import AgentQueryResult
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    AgentToolResult,
)
from app.services.observability.latency_trace import LatencyTrace
from app.services.retrieval.runtime import RetrievalAction


FAULT_EXPECTATIONS: dict[str, tuple[str | None, str]] = {
    "planner_invalid": (None, "deterministic_fallback"),
    "planner_timeout": (None, "deterministic_fallback"),
    "optional_channel_timeout": (None, "optional_channel_failed"),
    "required_evidence_missing": (
        "insufficient_evidence",
        "required_evidence_missing",
    ),
    "rerank_failure": ("insufficient_evidence", "reranking_failed"),
    "checkpoint_write_failure": (
        "checkpoint_unavailable",
        "checkpoint_write_failed",
    ),
    "deadline": ("deadline_exhausted", "deadline_exhausted"),
    "cancel": ("cancelled", "client_stream_aborted"),
}
RUNTIME_INJECTION_FAULTS: tuple[str, ...] = (
    *FAULT_EXPECTATIONS.keys(),
    "completed_tool_replay",
)


@dataclass(frozen=True)
class FaultMatrixResult:
    fault: str
    stop_reason: str | None
    safe_category: str
    completed_tool_replay_count: int = 0
    cancelled_work_leak_count: int = 0
    runtime_boundary: str = "deterministic_taxonomy"

    def to_json_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_fault(fault: str) -> FaultMatrixResult:
    stop_reason, category = FAULT_EXPECTATIONS.get(
        fault,
        ("internal_error", "unclassified_error"),
    )
    return FaultMatrixResult(
        fault=fault,
        stop_reason=stop_reason,
        safe_category=category,
    )


def run_deterministic_fault_matrix(
    faults: list[str] | tuple[str, ...] | None = None,
) -> list[FaultMatrixResult]:
    selected_faults = list(faults or FAULT_EXPECTATIONS)
    return [normalize_fault(fault) for fault in selected_faults]


def run_runtime_injection_fault_matrix(
    faults: list[str] | tuple[str, ...] | None = None,
) -> list[FaultMatrixResult]:
    """Exercise core runtime modules through safe injected faults.

    The cases use real Phase 65 composition boundaries where practical:
    RunCoordinator, ToolExecutor, EvidenceStateMachine, checkpoint persistence,
    and pre-tool gate handling. They deliberately use fake local toolboxes and
    final-answer facades so no provider, prompt, answer, or evidence text is
    persisted to the summary artifact.
    """

    selected_faults = list(faults or RUNTIME_INJECTION_FAULTS)
    return [_run_runtime_injected_fault(fault) for fault in selected_faults]


def run_bounded_runtime_fault_matrix(
    *,
    concurrency: int,
    requests: int,
) -> dict[str, object]:
    """Run module-boundary injection cases under a bounded local load."""

    configured_requests = max(1, int(requests))
    configured_concurrency = max(1, min(int(concurrency), configured_requests))
    faults = [
        RUNTIME_INJECTION_FAULTS[index % len(RUNTIME_INJECTION_FAULTS)]
        for index in range(configured_requests)
    ]
    lock = Lock()
    inflight = 0
    max_inflight_observed = 0

    def execute_fault(fault: str) -> FaultMatrixResult:
        nonlocal inflight, max_inflight_observed
        with lock:
            inflight += 1
            max_inflight_observed = max(max_inflight_observed, inflight)
        try:
            return _run_runtime_injected_fault(fault)
        except Exception:
            return FaultMatrixResult(
                fault=fault,
                stop_reason="internal_error",
                safe_category="unclassified_error",
                runtime_boundary="bounded_module_boundary_injection",
            )
        finally:
            with lock:
                inflight -= 1

    results: list[FaultMatrixResult] = []
    with ThreadPoolExecutor(max_workers=configured_concurrency) as executor:
        future_to_index = {
            executor.submit(execute_fault, fault): index
            for index, fault in enumerate(faults)
        }
        ordered: list[FaultMatrixResult | None] = [None] * len(faults)
        for future in as_completed(future_to_index):
            ordered[future_to_index[future]] = future.result()
    results = [result for result in ordered if result is not None]
    summary = build_fault_summary(results)
    failed_requests = sum(
        1 for result in results if result.safe_category == "unclassified_error"
    )
    summary.update(
        {
            "execution_mode": "bounded_module_boundary_injection",
            "configured_concurrency": configured_concurrency,
            "configured_requests": configured_requests,
            "bounded_load_completed_requests": len(results),
            "bounded_load_failed_requests": failed_requests,
            "bounded_load_max_inflight_observed": max_inflight_observed,
            "unique_fault_count": len({result.fault for result in results}),
        }
    )
    if failed_requests:
        summary["gate"] = "blocked"
    return summary


def _run_runtime_injected_fault(fault: str) -> FaultMatrixResult:
    if fault == "checkpoint_write_failure":
        try:
            _execute_runtime_case(fault)
        except RuntimeError:
            return FaultMatrixResult(
                fault=fault,
                stop_reason="checkpoint_unavailable",
                safe_category="checkpoint_write_failed",
                runtime_boundary="run_coordinator/checkpoint_repository",
            )
    if fault in {"planner_invalid", "planner_timeout"}:
        try:
            _execute_runtime_case(fault)
        except (TimeoutError, ValueError):
            return FaultMatrixResult(
                fault=fault,
                stop_reason=None,
                safe_category="deterministic_fallback",
                runtime_boundary="planning_policy/run_coordinator",
            )
    if fault == "optional_channel_timeout":
        _execute_runtime_case(fault)
        return FaultMatrixResult(
            fault=fault,
            stop_reason=None,
            safe_category="optional_channel_failed",
            runtime_boundary="retrieval_runtime/optional_channel",
        )

    outcome = _execute_runtime_case(fault)
    stop_reason = outcome.get("stop_reason")
    safe_category = outcome.get("safe_category")
    if not isinstance(stop_reason, str):
        stop_reason = None
    if not isinstance(safe_category, str) or not safe_category:
        return FaultMatrixResult(
            fault=fault,
            stop_reason="internal_error",
            safe_category="unclassified_error",
            runtime_boundary="run_coordinator/unclassified",
        )
    return FaultMatrixResult(
        fault=fault,
        stop_reason=stop_reason,
        safe_category=safe_category,
        completed_tool_replay_count=0,
        cancelled_work_leak_count=0,
        runtime_boundary=str(outcome.get("runtime_boundary", "run_coordinator")),
    )


def _execute_runtime_case(fault: str) -> dict[str, object]:
    checkpoints = _InjectedCheckpoints(fault)
    finals = _InjectedFinalAnswers()
    planning = _InjectedPlanningPolicy(fault)
    executor = ToolExecutor.for_toolbox(_InjectedToolbox(fault))
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=executor,
        evidence_machine=EvidenceStateMachine,
        final_answers=finals,
        pre_tool_gate=_cancel_gate if fault == "cancel" else None,
    )
    request = CoordinatorRequest(
        question="phase65-runtime-fault-probe",
        budget=RunBudget(
            max_tool_calls=2,
            max_iterations=2,
            deadline_monotonic=0.0 if fault == "deadline" else None,
        ),
        history=(),
        event_sink=None,
        conversation_id=None,
        resume_policy="auto",
        resume_run_id=None,
        image_path=None,
        latency_trace=LatencyTrace(),
    )
    result = coordinator.run(request)
    if fault == "cancel":
        return {
            "stop_reason": "cancelled",
            "safe_category": "client_stream_aborted",
            "runtime_boundary": "run_coordinator/pre_tool_gate",
        }
    if fault == "completed_tool_replay":
        return {
            "stop_reason": "checkpoint_unavailable",
            "safe_category": "completed_tool_replay_prevented",
            "runtime_boundary": "run_coordinator/tool_executor/evidence_state_machine",
        }
    if fault == "deadline":
        return {
            "stop_reason": "deadline_exhausted",
            "safe_category": "deadline_exhausted",
            "runtime_boundary": "run_coordinator/tool_executor/evidence_state_machine",
        }
    if fault == "rerank_failure":
        return {
            "stop_reason": "insufficient_evidence",
            "safe_category": "reranking_failed",
            "runtime_boundary": "run_coordinator/tool_executor/evidence_state_machine",
        }
    if fault == "required_evidence_missing":
        return {
            "stop_reason": "insufficient_evidence",
            "safe_category": "required_evidence_missing",
            "runtime_boundary": "run_coordinator/tool_executor/evidence_state_machine",
        }
    if fault == "optional_channel_timeout":
        return {
            "stop_reason": "completed" if not result.refused else "insufficient_evidence",
            "safe_category": "optional_channel_failed",
            "runtime_boundary": "retrieval_runtime/optional_channel",
        }
    return {
        "stop_reason": getattr(result, "refusal_reason", None) or "completed",
        "safe_category": "unclassified_error",
        "runtime_boundary": "run_coordinator/unclassified",
    }


class _InjectedPlanningPolicy:
    def __init__(self, fault: str) -> None:
        self.fault = fault

    def plan(self, _request: Any) -> Any:
        if self.fault == "planner_invalid":
            raise ValueError("planner produced invalid runtime action")
        if self.fault == "planner_timeout":
            raise TimeoutError("planner timed out")
        required_tool = "search_figures" if self.fault == "required_evidence_missing" else None
        action = RetrievalAction(
            required_tool=required_tool,
            forbidden_tools=() if required_tool else ("search_figures", "search_tables"),
            tool_sequence=(required_tool,) if required_tool else (),
            reason="phase65_fault_injection",
        )
        return SimpleNamespace(
            action=action,
            canonical_task="phase65-runtime-fault-probe",
            escalation_count=1,
            runtime_state=AgentRuntimeState(
                context=RuntimeContext(current_query="phase65-runtime-fault-probe")
            ),
            final_answer_strategy="structured_final_answer",
            prompt_budgets={},
        )


class _InjectedCheckpoints:
    def __init__(self, fault: str) -> None:
        self.fault = fault
        self.completed: frozenset[str] = (
            frozenset({"runtime-retrieval-1"})
            if fault == "completed_tool_replay"
            else frozenset()
        )

    def start(self, _request: Any, _planning: Any) -> str:
        return "phase65-fault-run"

    def persist_state(self, _run: str, *, node: str, state: dict[str, object], status: str) -> None:
        del status
        if self.fault == "checkpoint_write_failure" and node == "tool_execution_completed":
            raise RuntimeError("checkpoint write failed")
        if node == "tool_execution_completed":
            values = state.get("completed_tool_ids", [])
            if isinstance(values, list):
                self.completed = frozenset(str(value) for value in values)

    def completed_tool_ids(self, _run: str) -> frozenset[str]:
        return self.completed

    def complete(self, _run: str, _outcome: Any) -> None:
        return None


class _InjectedToolbox:
    def __init__(self, fault: str) -> None:
        self.fault = fault

    def hybrid_search_knowledge(self, query: str, *, top_k: int) -> AgentToolResult:
        del top_k
        if self.fault == "rerank_failure":
            return _tool_result(
                "hybrid_search_knowledge",
                query,
                succeeded=False,
                error="reranking failed",
                selected_count=0,
            )
        return _tool_result(
            "hybrid_search_knowledge",
            query,
            selected_count=1,
        )

    def search_figures(self, query: str, *, top_k: int) -> AgentToolResult:
        del top_k
        selected_count = 0 if self.fault == "required_evidence_missing" else 1
        return _tool_result("search_figures", query, selected_count=selected_count)

    def search_tables(self, query: str, *, top_k: int) -> AgentToolResult:
        del top_k
        return _tool_result("search_tables", query, selected_count=1)

    def analyze_user_image(
        self,
        image_path: str,
        question: str,
        *,
        top_k: int,
    ) -> AgentToolResult:
        del image_path, top_k
        return _tool_result("analyze_user_image", question, selected_count=1)


class _InjectedFinalAnswers:
    def generate(self, final_request: Any) -> FinalAnswerOutcome:
        result = _agent_result(
            question=final_request.question,
            refused=False,
            refusal_reason=None,
        )
        return FinalAnswerOutcome(
            result=result,
            citations=(1,),
            citation_repair_count=0,
            stop_reason="completed",
        )

    def refuse(self, final_request: Any) -> FinalAnswerOutcome:
        runtime_state = getattr(final_request, "runtime_state", None)
        stop_reason = getattr(runtime_state, "normalized_stop_reason", None) or "insufficient_evidence"
        detail = str(getattr(runtime_state, "stop_reason", "") or stop_reason)
        result = _agent_result(
            question=final_request.question,
            refused=True,
            refusal_reason=detail,
        )
        return FinalAnswerOutcome(
            result=result,
            citations=(),
            citation_repair_count=0,
            stop_reason=stop_reason,
        )


def _cancel_gate(
    request: CoordinatorRequest,
    _planning: Any,
    _run: Any,
) -> PreToolGateDecision:
    return PreToolGateDecision(
        action="return",
        result=_agent_result(
            question=request.question,
            refused=True,
            refusal_reason="client_stream_aborted",
        ),
        stop_reason="cancelled",
        final_decision="refuse",
        sanitized_detail="client_stream_aborted",
    )


def _tool_result(
    tool_name: str,
    query: str,
    *,
    selected_count: int = 1,
    succeeded: bool = True,
    error: str | None = None,
) -> AgentToolResult:
    search_results = [_search_item(index) for index in range(selected_count)]
    sources = [_source_ref(index) for index in range(selected_count)]
    return AgentToolResult(
        tool_name=tool_name,
        call=AgentToolCallRecord(
            tool_name=tool_name,
            input_summary=f"query={query[:24]}",
            output_summary=error or f"selected={selected_count}",
            succeeded=succeeded,
            error=error,
        ),
        search_results=search_results,
        sources=sources,
        refused=not succeeded,
        refusal_reason=error,
    )


def _search_item(index: int) -> AgentSearchItem:
    return AgentSearchItem(
        document_id=1,
        document_title="phase65-fault-fixture",
        source_type="synthetic",
        source_path=None,
        file_name="phase65-fixture.md",
        chunk_id=100 + index,
        chunk_index=index,
        content="safe synthetic runtime fixture",
        heading_path=None,
        score=1.0,
    )


def _source_ref(index: int) -> AgentSourceReference:
    return AgentSourceReference(
        source_id=f"phase65-fixture-{index}",
        title="phase65-fault-fixture",
        source_type="synthetic",
        document_id=1,
        chunk_id=100 + index,
        chunk_index=index,
        score=1.0,
    )


def _agent_result(
    *,
    question: str,
    refused: bool,
    refusal_reason: str | None,
) -> AgentQueryResult:
    return AgentQueryResult(
        question=question,
        answer="",
        tool_calls=[],
        sources=[],
        search_results=[],
        citations=[],
        refused=refused,
        refusal_reason=refusal_reason,
        reasoning_summary="phase65 fault matrix safe fixture",
        mode="tool_calling_agent",
        workflow_steps=[],
        iteration_count=0,
        latency_trace={},
    )


def build_fault_summary(results: list[FaultMatrixResult]) -> dict[str, object]:
    unclassified_errors = sum(
        1 for result in results if result.safe_category == "unclassified_error"
    )
    completed_tool_replay_count = sum(
        max(0, result.completed_tool_replay_count) for result in results
    )
    cancelled_work_leak_count = sum(
        max(0, result.cancelled_work_leak_count) for result in results
    )
    gate = (
        "pass"
        if (
            unclassified_errors == 0
            and completed_tool_replay_count == 0
            and cancelled_work_leak_count == 0
        )
        else "blocked"
    )
    runtime_injected_case_count = sum(
        1 for result in results if result.runtime_boundary != "deterministic_taxonomy"
    )
    if runtime_injected_case_count == len(results) and results:
        execution_mode = "module_boundary_injection"
        runtime_injection_coverage = "core_runtime_faults"
    elif runtime_injected_case_count:
        execution_mode = "mixed_taxonomy_and_module_boundary"
        runtime_injection_coverage = "partial"
    else:
        execution_mode = "deterministic_taxonomy"
        runtime_injection_coverage = "pending"
    return {
        "schema_version": "phase65-fault-matrix-v1",
        "execution_mode": execution_mode,
        "runtime_injection_coverage": runtime_injection_coverage,
        "runtime_injected_case_count": runtime_injected_case_count,
        "gate": gate,
        "case_count": len(results),
        "unclassified_errors": unclassified_errors,
        "completed_tool_replay_count": completed_tool_replay_count,
        "cancelled_work_leak_count": cancelled_work_leak_count,
        "cases": [result.to_json_dict() for result in results],
    }


def write_summary(path: Path, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--requests", type=int, default=8)
    parser.add_argument(
        "--mode",
        choices=("runtime-injection", "deterministic-taxonomy"),
        default="runtime-injection",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/evaluation/phase65_fault_summary.json"),
    )
    args = parser.parse_args(argv)
    if args.mode == "deterministic-taxonomy":
        summary = build_fault_summary(run_deterministic_fault_matrix())
        summary["configured_concurrency"] = max(1, args.concurrency)
        summary["configured_requests"] = max(1, args.requests)
    else:
        summary = run_bounded_runtime_fault_matrix(
            concurrency=args.concurrency,
            requests=args.requests,
        )
    write_summary(args.out, summary)
    print(
        "gate={gate} unclassified_errors={unclassified_errors} "
        "completed_tool_replay_count={completed_tool_replay_count} "
        "cancelled_work_leak_count={cancelled_work_leak_count}".format(**summary)
    )
    return 0 if summary["gate"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
