from __future__ import annotations

import json

from scripts.summarize_phase65_acceptance import (
    _load_csv_rows,
    _safe_json_sha256,
    build_acceptance_summary,
    build_baseline_reuse_waiver,
)
from scripts.build_phase65_holdout_blocked_summary import (
    build_holdout_blocked_summary,
)
from scripts.build_phase65_human_acceptance_packet import (
    build_human_acceptance_packet,
)
from scripts.record_phase65_human_acceptance import (
    main as record_human_acceptance_main,
    record_human_acceptance,
)


def _contract_snapshot() -> dict[str, object]:
    return {
        "schema_version": "phase65-contract-v1",
        "agent_request_schema_sha256": "a" * 64,
        "agent_response_schema_sha256": "b" * 64,
        "tool_schema_sha256": "c" * 64,
        "sse_fixture_sha256": "d" * 64,
        "checkpoint_schema_sha256": "e" * 64,
        "runtime_event_names": ["agent_step", "tool_call_result", "tool_call_start"],
    }


def _pass_summary(schema_version: str) -> dict[str, object]:
    return {"schema_version": schema_version, "gate": "pass", "failed_required": []}


def _blocked_evaluator_mismatch_summary() -> dict[str, object]:
    return {
        "mode": "summarize",
        "rows": 60,
        "manifest_comparison": ["evaluator_sha256_mismatch"],
        "gate_decision": {
            "contract_gate": "blocked",
            "quality_gate": "blocked",
            "runtime_non_regression_gate": "blocked",
            "phase64_latency_closure_gate": "blocked",
            "phase65_acceptance": "blocked",
            "reasons": ["evaluator_sha256_mismatch"],
            "metrics": {"paired_row_count": 30},
        },
    }


def _minimal_paired_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(30):
        for variant in ("baseline", "candidate"):
            rows.append(
                {
                    "variant": variant,
                    "case_id": f"case-{index:02d}",
                    "run": "1",
                    "ok": "True",
                    "error_category": "",
                    "http_status": "200",
                    "cold_cache_receipt_status": "valid",
                    "completed_tool_replay_count": "0",
                }
            )
    return rows


def _passing_holdout_summary() -> dict[str, object]:
    return {
        "schema_version": "phase65-holdout-summary-v1",
        "clean": True,
        "execution_mode": "real_api",
        "executed_ab_row_count": 24,
        "baseline_ab_row_count": 12,
        "candidate_ab_row_count": 12,
        "baseline_ab_case_set_sha256": "f" * 64,
        "candidate_ab_case_set_sha256": "f" * 64,
        "holdout_case_count": 12,
        "holdout_case_set_sha256": "f" * 64,
        "tuning_exclusion_proven": True,
        "primary_latency_percentile_ci_exclusion_proven": True,
        "public_overlap_exclusion_proven": True,
        "excluded_case_count": 30,
        "excluded_case_set_sha256": "e" * 64,
        "judge_summary": {
            "schema_version": "phase65-judge-summary-v1",
            "paired_count": 12,
            "judge_expected_pairs": 12,
            "case_set_sha256": "f" * 64,
            "receipt_contract_sha256": "a" * 64,
            "completion_lower_bound": 0.0,
            "accuracy_lower_bound": 0.0,
            "citation_support_lower_bound": 0.0,
            "overall_quality_lower_bound": 0.0,
        },
    }


def _accepted_human_summary_for(acceptance: dict[str, object]) -> dict[str, object]:
    packet = build_human_acceptance_packet(
        acceptance_summary=acceptance,
        reviewer_label="user",
    )
    receipt = record_human_acceptance(
        acceptance_packet=packet,
        current_acceptance_summary=acceptance,
        decision="pass",
        reviewer_label="user",
        checklist_confirmed=True,
    )
    return receipt["human_acceptance_summary"]


def test_acceptance_summary_blocks_when_primary_paired_evidence_is_missing() -> None:
    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "blocked",
            "failed_required": ["candidate_contract_fetch_not_ready"],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "blocked",
            "ready_to_execute": False,
            "failed_required": ["paid_execution_not_authorized"],
        },
        paired_summary=None,
        holdout_summary=None,
        human_acceptance=None,
    )

    assert summary["schema_version"] == "phase65-acceptance-summary-v1"
    assert summary["gate"] == "blocked"
    assert summary["components"]["contract_snapshot"] == "pass"
    assert summary["components"]["topology_gate"] == "pass"
    assert summary["components"]["fault_gate"] == "pass"
    assert summary["components"]["recovery_gate"] == "pass"
    assert summary["components"]["endpoint_readiness"] == "blocked"
    assert summary["components"]["paired_execution_preflight"] == "blocked"
    assert summary["components"]["paired_full_gate"] == "missing"
    assert summary["components"]["holdout_gate"] == "missing"
    assert summary["components"]["human_acceptance"] == "missing"
    assert "endpoint_readiness_not_pass" in summary["failed_required"]
    assert "paired_execution_preflight_not_pass" in summary["failed_required"]
    assert "paired_full_summary_missing" in summary["failed_required"]
    assert "holdout_summary_missing" in summary["failed_required"]
    assert "human_acceptance_missing" in summary["failed_required"]
    assert "answer" not in json.dumps(summary).casefold()
    assert "prompt" not in json.dumps(summary).casefold()


def test_acceptance_summary_distinguishes_blocked_paired_summary_from_missing() -> None:
    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "blocked",
            "ready_to_execute": False,
            "failed_required": ["paid_execution_not_authorized"],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "blocked",
                "quality_gate": "blocked",
                "runtime_non_regression_gate": "blocked",
                "phase64_latency_closure_gate": "blocked",
                "phase65_acceptance": "blocked",
                "reasons": ["evaluator_sha256_mismatch"],
            },
        },
        holdout_summary=None,
        human_acceptance=None,
    )

    assert summary["components"]["paired_full_gate"] == "blocked"
    assert "paired_full_summary_missing" not in summary["failed_required"]
    assert "paired_full_gate_not_pass" in summary["failed_required"]
    assert any(
        "resolve blocked paired A/B summary" in action
        for action in summary["next_required_actions"]
    )


def test_baseline_reuse_waiver_requires_authorized_aligned_ok_rows() -> None:
    waiver = build_baseline_reuse_waiver(
        paired_summary=_blocked_evaluator_mismatch_summary(),
        paired_rows=_minimal_paired_rows(),
        user_authorized_baseline_reuse=True,
        expected_pair_count=30,
    )

    assert waiver["schema_version"] == "phase65-baseline-reuse-waiver-v1"
    assert waiver["gate"] == "pass"
    assert waiver["substitutes_paired_full_gate"] is True
    assert waiver["allowed_summary_blockers"] == ["evaluator_sha256_mismatch"]
    assert waiver["baseline_pair_count"] == 30
    assert waiver["candidate_pair_count"] == 30
    assert waiver["failed_required"] == []
    assert "answer" not in json.dumps(waiver).casefold()
    assert "prompt" not in json.dumps(waiver).casefold()


def test_baseline_reuse_csv_loader_handles_utf8_bom(tmp_path) -> None:
    path = tmp_path / "paired.csv"
    path.write_text("\ufeffvariant,case_id,run,ok\nbaseline,c1,1,True\n", encoding="utf-8")

    rows = _load_csv_rows(path)

    assert rows[0]["variant"] == "baseline"


def test_baseline_reuse_waiver_rejects_non_mismatch_blockers() -> None:
    paired_summary = _blocked_evaluator_mismatch_summary()
    paired_summary["gate_decision"]["reasons"] = ["paired_rows_incomplete"]

    waiver = build_baseline_reuse_waiver(
        paired_summary=paired_summary,
        paired_rows=_minimal_paired_rows(),
        user_authorized_baseline_reuse=True,
        expected_pair_count=30,
    )

    assert waiver["gate"] == "blocked"
    assert "paired_summary_not_limited_to_evaluator_mismatch" in waiver["failed_required"]


def test_acceptance_summary_substitutes_explicit_baseline_reuse_waiver_for_paired_full_gate() -> None:
    paired_summary = _blocked_evaluator_mismatch_summary()
    waiver = build_baseline_reuse_waiver(
        paired_summary=paired_summary,
        paired_rows=_minimal_paired_rows(),
        user_authorized_baseline_reuse=True,
        expected_pair_count=30,
    )
    pre_human_summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "blocked",
            "ready_to_execute": False,
            "failed_required": ["paid_execution_not_authorized"],
        },
        paired_summary=paired_summary,
        baseline_reuse_waiver=waiver,
        holdout_summary=_passing_holdout_summary(),
    )
    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "blocked",
            "ready_to_execute": False,
            "failed_required": ["paid_execution_not_authorized"],
        },
        paired_summary=paired_summary,
        baseline_reuse_waiver=waiver,
        holdout_summary=_passing_holdout_summary(),
        human_acceptance_summary=_accepted_human_summary_for(pre_human_summary),
    )

    assert summary["gate"] == "pass"
    assert summary["components"]["paired_execution_preflight"] == "blocked"
    assert summary["components"]["paired_full_gate"] == "blocked"
    assert summary["components"]["baseline_reuse_waiver"] == "pass"
    assert summary["evidence_substitutions"] == [
        "baseline_reuse_waiver_for_paired_execution_preflight",
        "baseline_reuse_waiver_for_paired_full_gate"
    ]
    assert "paired_execution_preflight_not_pass" not in summary["failed_required"]
    assert "paired_full_gate_not_pass" not in summary["failed_required"]


def test_acceptance_summary_requires_holdout_judge_receipts() -> None:
    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary={
            "clean": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "tuning_exclusion_proven": True,
            "primary_latency_percentile_ci_exclusion_proven": True,
        },
        human_acceptance="pass",
    )

    assert summary["components"]["holdout_gate"] == "blocked"
    assert "holdout_gate_not_pass" in summary["failed_required"]


def test_acceptance_summary_requires_holdout_judge_summary_schema() -> None:
    holdout_summary = _passing_holdout_summary()
    del holdout_summary["judge_summary"]["schema_version"]  # type: ignore[index]

    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=holdout_summary,
    )

    assert summary["components"]["holdout_gate"] == "blocked"
    assert "holdout_gate_not_pass" in summary["failed_required"]


def test_acceptance_summary_requires_holdout_public_overlap_proof() -> None:
    holdout_summary = _passing_holdout_summary()
    del holdout_summary["public_overlap_exclusion_proven"]
    del holdout_summary["excluded_case_set_sha256"]

    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=holdout_summary,
        human_acceptance="pass",
    )

    assert summary["components"]["holdout_gate"] == "blocked"
    assert "holdout_gate_not_pass" in summary["failed_required"]


def test_acceptance_summary_requires_holdout_real_execution_proof() -> None:
    holdout_summary = _passing_holdout_summary()
    holdout_summary["execution_mode"] = "dry_run"
    holdout_summary["executed_ab_row_count"] = 0

    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=holdout_summary,
        human_acceptance="pass",
    )

    assert summary["components"]["holdout_gate"] == "blocked"
    assert "holdout_gate_not_pass" in summary["failed_required"]


def test_acceptance_summary_requires_holdout_summary_schema_version() -> None:
    holdout_summary = _passing_holdout_summary()
    del holdout_summary["schema_version"]

    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=holdout_summary,
        human_acceptance="pass",
    )

    assert summary["components"]["holdout_gate"] == "blocked"
    assert "holdout_gate_not_pass" in summary["failed_required"]


def test_acceptance_summary_requires_holdout_ab_lane_counts() -> None:
    holdout_summary = _passing_holdout_summary()
    del holdout_summary["candidate_ab_row_count"]

    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=holdout_summary,
        human_acceptance="pass",
    )

    assert summary["components"]["holdout_gate"] == "blocked"
    assert "holdout_gate_not_pass" in summary["failed_required"]


def test_acceptance_summary_requires_holdout_ab_lane_case_set_hashes() -> None:
    holdout_summary = _passing_holdout_summary()
    del holdout_summary["candidate_ab_case_set_sha256"]

    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=holdout_summary,
        human_acceptance="pass",
    )

    assert summary["components"]["holdout_gate"] == "blocked"
    assert "holdout_gate_not_pass" in summary["failed_required"]


def test_blocked_holdout_receipt_replaces_missing_holdout_status() -> None:
    holdout = build_holdout_blocked_summary(
        reason="private_holdout_cases_missing",
        expected_min_cases=12,
    )
    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=holdout["holdout_summary"],
        human_acceptance="pass",
    )

    assert holdout["gate"] == "blocked"
    assert holdout["holdout_summary"]["holdout_case_count"] == 0
    assert "private_holdout_cases_missing" in holdout["failed_required"]
    assert summary["components"]["holdout_gate"] == "blocked"
    assert "holdout_summary_missing" not in summary["failed_required"]
    assert "holdout_gate_not_pass" in summary["failed_required"]
    assert "answer" not in json.dumps(holdout).casefold()
    assert "prompt" not in json.dumps(holdout).casefold()


def test_pending_human_acceptance_packet_replaces_missing_human_status() -> None:
    acceptance = {
        "schema_version": "phase65-acceptance-summary-v1",
        "gate": "blocked",
        "components": {
            "contract_snapshot": "pass",
            "topology_gate": "pass",
            "fault_gate": "pass",
            "recovery_gate": "pass",
            "endpoint_readiness": "pass",
            "paired_execution_preflight": "blocked",
            "paired_full_gate": "blocked",
            "baseline_reuse_waiver": "pass",
            "holdout_gate": "blocked",
            "human_acceptance": "missing",
        },
        "failed_required": ["holdout_gate_not_pass", "human_acceptance_missing"],
        "evidence_substitutions": [
            "baseline_reuse_waiver_for_paired_execution_preflight",
            "baseline_reuse_waiver_for_paired_full_gate",
        ],
    }
    packet = build_human_acceptance_packet(
        acceptance_summary=acceptance,
        reviewer_label="user",
    )
    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=_passing_holdout_summary(),
        human_acceptance_summary=packet["human_acceptance_summary"],
    )

    assert packet["gate"] == "blocked"
    assert packet["human_acceptance_summary"]["status"] == "pending_user_review"
    assert packet["human_acceptance_summary"]["acceptance_summary_sha256"]
    assert "human_acceptance_missing" not in summary["failed_required"]
    assert "human_acceptance_not_pass" in summary["failed_required"]
    assert summary["components"]["human_acceptance"] == "blocked"
    assert "answer" not in json.dumps(packet).casefold()
    assert "prompt" not in json.dumps(packet).casefold()


def test_human_acceptance_recorder_rejects_pass_when_holdout_is_still_blocked() -> None:
    packet = build_human_acceptance_packet(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "blocked",
            "components": {
                "holdout_gate": "blocked",
                "human_acceptance": "blocked",
            },
            "failed_required": ["holdout_gate_not_pass", "human_acceptance_not_pass"],
        },
        reviewer_label="user",
    )

    try:
        record_human_acceptance(
            acceptance_packet=packet,
            decision="pass",
            reviewer_label="user",
            checklist_confirmed=True,
        )
    except ValueError as exc:
        assert str(exc) == "cannot_pass_with_open_non_human_gates"
    else:
        raise AssertionError("pass decision should reject open holdout gate")


def test_human_acceptance_recorder_pass_unblocks_human_gate_when_only_human_is_open() -> None:
    acceptance = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=_passing_holdout_summary(),
        human_acceptance_summary=None,
    )
    packet = build_human_acceptance_packet(
        acceptance_summary=acceptance,
        reviewer_label="user",
    )
    receipt = record_human_acceptance(
        acceptance_packet=packet,
        current_acceptance_summary=acceptance,
        decision="pass",
        reviewer_label="user",
        checklist_confirmed=True,
    )
    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=_passing_holdout_summary(),
        human_acceptance_summary=receipt["human_acceptance_summary"],
    )

    assert receipt["gate"] == "pass"
    assert receipt["human_acceptance_summary"]["status"] == "accepted"
    assert summary["components"]["human_acceptance"] == "pass"
    assert isinstance(summary["human_acceptance_summary_sha256"], str)
    assert summary["holdout_case_set_sha256"] == "f" * 64
    assert summary["gate"] == "pass"
    assert "answer" not in json.dumps(receipt).casefold()
    assert "prompt" not in json.dumps(receipt).casefold()


def test_human_acceptance_record_must_match_current_pre_human_summary() -> None:
    stale_record = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
        "reviewer_label": "user",
        "acceptance_summary_sha256": "0" * 64,
        "review_checklist_confirmed": True,
        "decision": "pass",
        "open_non_human_gate_count": 0,
    }

    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=_passing_holdout_summary(),
        human_acceptance_summary=stale_record,
    )

    assert summary["components"]["human_acceptance"] == "blocked"
    assert summary["gate"] == "blocked"
    assert "human_acceptance_not_pass" in summary["failed_required"]


def test_human_acceptance_summary_requires_recorder_fields() -> None:
    pre_human_summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=_passing_holdout_summary(),
        human_acceptance_summary=None,
    )
    handwritten_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
        "acceptance_summary_sha256": _safe_json_sha256(pre_human_summary),
    }

    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=_passing_holdout_summary(),
        human_acceptance_summary=handwritten_summary,
    )

    assert summary["components"]["human_acceptance"] == "blocked"
    assert summary["gate"] == "blocked"
    assert "human_acceptance_not_pass" in summary["failed_required"]


def test_human_acceptance_recorder_rejects_stale_current_summary() -> None:
    acceptance = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=_passing_holdout_summary(),
        human_acceptance_summary=None,
    )
    packet = build_human_acceptance_packet(
        acceptance_summary=acceptance,
        reviewer_label="user",
    )
    stale_acceptance = {
        **acceptance,
        "next_required_actions": ["changed after packet creation"],
    }

    try:
        record_human_acceptance(
            acceptance_packet=packet,
            current_acceptance_summary=stale_acceptance,
            decision="pass",
            reviewer_label="user",
            checklist_confirmed=True,
        )
    except ValueError as exc:
        assert str(exc) == "human_acceptance_summary_mismatch"
    else:
        raise AssertionError("stale current acceptance summary should be rejected")


def test_human_acceptance_recorder_cli_emits_safe_error_without_traceback(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    packet = build_human_acceptance_packet(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "blocked",
            "components": {
                "holdout_gate": "blocked",
                "human_acceptance": "blocked",
            },
            "failed_required": ["holdout_gate_not_pass", "human_acceptance_not_pass"],
        },
        reviewer_label="user",
    )
    packet_path = tmp_path / "packet.json"
    out_path = tmp_path / "record.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "record_phase65_human_acceptance.py",
            "--acceptance-packet",
            str(packet_path),
            "--decision",
            "pass",
            "--reviewer-label",
            "user",
            "--confirm-checklist",
            "--out",
            str(out_path),
        ],
    )

    exit_code = record_human_acceptance_main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["gate"] == "blocked"
    assert payload["error_category"] == "cannot_pass_with_open_non_human_gates"
    assert not out_path.exists()
    assert "Traceback" not in captured.err
    assert "answer" not in captured.out.casefold()
    assert "prompt" not in captured.out.casefold()


def test_human_acceptance_recorder_cli_rejects_stale_current_summary(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    acceptance = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=_passing_holdout_summary(),
        human_acceptance_summary=None,
    )
    packet = build_human_acceptance_packet(
        acceptance_summary=acceptance,
        reviewer_label="user",
    )
    stale_acceptance = {
        **acceptance,
        "next_required_actions": ["changed after packet creation"],
    }
    packet_path = tmp_path / "packet.json"
    current_path = tmp_path / "current.json"
    out_path = tmp_path / "record.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    current_path.write_text(json.dumps(stale_acceptance), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "record_phase65_human_acceptance.py",
            "--acceptance-packet",
            str(packet_path),
            "--current-acceptance-summary",
            str(current_path),
            "--decision",
            "pass",
            "--reviewer-label",
            "user",
            "--confirm-checklist",
            "--out",
            str(out_path),
        ],
    )

    exit_code = record_human_acceptance_main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["gate"] == "blocked"
    assert payload["error_category"] == "human_acceptance_summary_mismatch"
    assert not out_path.exists()
    assert "Traceback" not in captured.err
    assert "answer" not in captured.out.casefold()
    assert "prompt" not in captured.out.casefold()


def test_direct_human_acceptance_pass_does_not_bypass_record_requirement() -> None:
    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=_passing_holdout_summary(),
        human_acceptance="pass",
    )

    assert summary["components"]["human_acceptance"] == "blocked"
    assert summary["gate"] == "blocked"
    assert "human_acceptance_not_pass" in summary["failed_required"]


def test_acceptance_summary_passes_only_when_every_required_gate_passes() -> None:
    pre_human_summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=_passing_holdout_summary(),
    )
    summary = build_acceptance_summary(
        contract_snapshot=_contract_snapshot(),
        topology_summary=_pass_summary("phase65-topology-v1"),
        fault_summary=_pass_summary("phase65-fault-matrix-v1"),
        recovery_summary=_pass_summary("phase65-runtime-recovery-v1"),
        endpoint_readiness_summary={
            "schema_version": "phase65-endpoint-readiness-v1",
            "gate": "pass",
            "failed_required": [],
        },
        paired_preflight_summary={
            "schema_version": "phase65-paired-preflight-v1",
            "gate": "pass",
            "ready_to_execute": True,
            "failed_required": [],
        },
        paired_summary={
            "mode": "summarize",
            "gate_decision": {
                "contract_gate": "pass",
                "quality_gate": "pass",
                "runtime_non_regression_gate": "pass",
                "phase64_latency_closure_gate": "pass",
                "phase65_acceptance": "pass",
            },
        },
        holdout_summary=_passing_holdout_summary(),
        human_acceptance_summary=_accepted_human_summary_for(pre_human_summary),
    )

    assert summary["gate"] == "pass"
    assert summary["phase65_acceptance"] == "pass"
    assert (
        summary["pre_human_acceptance_summary_sha256"]
        == _safe_json_sha256(pre_human_summary)
    )
    assert summary["holdout_case_count"] == 12
    assert summary["holdout_execution_mode"] == "real_api"
    assert summary["holdout_executed_ab_row_count"] == 24
    assert summary["holdout_baseline_ab_row_count"] == 12
    assert summary["holdout_candidate_ab_row_count"] == 12
    assert summary["holdout_case_set_sha256"] == "f" * 64
    assert summary["holdout_excluded_case_count"] == 30
    assert summary["holdout_excluded_case_set_sha256"] == "e" * 64
    assert summary["baseline_ab_case_set_sha256"] == "f" * 64
    assert summary["candidate_ab_case_set_sha256"] == "f" * 64
    assert summary["holdout_judge_receipt_contract_sha256"] == "a" * 64
    assert summary["failed_required"] == []
