"""Audit Phase 65 closeout readiness from safe receipt artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.summarize_phase65_acceptance import (
    _load_json,
    _safe_json_sha256,
    _write_json,
)
from scripts.prepare_phase65_holdout_intake import HOLDOUT_TEMPLATE_FIELDS

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def build_phase65_closeout_audit(
    *,
    acceptance_summary: Mapping[str, object],
    holdout_intake_packet: Mapping[str, object] | None = None,
    human_acceptance_packet: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if acceptance_summary.get("schema_version") != "phase65-acceptance-summary-v1":
        raise ValueError("invalid_acceptance_summary")
    components = {
        "acceptance_summary": _acceptance_summary_label(acceptance_summary),
        "holdout_intake": _holdout_intake_label(
            holdout_intake_packet,
            acceptance_summary=acceptance_summary,
        ),
        "human_acceptance_packet": _human_acceptance_record_label(
            human_acceptance_packet,
            acceptance_summary=acceptance_summary,
        ),
    }
    failed_required = _string_list(acceptance_summary.get("failed_required"))
    next_required_actions = list(
        dict.fromkeys(
            _string_list(acceptance_summary.get("next_required_actions"))
            + _string_list(
                holdout_intake_packet.get("next_required_actions")
                if isinstance(holdout_intake_packet, Mapping)
                else None
            )
            + _string_list(
                human_acceptance_packet.get("next_required_actions")
                if isinstance(human_acceptance_packet, Mapping)
                else None
            )
        )
    )
    if "holdout_gate_not_pass" in failed_required and not any(
        "private holdout" in action for action in next_required_actions
    ):
        next_required_actions.append(
            "provide private holdout cases and run baseline/candidate A/B holdout with blind judge"
        )
    if "human_acceptance_not_pass" in failed_required and not any(
        "human acceptance" in action for action in next_required_actions
    ):
        next_required_actions.append(
            "record explicit human acceptance after reviewer holdout passes"
        )

    ready = (
        components["acceptance_summary"] == "pass"
        and components["holdout_intake"] == "pass"
        and components["human_acceptance_packet"] == "pass"
        and not failed_required
    )
    return {
        "schema_version": "phase65-closeout-audit-v1",
        "gate": "pass" if ready else "blocked",
        "ready_for_closeout": ready,
        "components": components,
        "failed_required": failed_required,
        "next_required_actions": next_required_actions,
    }


def _gate_label(payload: Mapping[str, object] | None) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    gate = payload.get("gate")
    return gate if gate in {"pass", "fail", "blocked"} else "blocked"  # type: ignore[return-value]


def _acceptance_summary_label(payload: Mapping[str, object]) -> str:
    gate = _gate_label(payload)
    if gate != "pass":
        return gate
    if payload.get("phase65_acceptance") != "pass":
        return "blocked"
    if _string_list(payload.get("failed_required")):
        return "blocked"
    components = payload.get("components")
    if not isinstance(components, Mapping):
        return "blocked"
    required_pass_components = (
        "contract_snapshot",
        "topology_gate",
        "fault_gate",
        "recovery_gate",
        "endpoint_readiness",
        "holdout_gate",
        "human_acceptance",
    )
    for name in required_pass_components:
        if components.get(name) != "pass":
            return "blocked"
    holdout_case_count = payload.get("holdout_case_count")
    if not isinstance(holdout_case_count, int) or holdout_case_count < 12:
        return "blocked"
    if payload.get("holdout_execution_mode") != "real_api":
        return "blocked"
    executed_ab_row_count = payload.get("holdout_executed_ab_row_count")
    baseline_ab_row_count = payload.get("holdout_baseline_ab_row_count")
    candidate_ab_row_count = payload.get("holdout_candidate_ab_row_count")
    if (
        not isinstance(executed_ab_row_count, int)
        or not isinstance(baseline_ab_row_count, int)
        or not isinstance(candidate_ab_row_count, int)
        or executed_ab_row_count < holdout_case_count * 2
        or baseline_ab_row_count != holdout_case_count
        or candidate_ab_row_count != holdout_case_count
    ):
        return "blocked"
    holdout_case_set_sha256 = payload.get("holdout_case_set_sha256")
    if not isinstance(holdout_case_set_sha256, str) or not _SHA256.fullmatch(
        holdout_case_set_sha256
    ):
        return "blocked"
    excluded_case_count = payload.get("holdout_excluded_case_count")
    excluded_case_set_sha256 = payload.get("holdout_excluded_case_set_sha256")
    if not isinstance(excluded_case_count, int) or excluded_case_count <= 0:
        return "blocked"
    if not isinstance(
        excluded_case_set_sha256, str
    ) or not _SHA256.fullmatch(excluded_case_set_sha256):
        return "blocked"
    if payload.get("baseline_ab_case_set_sha256") != holdout_case_set_sha256:
        return "blocked"
    if payload.get("candidate_ab_case_set_sha256") != holdout_case_set_sha256:
        return "blocked"
    judge_receipt_contract_sha256 = payload.get(
        "holdout_judge_receipt_contract_sha256"
    )
    if not isinstance(
        judge_receipt_contract_sha256, str
    ) or not _SHA256.fullmatch(judge_receipt_contract_sha256):
        return "blocked"
    paired_preflight = components.get("paired_execution_preflight")
    paired_full = components.get("paired_full_gate")
    baseline_waiver = components.get("baseline_reuse_waiver")
    if paired_preflight == "pass" and paired_full == "pass":
        return "pass"
    if baseline_waiver == "pass":
        substitutions = payload.get("evidence_substitutions")
        if not isinstance(substitutions, list):
            return "blocked"
        required_substitutions = {
            "baseline_reuse_waiver_for_paired_execution_preflight",
            "baseline_reuse_waiver_for_paired_full_gate",
        }
        if not required_substitutions.issubset(
            {item for item in substitutions if isinstance(item, str)}
        ):
            return "blocked"
        return "pass"
    return "blocked"


def _holdout_intake_label(
    payload: Mapping[str, object] | None,
    *,
    acceptance_summary: Mapping[str, object],
) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    if _gate_label(payload) != "pass":
        return _gate_label(payload)
    if payload.get("schema_version") != "phase65-holdout-intake-validation-v1":
        return "blocked"
    if payload.get("ready_to_run_holdout") is not True:
        return "blocked"
    holdout_case_count = payload.get("holdout_case_count")
    if not isinstance(holdout_case_count, int) or holdout_case_count < 12:
        return "blocked"
    expected_count = acceptance_summary.get("holdout_case_count")
    if not isinstance(expected_count, int) or holdout_case_count != expected_count:
        return "blocked"
    if payload.get("excluded_case_overlap_count") != 0:
        return "blocked"
    if payload.get("required_columns") != list(HOLDOUT_TEMPLATE_FIELDS):
        return "blocked"
    expected_digest = acceptance_summary.get("holdout_case_set_sha256")
    if not isinstance(expected_digest, str):
        return "blocked"
    if payload.get("holdout_case_set_sha256") != expected_digest:
        return "blocked"
    return "pass"


def _human_acceptance_record_label(
    payload: Mapping[str, object] | None,
    *,
    acceptance_summary: Mapping[str, object],
) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    if payload.get("schema_version") != "phase65-human-acceptance-record-v1":
        return "blocked"
    if payload.get("gate") != "pass":
        return _gate_label(payload)
    summary = payload.get("human_acceptance_summary")
    if not isinstance(summary, Mapping):
        return "blocked"
    if summary.get("schema_version") != "phase65-human-acceptance-summary-v1":
        return "blocked"
    if summary.get("gate") != "pass" or summary.get("status") != "accepted":
        return "blocked"
    if summary.get("decision") != "pass":
        return "blocked"
    if summary.get("review_checklist_confirmed") is not True:
        return "blocked"
    if summary.get("open_non_human_gate_count") != 0:
        return "blocked"
    reviewer_label = summary.get("reviewer_label")
    if not isinstance(reviewer_label, str) or not reviewer_label:
        return "blocked"
    source_summary_digest = summary.get("acceptance_summary_sha256")
    if not isinstance(source_summary_digest, str) or not _SHA256.fullmatch(
        source_summary_digest
    ):
        return "blocked"
    expected_source_digest = acceptance_summary.get(
        "pre_human_acceptance_summary_sha256"
    )
    if (
        not isinstance(expected_source_digest, str)
        or source_summary_digest != expected_source_digest
    ):
        return "blocked"
    expected_digest = acceptance_summary.get("human_acceptance_summary_sha256")
    if not isinstance(expected_digest, str):
        return "blocked"
    if _safe_json_sha256(summary) != expected_digest:
        return "blocked"
    return "pass"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Phase 65 closeout readiness from safe receipts."
    )
    parser.add_argument("--acceptance-summary", type=Path, required=True)
    parser.add_argument("--holdout-intake", type=Path)
    parser.add_argument("--human-acceptance-packet", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    acceptance = _load_json(args.acceptance_summary)
    if acceptance is None:
        raise ValueError("acceptance_summary_required")
    audit = build_phase65_closeout_audit(
        acceptance_summary=acceptance,
        holdout_intake_packet=_load_json(args.holdout_intake),
        human_acceptance_packet=_load_json(args.human_acceptance_packet),
    )
    _write_json(args.out, audit)
    print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
    return 0 if audit["gate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
