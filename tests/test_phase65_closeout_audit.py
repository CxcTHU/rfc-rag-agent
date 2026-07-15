from __future__ import annotations

import json

from scripts.audit_phase65_closeout import build_phase65_closeout_audit
from scripts.prepare_phase65_holdout_intake import HOLDOUT_TEMPLATE_FIELDS
from scripts.summarize_phase65_acceptance import _safe_json_sha256


def test_closeout_audit_blocks_when_acceptance_is_not_pass() -> None:
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "blocked",
            "components": {
                "baseline_reuse_waiver": "pass",
                "holdout_gate": "blocked",
                "human_acceptance": "blocked",
            },
            "failed_required": ["holdout_gate_not_pass", "human_acceptance_not_pass"],
            "next_required_actions": [
                "resolve failed or blocked reviewer holdout evidence",
                "resolve human acceptance findings before release closeout",
            ],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-v1",
            "gate": "blocked",
            "template_is_executable": False,
            "expected_min_cases": 12,
            "next_required_actions": [
                "copy the template to the target private holdout case path and fill at least twelve unique reviewer cases"
            ],
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-packet-v1",
            "gate": "blocked",
            "human_acceptance_summary": {
                "schema_version": "phase65-human-acceptance-summary-v1",
                "status": "pending_user_review",
                "failed_required": ["holdout_gate_not_pass", "human_acceptance_not_pass"],
            },
        },
    )

    assert audit["schema_version"] == "phase65-closeout-audit-v1"
    assert audit["ready_for_closeout"] is False
    assert audit["gate"] == "blocked"
    assert audit["components"]["acceptance_summary"] == "blocked"
    assert audit["components"]["holdout_intake"] == "blocked"
    assert audit["components"]["human_acceptance_packet"] == "blocked"
    assert audit["failed_required"] == [
        "holdout_gate_not_pass",
        "human_acceptance_not_pass",
    ]
    assert any("private holdout" in action for action in audit["next_required_actions"])
    assert any("human acceptance" in action for action in audit["next_required_actions"])
    assert "answer" not in json.dumps(audit).casefold()
    assert "prompt" not in json.dumps(audit).casefold()


def test_closeout_audit_passes_only_when_acceptance_passes_and_supporting_packets_pass() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
        "reviewer_label": "user",
        "acceptance_summary_sha256": "a" * 64,
        "review_checklist_confirmed": True,
        "decision": "pass",
        "open_non_human_gate_count": 0,
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "phase65_acceptance": "pass",
            "components": {
                "contract_snapshot": "pass",
                "topology_gate": "pass",
                "fault_gate": "pass",
                "recovery_gate": "pass",
                "endpoint_readiness": "pass",
                "paired_execution_preflight": "pass",
                "paired_full_gate": "pass",
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_count": 12,
            "holdout_execution_mode": "real_api",
            "holdout_executed_ab_row_count": 24,
            "holdout_baseline_ab_row_count": 12,
            "holdout_candidate_ab_row_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "holdout_excluded_case_count": 30,
            "holdout_excluded_case_set_sha256": "e" * 64,
            "baseline_ab_case_set_sha256": "f" * 64,
            "candidate_ab_case_set_sha256": "f" * 64,
            "holdout_judge_receipt_contract_sha256": "a" * 64,
            "pre_human_acceptance_summary_sha256": "a" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "excluded_case_overlap_count": 0,
            "required_columns": list(HOLDOUT_TEMPLATE_FIELDS),
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["gate"] == "pass"
    assert audit["ready_for_closeout"] is True
    assert audit["failed_required"] == []


def test_closeout_audit_rejects_human_record_with_wrong_source_summary_hash() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
        "reviewer_label": "user",
        "acceptance_summary_sha256": "b" * 64,
        "review_checklist_confirmed": True,
        "decision": "pass",
        "open_non_human_gate_count": 0,
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "phase65_acceptance": "pass",
            "components": {
                "contract_snapshot": "pass",
                "topology_gate": "pass",
                "fault_gate": "pass",
                "recovery_gate": "pass",
                "endpoint_readiness": "pass",
                "paired_execution_preflight": "pass",
                "paired_full_gate": "pass",
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_count": 12,
            "holdout_execution_mode": "real_api",
            "holdout_executed_ab_row_count": 24,
            "holdout_baseline_ab_row_count": 12,
            "holdout_candidate_ab_row_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "holdout_excluded_case_count": 30,
            "holdout_excluded_case_set_sha256": "e" * 64,
            "baseline_ab_case_set_sha256": "f" * 64,
            "candidate_ab_case_set_sha256": "f" * 64,
            "holdout_judge_receipt_contract_sha256": "a" * 64,
            "pre_human_acceptance_summary_sha256": "a" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "excluded_case_overlap_count": 0,
            "required_columns": list(HOLDOUT_TEMPLATE_FIELDS),
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["human_acceptance_packet"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_acceptance_pass_missing_public_overlap_proof() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
        "reviewer_label": "user",
        "acceptance_summary_sha256": "a" * 64,
        "review_checklist_confirmed": True,
        "decision": "pass",
        "open_non_human_gate_count": 0,
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "phase65_acceptance": "pass",
            "components": {
                "contract_snapshot": "pass",
                "topology_gate": "pass",
                "fault_gate": "pass",
                "recovery_gate": "pass",
                "endpoint_readiness": "pass",
                "paired_execution_preflight": "pass",
                "paired_full_gate": "pass",
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_count": 12,
            "holdout_execution_mode": "real_api",
            "holdout_executed_ab_row_count": 24,
            "holdout_baseline_ab_row_count": 12,
            "holdout_candidate_ab_row_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "baseline_ab_case_set_sha256": "f" * 64,
            "candidate_ab_case_set_sha256": "f" * 64,
            "holdout_judge_receipt_contract_sha256": "a" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "excluded_case_overlap_count": 0,
            "required_columns": list(HOLDOUT_TEMPLATE_FIELDS),
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["acceptance_summary"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_acceptance_pass_missing_holdout_execution_proof() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
        "reviewer_label": "user",
        "acceptance_summary_sha256": "a" * 64,
        "review_checklist_confirmed": True,
        "decision": "pass",
        "open_non_human_gate_count": 0,
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "phase65_acceptance": "pass",
            "components": {
                "contract_snapshot": "pass",
                "topology_gate": "pass",
                "fault_gate": "pass",
                "recovery_gate": "pass",
                "endpoint_readiness": "pass",
                "paired_execution_preflight": "pass",
                "paired_full_gate": "pass",
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "baseline_ab_case_set_sha256": "f" * 64,
            "candidate_ab_case_set_sha256": "f" * 64,
            "holdout_judge_receipt_contract_sha256": "a" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "excluded_case_overlap_count": 0,
            "required_columns": list(HOLDOUT_TEMPLATE_FIELDS),
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["acceptance_summary"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_acceptance_pass_missing_holdout_judge_receipt_hash() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
        "reviewer_label": "user",
        "acceptance_summary_sha256": "a" * 64,
        "review_checklist_confirmed": True,
        "decision": "pass",
        "open_non_human_gate_count": 0,
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "phase65_acceptance": "pass",
            "components": {
                "contract_snapshot": "pass",
                "topology_gate": "pass",
                "fault_gate": "pass",
                "recovery_gate": "pass",
                "endpoint_readiness": "pass",
                "paired_execution_preflight": "pass",
                "paired_full_gate": "pass",
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_set_sha256": "f" * 64,
            "baseline_ab_case_set_sha256": "f" * 64,
            "candidate_ab_case_set_sha256": "f" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "excluded_case_overlap_count": 0,
            "required_columns": list(HOLDOUT_TEMPLATE_FIELDS),
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["acceptance_summary"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_holdout_intake_count_mismatch() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
        "reviewer_label": "user",
        "acceptance_summary_sha256": "a" * 64,
        "review_checklist_confirmed": True,
        "decision": "pass",
        "open_non_human_gate_count": 0,
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "phase65_acceptance": "pass",
            "components": {
                "contract_snapshot": "pass",
                "topology_gate": "pass",
                "fault_gate": "pass",
                "recovery_gate": "pass",
                "endpoint_readiness": "pass",
                "paired_execution_preflight": "pass",
                "paired_full_gate": "pass",
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_count": 13,
            "holdout_case_set_sha256": "f" * 64,
            "baseline_ab_case_set_sha256": "f" * 64,
            "candidate_ab_case_set_sha256": "f" * 64,
            "holdout_judge_receipt_contract_sha256": "a" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "excluded_case_overlap_count": 0,
            "required_columns": list(HOLDOUT_TEMPLATE_FIELDS),
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["holdout_intake"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_acceptance_pass_missing_holdout_lane_hashes() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
        "reviewer_label": "user",
        "acceptance_summary_sha256": "a" * 64,
        "review_checklist_confirmed": True,
        "decision": "pass",
        "open_non_human_gate_count": 0,
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "phase65_acceptance": "pass",
            "components": {
                "contract_snapshot": "pass",
                "topology_gate": "pass",
                "fault_gate": "pass",
                "recovery_gate": "pass",
                "endpoint_readiness": "pass",
                "paired_execution_preflight": "pass",
                "paired_full_gate": "pass",
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_set_sha256": "f" * 64,
            "baseline_ab_case_set_sha256": "f" * 64,
            "candidate_ab_case_set_sha256": "e" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "excluded_case_overlap_count": 0,
            "required_columns": list(HOLDOUT_TEMPLATE_FIELDS),
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["acceptance_summary"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_requires_human_acceptance_record_not_generic_pass_packet() -> None:
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "components": {
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-packet-v1",
            "gate": "pass",
            "human_acceptance_summary": {
                "schema_version": "phase65-human-acceptance-summary-v1",
                "gate": "pass",
                "status": "accepted",
            },
        },
    )

    assert audit["components"]["human_acceptance_packet"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_human_record_that_does_not_match_acceptance_summary() -> None:
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "components": {
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "human_acceptance_summary_sha256": "0" * 64,
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": {
                "schema_version": "phase65-human-acceptance-summary-v1",
                "gate": "pass",
                "status": "accepted",
            },
        },
    )

    assert audit["components"]["human_acceptance_packet"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_human_record_missing_recorder_fields() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "phase65_acceptance": "pass",
            "components": {
                "contract_snapshot": "pass",
                "topology_gate": "pass",
                "fault_gate": "pass",
                "recovery_gate": "pass",
                "endpoint_readiness": "pass",
                "paired_execution_preflight": "pass",
                "paired_full_gate": "pass",
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_set_sha256": "f" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["human_acceptance_packet"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_holdout_intake_that_does_not_match_acceptance_summary() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "components": {
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_set_sha256": "f" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "e" * 64,
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["holdout_intake"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_holdout_intake_with_too_few_cases() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "phase65_acceptance": "pass",
            "components": {
                "contract_snapshot": "pass",
                "topology_gate": "pass",
                "fault_gate": "pass",
                "recovery_gate": "pass",
                "endpoint_readiness": "pass",
                "paired_execution_preflight": "pass",
                "paired_full_gate": "pass",
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_set_sha256": "f" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 11,
            "holdout_case_set_sha256": "f" * 64,
            "failed_required": [],
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["holdout_intake"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_holdout_intake_with_overlap_count() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
        "reviewer_label": "user",
        "acceptance_summary_sha256": "a" * 64,
        "review_checklist_confirmed": True,
        "decision": "pass",
        "open_non_human_gate_count": 0,
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "phase65_acceptance": "pass",
            "components": {
                "contract_snapshot": "pass",
                "topology_gate": "pass",
                "fault_gate": "pass",
                "recovery_gate": "pass",
                "endpoint_readiness": "pass",
                "paired_execution_preflight": "pass",
                "paired_full_gate": "pass",
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_set_sha256": "f" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "excluded_case_overlap_count": 1,
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["holdout_intake"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_holdout_intake_missing_required_columns() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
        "reviewer_label": "user",
        "acceptance_summary_sha256": "a" * 64,
        "review_checklist_confirmed": True,
        "decision": "pass",
        "open_non_human_gate_count": 0,
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "phase65_acceptance": "pass",
            "components": {
                "contract_snapshot": "pass",
                "topology_gate": "pass",
                "fault_gate": "pass",
                "recovery_gate": "pass",
                "endpoint_readiness": "pass",
                "paired_execution_preflight": "pass",
                "paired_full_gate": "pass",
                "holdout_gate": "pass",
                "human_acceptance": "pass",
            },
            "holdout_case_set_sha256": "f" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
            "excluded_case_overlap_count": 0,
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["holdout_intake"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False


def test_closeout_audit_rejects_minimal_handwritten_acceptance_pass_summary() -> None:
    human_acceptance_summary = {
        "schema_version": "phase65-human-acceptance-summary-v1",
        "gate": "pass",
        "status": "accepted",
    }
    audit = build_phase65_closeout_audit(
        acceptance_summary={
            "schema_version": "phase65-acceptance-summary-v1",
            "gate": "pass",
            "holdout_case_set_sha256": "f" * 64,
            "human_acceptance_summary_sha256": _safe_json_sha256(
                human_acceptance_summary
            ),
            "failed_required": [],
            "next_required_actions": [],
        },
        holdout_intake_packet={
            "schema_version": "phase65-holdout-intake-validation-v1",
            "gate": "pass",
            "ready_to_run_holdout": True,
            "holdout_case_count": 12,
            "holdout_case_set_sha256": "f" * 64,
        },
        human_acceptance_packet={
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "pass",
            "human_acceptance_summary": human_acceptance_summary,
        },
    )

    assert audit["components"]["acceptance_summary"] == "blocked"
    assert audit["gate"] == "blocked"
    assert audit["ready_for_closeout"] is False
