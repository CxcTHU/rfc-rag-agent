"""Build a safe Phase 65 acceptance evidence summary.

The summary is intentionally fail-closed.  It reports gate/status labels and
bounded failure categories only; it never persists prompts, answers, evidence
text, provider payloads, credentials, or private logs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal


GateStatus = Literal["pass", "fail", "blocked", "missing"]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
JUDGE_DIMENSIONS = ("completion", "accuracy", "citation_support", "overall_quality")
_BASELINE_REUSE_ALLOWED_BLOCKERS = ("evaluator_sha256_mismatch",)


def build_acceptance_summary(
    *,
    contract_snapshot: Mapping[str, object] | None,
    topology_summary: Mapping[str, object] | None,
    fault_summary: Mapping[str, object] | None,
    recovery_summary: Mapping[str, object] | None,
    endpoint_readiness_summary: Mapping[str, object] | None,
    paired_preflight_summary: Mapping[str, object] | None,
    paired_summary: Mapping[str, object] | None,
    baseline_reuse_waiver: Mapping[str, object] | None = None,
    holdout_summary: Mapping[str, object] | None = None,
    human_acceptance_summary: Mapping[str, object] | None = None,
    human_acceptance: str | None = None,
) -> dict[str, object]:
    paired_status = _paired_summary_status(paired_summary)
    waiver_status = _baseline_reuse_waiver_status(
        baseline_reuse_waiver,
        paired_summary=paired_summary,
        paired_status=paired_status,
    )
    components_without_human: dict[str, GateStatus] = {
        "contract_snapshot": _contract_status(contract_snapshot),
        "topology_gate": _gate_status(topology_summary),
        "fault_gate": _gate_status(fault_summary),
        "recovery_gate": _gate_status(recovery_summary),
        "endpoint_readiness": _endpoint_readiness_status(endpoint_readiness_summary),
        "paired_execution_preflight": _paired_preflight_status(paired_preflight_summary),
        "paired_full_gate": paired_status,
        "baseline_reuse_waiver": waiver_status,
        "holdout_gate": _holdout_status(holdout_summary),
    }
    substitution_active = waiver_status == "pass" and (
        paired_status != "pass"
        or components_without_human["paired_execution_preflight"] != "pass"
    )
    pre_human_components = {
        **components_without_human,
        "human_acceptance": _human_acceptance_status(None),
    }
    pre_human_summary = _build_acceptance_summary_payload(
        pre_human_components,
        substitution_active=substitution_active,
    )
    _attach_holdout_proof_hashes(
        pre_human_summary,
        holdout_status=components_without_human["holdout_gate"],
        holdout_summary=holdout_summary,
    )
    components = {
        **components_without_human,
        "human_acceptance": _human_acceptance_status(
            human_acceptance,
            human_acceptance_summary=human_acceptance_summary,
            expected_acceptance_summary_sha256=_safe_json_sha256(pre_human_summary),
        ),
    }
    summary = _build_acceptance_summary_payload(
        components,
        substitution_active=substitution_active,
    )
    if (
        components["human_acceptance"] == "pass"
        and isinstance(human_acceptance_summary, Mapping)
    ):
        summary["pre_human_acceptance_summary_sha256"] = _safe_json_sha256(
            pre_human_summary
        )
        summary["human_acceptance_summary_sha256"] = _safe_json_sha256(
            human_acceptance_summary
        )
    _attach_holdout_proof_hashes(
        summary,
        holdout_status=components["holdout_gate"],
        holdout_summary=holdout_summary,
    )
    return summary


def _attach_holdout_proof_hashes(
    summary: dict[str, object],
    *,
    holdout_status: GateStatus,
    holdout_summary: Mapping[str, object] | None,
) -> None:
    if holdout_status != "pass" or not isinstance(holdout_summary, Mapping):
        return
    holdout_case_count = holdout_summary.get("holdout_case_count")
    if isinstance(holdout_case_count, int) and holdout_case_count >= 12:
        summary["holdout_case_count"] = holdout_case_count
    if holdout_summary.get("execution_mode") == "real_api":
        summary["holdout_execution_mode"] = "real_api"
    for source, target in (
        ("executed_ab_row_count", "holdout_executed_ab_row_count"),
        ("baseline_ab_row_count", "holdout_baseline_ab_row_count"),
        ("candidate_ab_row_count", "holdout_candidate_ab_row_count"),
    ):
        value = holdout_summary.get(source)
        if isinstance(value, int) and value >= 0:
            summary[target] = value
    holdout_case_set_sha256 = holdout_summary.get("holdout_case_set_sha256")
    if isinstance(holdout_case_set_sha256, str) and _SHA256.fullmatch(
        holdout_case_set_sha256
    ):
        summary["holdout_case_set_sha256"] = holdout_case_set_sha256
    excluded_case_count = holdout_summary.get("excluded_case_count")
    if isinstance(excluded_case_count, int) and excluded_case_count > 0:
        summary["holdout_excluded_case_count"] = excluded_case_count
    excluded_case_set_sha256 = holdout_summary.get("excluded_case_set_sha256")
    if isinstance(excluded_case_set_sha256, str) and _SHA256.fullmatch(
        excluded_case_set_sha256
    ):
        summary["holdout_excluded_case_set_sha256"] = excluded_case_set_sha256
    for field in ("baseline_ab_case_set_sha256", "candidate_ab_case_set_sha256"):
        value = holdout_summary.get(field)
        if isinstance(value, str) and _SHA256.fullmatch(value):
            summary[field] = value
    judge_summary = holdout_summary.get("judge_summary")
    if isinstance(judge_summary, Mapping):
        receipt_contract_sha256 = judge_summary.get("receipt_contract_sha256")
        if isinstance(receipt_contract_sha256, str) and _SHA256.fullmatch(
            receipt_contract_sha256
        ):
            summary["holdout_judge_receipt_contract_sha256"] = (
                receipt_contract_sha256
            )


def _build_acceptance_summary_payload(
    components: Mapping[str, GateStatus],
    *,
    substitution_active: bool,
) -> dict[str, object]:
    failed_required = _failed_required(
        components,
        baseline_reuse_substitutes_paired_evidence=substitution_active,
    )
    phase65_acceptance = "pass" if not failed_required else "blocked"
    summary: dict[str, object] = {
        "schema_version": "phase65-acceptance-summary-v1",
        "gate": phase65_acceptance,
        "phase65_acceptance": phase65_acceptance,
        "components": components,
        "failed_required": failed_required,
        "next_required_actions": _next_required_actions(failed_required),
    }
    if substitution_active:
        summary["evidence_substitutions"] = [
            "baseline_reuse_waiver_for_paired_execution_preflight",
            "baseline_reuse_waiver_for_paired_full_gate"
        ]
    return summary


def build_baseline_reuse_waiver(
    *,
    paired_summary: Mapping[str, object] | None,
    paired_rows: Sequence[Mapping[str, object]],
    user_authorized_baseline_reuse: bool,
    expected_pair_count: int,
    scope: str = "phase65_candidate_targeted_followup_repair_only",
) -> dict[str, object]:
    """Build a narrow waiver for reusing a completed baseline run.

    The waiver is intentionally not a formal paired A/B pass.  It can only
    substitute the required paired-full component when the paired summary is
    blocked solely by the evaluator hash mismatch caused by targeted candidate
    rerun/reuse, and row-level baseline/candidate evidence is clean and aligned.
    """

    failed_required: list[str] = []
    if not user_authorized_baseline_reuse:
        failed_required.append("baseline_reuse_not_user_authorized")
    if not isinstance(expected_pair_count, int) or expected_pair_count <= 0:
        failed_required.append("expected_pair_count_invalid")
    if not isinstance(scope, str) or not scope:
        failed_required.append("scope_missing")

    summary_ok, summary_failed = _baseline_reuse_summary_checks(
        paired_summary,
        expected_pair_count=expected_pair_count,
    )
    if not summary_ok:
        failed_required.extend(summary_failed)

    row_report = _baseline_reuse_row_report(
        paired_rows,
        expected_pair_count=expected_pair_count,
    )
    failed_required.extend(str(item) for item in row_report["failed_required"])
    failed_required = list(dict.fromkeys(failed_required))
    paired_summary_sha256 = (
        _safe_json_sha256(paired_summary) if isinstance(paired_summary, Mapping) else None
    )
    gate = "pass" if not failed_required else "blocked"
    return {
        "schema_version": "phase65-baseline-reuse-waiver-v1",
        "gate": gate,
        "substitutes_paired_full_gate": gate == "pass",
        "scope": scope,
        "user_authorized_baseline_reuse": bool(user_authorized_baseline_reuse),
        "allowed_summary_blockers": list(_BASELINE_REUSE_ALLOWED_BLOCKERS),
        "paired_summary_sha256": paired_summary_sha256,
        "paired_row_count": len(paired_rows),
        "paired_case_run_count": row_report["paired_case_run_count"],
        "baseline_pair_count": row_report["baseline_pair_count"],
        "candidate_pair_count": row_report["candidate_pair_count"],
        "failed_required": failed_required,
    }


def _baseline_reuse_summary_checks(
    paired_summary: Mapping[str, object] | None,
    *,
    expected_pair_count: int,
) -> tuple[bool, list[str]]:
    failed_required: list[str] = []
    if not isinstance(paired_summary, Mapping):
        return False, ["paired_summary_missing"]
    decision = paired_summary.get("gate_decision")
    if not isinstance(decision, Mapping):
        return False, ["paired_summary_gate_decision_missing"]
    if decision.get("phase65_acceptance") != "blocked":
        failed_required.append("paired_summary_not_blocked")
    reasons = _string_set(decision.get("reasons"))
    manifest_comparison = _string_set(paired_summary.get("manifest_comparison"))
    allowed = set(_BASELINE_REUSE_ALLOWED_BLOCKERS)
    if reasons != allowed or manifest_comparison != allowed:
        failed_required.append("paired_summary_not_limited_to_evaluator_mismatch")
    metrics = decision.get("metrics")
    paired_row_count = (
        metrics.get("paired_row_count") if isinstance(metrics, Mapping) else None
    )
    if paired_row_count != expected_pair_count:
        failed_required.append("paired_summary_pair_count_mismatch")
    rows = paired_summary.get("rows")
    if isinstance(rows, int) and rows != expected_pair_count * 2:
        failed_required.append("paired_summary_row_count_mismatch")
    return not failed_required, failed_required


def _baseline_reuse_row_report(
    paired_rows: Sequence[Mapping[str, object]],
    *,
    expected_pair_count: int,
) -> dict[str, object]:
    failed_required: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    baseline_keys: set[tuple[str, str]] = set()
    candidate_keys: set[tuple[str, str]] = set()
    for row in paired_rows:
        variant = _clean_string(row.get("variant"))
        case_id = _clean_string(row.get("case_id"))
        run = _clean_string(row.get("run"))
        if variant not in {"baseline", "candidate"} or not case_id or not run:
            failed_required.append("paired_row_identity_invalid")
            continue
        variant_key = (variant, case_id, run)
        if variant_key in seen:
            failed_required.append("paired_row_duplicate")
        seen.add(variant_key)
        case_run_key = (case_id, run)
        if variant == "baseline":
            baseline_keys.add(case_run_key)
        else:
            candidate_keys.add(case_run_key)
        if _truthy(row.get("ok")) is not True:
            failed_required.append(f"{variant}_row_not_ok")
        error_category = _clean_string(row.get("error_category"))
        if error_category:
            failed_required.append(f"{variant}_error_category_present")
        http_status = _clean_string(row.get("http_status"))
        if http_status and http_status != "200":
            failed_required.append(f"{variant}_http_status_not_200")
        cold_receipt = _clean_string(row.get("cold_cache_receipt_status"))
        if cold_receipt and cold_receipt != "valid":
            failed_required.append(f"{variant}_cold_receipt_invalid")
        replay_count = _clean_string(row.get("completed_tool_replay_count"))
        if replay_count and replay_count != "0":
            failed_required.append(f"{variant}_completed_tool_replay_present")

    if baseline_keys != candidate_keys:
        failed_required.append("paired_case_run_alignment_mismatch")
    if len(baseline_keys) != expected_pair_count:
        failed_required.append("baseline_pair_count_mismatch")
    if len(candidate_keys) != expected_pair_count:
        failed_required.append("candidate_pair_count_mismatch")
    if len(paired_rows) != expected_pair_count * 2:
        failed_required.append("paired_row_count_mismatch")
    return {
        "paired_case_run_count": len(baseline_keys & candidate_keys),
        "baseline_pair_count": len(baseline_keys),
        "candidate_pair_count": len(candidate_keys),
        "failed_required": list(dict.fromkeys(failed_required)),
    }


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _clean_string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _truthy(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return None


def _safe_json_sha256(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _contract_status(snapshot: Mapping[str, object] | None) -> GateStatus:
    if not snapshot:
        return "missing"
    required_hashes = (
        "agent_request_schema_sha256",
        "agent_response_schema_sha256",
        "tool_schema_sha256",
        "sse_fixture_sha256",
        "checkpoint_schema_sha256",
    )
    if snapshot.get("schema_version") != "phase65-contract-v1":
        return "blocked"
    if any(not isinstance(snapshot.get(field), str) or not _SHA256.fullmatch(str(snapshot.get(field))) for field in required_hashes):
        return "blocked"
    names = snapshot.get("runtime_event_names")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        return "blocked"
    return "pass"


def _gate_status(summary: Mapping[str, object] | None) -> GateStatus:
    if not summary:
        return "missing"
    gate = summary.get("gate")
    return gate if gate in {"pass", "fail", "blocked"} else "blocked"  # type: ignore[return-value]


def _paired_preflight_status(summary: Mapping[str, object] | None) -> GateStatus:
    if not summary:
        return "missing"
    if summary.get("schema_version") != "phase65-paired-preflight-v1":
        return "blocked"
    if summary.get("gate") == "pass" and summary.get("ready_to_execute") is True:
        return "pass"
    return "blocked"


def _endpoint_readiness_status(summary: Mapping[str, object] | None) -> GateStatus:
    if not summary:
        return "missing"
    if summary.get("schema_version") != "phase65-endpoint-readiness-v1":
        return "blocked"
    return "pass" if summary.get("gate") == "pass" else "blocked"


def _paired_summary_status(summary: Mapping[str, object] | None) -> GateStatus:
    if not summary:
        return "missing"
    decision = summary.get("gate_decision")
    if not isinstance(decision, Mapping):
        return "blocked"
    required = (
        "contract_gate",
        "quality_gate",
        "runtime_non_regression_gate",
        "phase64_latency_closure_gate",
        "phase65_acceptance",
    )
    if all(decision.get(field) == "pass" for field in required):
        return "pass"
    if any(decision.get(field) == "fail" for field in required):
        return "fail"
    return "blocked"


def _baseline_reuse_waiver_status(
    waiver: Mapping[str, object] | None,
    *,
    paired_summary: Mapping[str, object] | None,
    paired_status: GateStatus,
) -> GateStatus:
    if paired_status == "pass":
        return "pass"
    if not waiver:
        return "missing"
    if waiver.get("schema_version") != "phase65-baseline-reuse-waiver-v1":
        return "blocked"
    if waiver.get("gate") != "pass":
        return "blocked"
    if waiver.get("substitutes_paired_full_gate") is not True:
        return "blocked"
    if waiver.get("user_authorized_baseline_reuse") is not True:
        return "blocked"
    if waiver.get("allowed_summary_blockers") != list(_BASELINE_REUSE_ALLOWED_BLOCKERS):
        return "blocked"
    if waiver.get("failed_required") != []:
        return "blocked"
    digest = waiver.get("paired_summary_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        return "blocked"
    if isinstance(paired_summary, Mapping) and digest != _safe_json_sha256(paired_summary):
        return "blocked"
    for field in ("paired_case_run_count", "baseline_pair_count", "candidate_pair_count"):
        if not isinstance(waiver.get(field), int) or int(waiver.get(field)) <= 0:
            return "blocked"
    if waiver.get("baseline_pair_count") != waiver.get("candidate_pair_count"):
        return "blocked"
    return "pass"


def _holdout_status(summary: Mapping[str, object] | None) -> GateStatus:
    if not summary:
        return "missing"
    count = summary.get("holdout_case_count")
    fingerprint = summary.get("holdout_case_set_sha256")
    executed_ab_row_count = summary.get("executed_ab_row_count")
    baseline_ab_row_count = summary.get("baseline_ab_row_count")
    candidate_ab_row_count = summary.get("candidate_ab_row_count")
    baseline_ab_case_set_sha256 = summary.get("baseline_ab_case_set_sha256")
    candidate_ab_case_set_sha256 = summary.get("candidate_ab_case_set_sha256")
    excluded_count = summary.get("excluded_case_count")
    excluded_fingerprint = summary.get("excluded_case_set_sha256")
    judge_summary = summary.get("judge_summary")
    if summary.get("schema_version") != "phase65-holdout-summary-v1":
        return "blocked"
    execution_shape_ok = (
        summary.get("clean") is True
        and isinstance(count, int)
        and count >= 12
        and isinstance(fingerprint, str)
        and _SHA256.fullmatch(fingerprint)
        and summary.get("tuning_exclusion_proven") is True
        and summary.get("primary_latency_percentile_ci_exclusion_proven") is True
    )
    public_overlap_proof_ok = (
        summary.get("public_overlap_exclusion_proven") is True
        and isinstance(excluded_count, int)
        and excluded_count > 0
        and isinstance(excluded_fingerprint, str)
        and _SHA256.fullmatch(excluded_fingerprint)
    )
    real_execution_proof_ok = (
        summary.get("execution_mode") == "real_api"
        and isinstance(executed_ab_row_count, int)
        and isinstance(baseline_ab_row_count, int)
        and isinstance(candidate_ab_row_count, int)
        and isinstance(count, int)
        and executed_ab_row_count >= count * 2
        and baseline_ab_row_count == count
        and candidate_ab_row_count == count
        and baseline_ab_case_set_sha256 == fingerprint
        and candidate_ab_case_set_sha256 == fingerprint
    )
    required_shape_ok = (
        execution_shape_ok and public_overlap_proof_ok and real_execution_proof_ok
    )
    if required_shape_ok and _holdout_judge_summary_passes(
        judge_summary,
        holdout_case_count=count,
        holdout_case_set_sha256=fingerprint,
    ):
        return "pass"
    if required_shape_ok or execution_shape_ok:
        return "blocked"
    return "fail" if isinstance(count, int) and count > 0 else "blocked"


def _holdout_judge_summary_passes(
    judge_summary: object,
    *,
    holdout_case_count: int,
    holdout_case_set_sha256: str,
) -> bool:
    if not isinstance(judge_summary, Mapping):
        return False
    if judge_summary.get("schema_version") != "phase65-judge-summary-v1":
        return False
    if judge_summary.get("paired_count") != holdout_case_count:
        return False
    if judge_summary.get("judge_expected_pairs") != holdout_case_count:
        return False
    if judge_summary.get("case_set_sha256") != holdout_case_set_sha256:
        return False
    receipt_contract_sha256 = judge_summary.get("receipt_contract_sha256")
    if not isinstance(receipt_contract_sha256, str) or not _SHA256.fullmatch(
        receipt_contract_sha256
    ):
        return False
    for dimension in JUDGE_DIMENSIONS:
        try:
            lower_bound = float(judge_summary[f"{dimension}_lower_bound"])
        except (KeyError, TypeError, ValueError):
            return False
        if not math.isfinite(lower_bound) or lower_bound < -0.05:
            return False
    return True


def _human_acceptance_status(
    value: str | None,
    *,
    human_acceptance_summary: Mapping[str, object] | None = None,
    expected_acceptance_summary_sha256: str | None = None,
) -> GateStatus:
    if value is None:
        if human_acceptance_summary is None:
            return "missing"
        if (
            human_acceptance_summary.get("schema_version")
            != "phase65-human-acceptance-summary-v1"
        ):
            return "blocked"
        if human_acceptance_summary.get("gate") == "pass":
            if (
                expected_acceptance_summary_sha256 is None
                or human_acceptance_summary.get("acceptance_summary_sha256")
                != expected_acceptance_summary_sha256
            ):
                return "blocked"
            if human_acceptance_summary.get("status") != "accepted":
                return "blocked"
            if human_acceptance_summary.get("decision") != "pass":
                return "blocked"
            if human_acceptance_summary.get("review_checklist_confirmed") is not True:
                return "blocked"
            if human_acceptance_summary.get("open_non_human_gate_count") != 0:
                return "blocked"
            reviewer_label = human_acceptance_summary.get("reviewer_label")
            if not isinstance(reviewer_label, str) or not reviewer_label:
                return "blocked"
            return "pass"
        return "blocked"
    if value == "pass":
        return "blocked"
    return "fail"


def _failed_required(
    components: Mapping[str, GateStatus],
    *,
    baseline_reuse_substitutes_paired_evidence: bool = False,
) -> list[str]:
    return [
        _failed_required_reason(name, status)
        for name, status in components.items()
        if status != "pass"
        and not (
            baseline_reuse_substitutes_paired_evidence
            and name in {"paired_execution_preflight", "paired_full_gate"}
        )
    ]


def _failed_required_reason(name: str, status: GateStatus) -> str:
    if name == "paired_full_gate":
        return (
            "paired_full_summary_missing"
            if status == "missing"
            else "paired_full_gate_not_pass"
        )
    if name == "holdout_gate":
        return (
            "holdout_summary_missing"
            if status == "missing"
            else "holdout_gate_not_pass"
        )
    if name == "human_acceptance":
        return (
            "human_acceptance_missing"
            if status == "missing"
            else "human_acceptance_not_pass"
        )
    if name == "baseline_reuse_waiver":
        return (
            "baseline_reuse_waiver_missing"
            if status == "missing"
            else "baseline_reuse_waiver_not_pass"
        )
    return {
        "contract_snapshot": "contract_snapshot_not_pass",
        "topology_gate": "topology_gate_not_pass",
        "fault_gate": "fault_gate_not_pass",
        "recovery_gate": "recovery_gate_not_pass",
        "endpoint_readiness": "endpoint_readiness_not_pass",
        "paired_execution_preflight": "paired_execution_preflight_not_pass",
    }[name]


def _next_required_actions(failed_required: list[str]) -> list[str]:
    actions: list[str] = []
    if "paired_execution_preflight_not_pass" in failed_required:
        actions.append("produce complete cold baseline/candidate manifests and explicit human approval before paired execution")
    if "endpoint_readiness_not_pass" in failed_required:
        actions.append("make baseline/candidate endpoints expose readable contract readiness with distinct identities")
    if "paired_full_summary_missing" in failed_required:
        actions.append("run approved paired A/B plus blind judge and summarize four independent gate decisions")
    if "paired_full_gate_not_pass" in failed_required:
        actions.append("resolve blocked paired A/B summary before claiming full Phase 65 acceptance")
    if "baseline_reuse_waiver_missing" in failed_required:
        actions.append("provide an explicit baseline reuse waiver or rerun the paired A/B from scratch")
    if "baseline_reuse_waiver_not_pass" in failed_required:
        actions.append("fix the baseline reuse waiver evidence or rerun the paired A/B from scratch")
    if "holdout_summary_missing" in failed_required:
        actions.append("run reviewer holdout evidence using safe projection only")
    if "holdout_gate_not_pass" in failed_required:
        actions.append("resolve failed or blocked reviewer holdout evidence")
    if "human_acceptance_missing" in failed_required:
        actions.append("record explicit user human acceptance after UI/API review")
    if "human_acceptance_not_pass" in failed_required:
        actions.append("resolve human acceptance findings before release closeout")
    return actions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize Phase 65 acceptance evidence.")
    parser.add_argument("--contract-snapshot", type=Path)
    parser.add_argument("--topology-summary", type=Path)
    parser.add_argument("--fault-summary", type=Path)
    parser.add_argument("--recovery-summary", type=Path)
    parser.add_argument("--endpoint-readiness-summary", type=Path)
    parser.add_argument("--paired-preflight-summary", type=Path)
    parser.add_argument("--paired-summary", type=Path)
    parser.add_argument("--baseline-reuse-waiver", type=Path)
    parser.add_argument("--holdout-summary", type=Path)
    parser.add_argument("--human-acceptance-summary", type=Path)
    parser.add_argument("--human-acceptance", choices=("fail",))
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paired_preflight_parent = _load_json(args.paired_preflight_summary)
    paired_preflight = (
        paired_preflight_parent.get("paired_execution_preflight")
        if isinstance(paired_preflight_parent, Mapping)
        else None
    )
    summary = build_acceptance_summary(
        contract_snapshot=_load_json(args.contract_snapshot),
        topology_summary=_load_json(args.topology_summary),
        fault_summary=_load_json(args.fault_summary),
        recovery_summary=_load_json(args.recovery_summary),
        endpoint_readiness_summary=_extract_endpoint_readiness(
            _load_json(args.endpoint_readiness_summary)
        ),
        paired_preflight_summary=paired_preflight if isinstance(paired_preflight, Mapping) else paired_preflight_parent,
        paired_summary=_load_json(args.paired_summary),
        baseline_reuse_waiver=_load_json(args.baseline_reuse_waiver),
        holdout_summary=_extract_holdout_summary(_load_json(args.holdout_summary)),
        human_acceptance_summary=_extract_human_acceptance_summary(
            _load_json(args.human_acceptance_summary)
        ),
        human_acceptance=args.human_acceptance,
    )
    _write_json(args.out, summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["gate"] == "pass" else 1


def _load_json(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid_json:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid_json:{path}")
    return payload


def _load_csv_rows(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _extract_holdout_summary(payload: Mapping[str, object] | None) -> Mapping[str, object] | None:
    if payload is None:
        return None
    candidate = payload.get("holdout_summary", payload)
    return candidate if isinstance(candidate, Mapping) else None


def _extract_endpoint_readiness(payload: Mapping[str, object] | None) -> Mapping[str, object] | None:
    if payload is None:
        return None
    candidate = payload.get("endpoint_readiness", payload)
    return candidate if isinstance(candidate, Mapping) else None


def _extract_human_acceptance_summary(payload: Mapping[str, object] | None) -> Mapping[str, object] | None:
    if payload is None:
        return None
    candidate = payload.get("human_acceptance_summary", payload)
    return candidate if isinstance(candidate, Mapping) else None


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(f"{encoded}\n")
        temporary = Path(stream.name)
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
