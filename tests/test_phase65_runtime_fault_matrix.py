import pytest

from scripts.run_phase65_fault_matrix import (
    FaultMatrixResult,
    build_fault_summary,
    run_bounded_runtime_fault_matrix,
    run_deterministic_fault_matrix,
    run_runtime_injection_fault_matrix,
)


@pytest.mark.parametrize(
    ("fault", "expected_stop", "expected_category"),
    [
        ("planner_invalid", None, "deterministic_fallback"),
        ("planner_timeout", None, "deterministic_fallback"),
        ("optional_channel_timeout", None, "optional_channel_failed"),
        (
            "required_evidence_missing",
            "insufficient_evidence",
            "required_evidence_missing",
        ),
        ("rerank_failure", "insufficient_evidence", "reranking_failed"),
        ("checkpoint_write_failure", "checkpoint_unavailable", "checkpoint_write_failed"),
        ("deadline", "deadline_exhausted", "deadline_exhausted"),
        ("cancel", "cancelled", "client_stream_aborted"),
    ],
)
def test_fault_matrix_normalizes_expected_categories(
    fault: str,
    expected_stop: str | None,
    expected_category: str,
) -> None:
    results = run_deterministic_fault_matrix([fault])

    assert results == [
        FaultMatrixResult(
            fault=fault,
            stop_reason=expected_stop,
            safe_category=expected_category,
        )
    ]


def test_fault_summary_blocks_unclassified_or_replayed_tools() -> None:
    summary = build_fault_summary(
        [
            FaultMatrixResult("rerank_failure", "insufficient_evidence", "reranking_failed"),
            FaultMatrixResult("unknown", "internal_error", "unclassified_error"),
            FaultMatrixResult(
                "resume_replay",
                "checkpoint_unavailable",
                "completed_tool_replay_prevented",
                completed_tool_replay_count=1,
            ),
        ]
    )

    assert summary["gate"] == "blocked"
    assert summary["unclassified_errors"] == 1
    assert summary["completed_tool_replay_count"] == 1


def test_fault_summary_passes_when_all_faults_are_classified_and_no_leaks() -> None:
    summary = build_fault_summary(run_deterministic_fault_matrix())

    assert summary["gate"] == "pass"
    assert summary["case_count"] == 8
    assert summary["unclassified_errors"] == 0
    assert summary["completed_tool_replay_count"] == 0
    assert summary["cancelled_work_leak_count"] == 0
    assert "answer" not in str(summary).casefold()
    assert "raw_response" not in str(summary).casefold()


def test_runtime_injection_fault_matrix_exercises_core_runtime_boundaries() -> None:
    results = run_runtime_injection_fault_matrix(
        [
            "required_evidence_missing",
            "rerank_failure",
            "checkpoint_write_failure",
            "deadline",
            "completed_tool_replay",
            "cancel",
        ]
    )

    by_fault = {result.fault: result for result in results}
    assert by_fault["required_evidence_missing"].stop_reason == "insufficient_evidence"
    assert by_fault["required_evidence_missing"].safe_category == "required_evidence_missing"
    assert by_fault["rerank_failure"].safe_category == "reranking_failed"
    assert by_fault["checkpoint_write_failure"].stop_reason == "checkpoint_unavailable"
    assert by_fault["deadline"].stop_reason == "deadline_exhausted"
    assert by_fault["completed_tool_replay"].safe_category == "completed_tool_replay_prevented"
    assert by_fault["completed_tool_replay"].completed_tool_replay_count == 0
    assert by_fault["cancel"].stop_reason == "cancelled"
    assert all(result.runtime_boundary != "deterministic_taxonomy" for result in results)

    summary = build_fault_summary(results)
    assert summary["gate"] == "pass"
    assert summary["execution_mode"] == "module_boundary_injection"
    assert summary["runtime_injection_coverage"] == "core_runtime_faults"
    assert summary["runtime_injected_case_count"] == len(results)


def test_runtime_injection_default_matrix_includes_completed_tool_replay_guard() -> None:
    results = run_runtime_injection_fault_matrix()
    summary = build_fault_summary(results)

    assert "completed_tool_replay" in {result.fault for result in results}
    assert summary["case_count"] == 9
    assert summary["completed_tool_replay_count"] == 0
    assert summary["execution_mode"] == "module_boundary_injection"


def test_bounded_runtime_fault_matrix_executes_requested_injection_load() -> None:
    summary = run_bounded_runtime_fault_matrix(concurrency=4, requests=18)

    assert summary["gate"] == "pass"
    assert summary["execution_mode"] == "bounded_module_boundary_injection"
    assert summary["runtime_injection_coverage"] == "core_runtime_faults"
    assert summary["configured_concurrency"] == 4
    assert summary["configured_requests"] == 18
    assert summary["bounded_load_completed_requests"] == 18
    assert summary["bounded_load_failed_requests"] == 0
    assert summary["bounded_load_max_inflight_observed"] <= 4
    assert summary["runtime_injected_case_count"] == 18
    assert summary["case_count"] == 18
    assert summary["unique_fault_count"] == 9
    assert "answer" not in str(summary).casefold()
    assert "raw_response" not in str(summary).casefold()
