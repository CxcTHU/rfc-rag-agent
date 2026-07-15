"""Comparable manifests and fail-closed release decisions for Phase 65."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from scripts.judge_phase65_agent_gate import (
    JUDGE_DIMENSIONS,
    JudgeReceiptContract,
    canonical_judge_receipt_contract_sha256,
    summarize_judge_rows,
    validate_safe_judge_rows,
)
from scripts.phase65_gate_manifest import AgentGateManifest


GateStatus = Literal["pass", "fail", "blocked"]
_MATCHED_MANIFEST_FIELDS = (
    "schema_version",
    "evaluator_sha256",
    "case_set_sha256",
    "prompt_sha256",
    "tool_schema_sha256",
    "corpus_fingerprint",
    "index_fingerprint",
    "provider_models",
    "judge_receipt_contract_sha256",
    "cache_policy",
    "environment_class",
    "expected_rows",
)
_FINGERPRINT_FIELDS = (
    "scoped_content_sha256",
    "evaluator_sha256",
    "case_set_sha256",
    "prompt_sha256",
    "tool_schema_sha256",
    "corpus_fingerprint",
    "index_fingerprint",
    "endpoint_identity_sha256",
    "judge_receipt_contract_sha256",
)
_SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ManifestComparison:
    comparable: bool
    violations: tuple[str, ...]
    expected_rows: int | None = None
    case_set_sha256: str | None = None
    judge_receipt_contract_sha256: str | None = None


@dataclass(frozen=True)
class GateDecision:
    contract_gate: GateStatus
    quality_gate: GateStatus
    runtime_non_regression_gate: GateStatus
    phase64_latency_closure_gate: GateStatus
    phase65_acceptance: GateStatus
    reasons: tuple[str, ...]
    metrics: dict[str, float | int | bool | None]


def compare_manifests(
    baseline: AgentGateManifest, candidate: AgentGateManifest
) -> ManifestComparison:
    """Permit only run/worktree identity differences between complete cold runs."""
    violations: list[str] = []
    for side, manifest, expected_variant in (
        ("baseline", baseline, "baseline"),
        ("candidate", candidate, "candidate"),
    ):
        if manifest.variant != expected_variant:
            violations.append(f"{side}_variant_invalid")
        if (
            manifest.status != "complete"
            or manifest.expected_rows <= 0
            or manifest.completed_rows != manifest.expected_rows
        ):
            violations.append(f"{side}_manifest_incomplete")
        if manifest.cache_policy != "cold":
            violations.append(f"{side}_cache_policy_not_cold")
        for field in _FINGERPRINT_FIELDS:
            value = getattr(manifest, field)
            if not isinstance(value, str) or not value or (
                field.endswith("_sha256") and not _SHA256_PATTERN.fullmatch(value)
            ):
                violations.append(f"{side}_{field}_missing")
        if not manifest.provider_models:
            violations.append(f"{side}_provider_models_missing")

    for field in _MATCHED_MANIFEST_FIELDS:
        if getattr(baseline, field) != getattr(candidate, field):
            violations.append(f"{field}_mismatch")
    # The field is lane-local: a credible A/B comparison requires two separate
    # deployed endpoint identities, not the same identity copied into both
    # manifests.  Each value was fetched from its own lane before manifest write.
    if baseline.endpoint_identity_sha256 == candidate.endpoint_identity_sha256:
        violations.append("endpoint_identity_not_distinct")
    return ManifestComparison(
        comparable=not violations,
        violations=tuple(violations),
        expected_rows=baseline.expected_rows if not violations else None,
        case_set_sha256=baseline.case_set_sha256 if not violations else None,
        judge_receipt_contract_sha256=(
            baseline.judge_receipt_contract_sha256 if not violations else None
        ),
    )


def build_paired_execution_preflight(
    *,
    baseline_manifest: AgentGateManifest,
    candidate_manifest: AgentGateManifest,
    contract_gate: GateStatus,
    topology_gate: GateStatus,
    fault_gate: GateStatus,
    paid_execution_authorized: bool,
) -> dict[str, object]:
    """Summarize whether the paid paired A/B lane is allowed to start.

    This is intentionally stricter than a dry-run manifest: it requires the two
    lanes to already be comparable cold-run manifests with distinct endpoint
    identities, and it records missing authorization as a required blocker.  It
    emits only gate/status labels and safe manifest fingerprints.
    """

    failed_required: list[str] = list(
        compare_manifests(baseline_manifest, candidate_manifest).violations
    )
    for name, value in (
        ("contract", contract_gate),
        ("topology", topology_gate),
        ("fault", fault_gate),
    ):
        if value != "pass":
            failed_required.append(f"{name}_gate_not_pass")
    if not paid_execution_authorized:
        failed_required.append("paid_execution_not_authorized")

    failed_required = list(dict.fromkeys(failed_required))
    return {
        "schema_version": "phase65-paired-preflight-v1",
        "gate": "pass" if not failed_required else "blocked",
        "ready_to_execute": not failed_required,
        "failed_required": failed_required,
        "components": {
            "manifest_comparison": "pass" if not compare_manifests(baseline_manifest, candidate_manifest).violations else "blocked",
            "contract_gate": contract_gate,
            "topology_gate": topology_gate,
            "fault_gate": fault_gate,
            "paid_execution_authorized": bool(paid_execution_authorized),
        },
        "baseline_endpoint_identity_sha256": baseline_manifest.endpoint_identity_sha256,
        "candidate_endpoint_identity_sha256": candidate_manifest.endpoint_identity_sha256,
    }


def build_phase65_gate_decision(
    *,
    paired_rows: Sequence[Mapping[str, object]],
    manifest_comparison: ManifestComparison,
    judge_summary: Mapping[str, object] | None,
    holdout_summary: Mapping[str, object] | None,
    judge_rows: Sequence[Mapping[str, object]] | None = None,
    judge_receipt_contract: JudgeReceiptContract | None = None,
) -> GateDecision:
    """Keep contract, quality, relative runtime, and absolute closure independent."""
    if not manifest_comparison.comparable:
        return _blocked_decision(
            list(manifest_comparison.violations), {"paired_row_count": len(paired_rows)}
        )
    if not _strict_nonnegative_int(manifest_comparison.expected_rows) or (
        manifest_comparison.expected_rows == 0
    ):
        return _blocked_decision(
            ["expected_pair_count_unavailable"], {"paired_row_count": len(paired_rows)}
        )
    if (
        not isinstance(manifest_comparison.case_set_sha256, str)
        or not _SHA256_PATTERN.fullmatch(manifest_comparison.case_set_sha256)
        or judge_receipt_contract is None
        or judge_receipt_contract.case_set_sha256 != manifest_comparison.case_set_sha256
        or not isinstance(manifest_comparison.judge_receipt_contract_sha256, str)
        or not _SHA256_PATTERN.fullmatch(manifest_comparison.judge_receipt_contract_sha256)
        or canonical_judge_receipt_contract_sha256(judge_receipt_contract)
        != manifest_comparison.judge_receipt_contract_sha256
    ):
        return _blocked_decision(
            ["judge_case_set_receipt_mismatch"], {"paired_row_count": len(paired_rows)}
        )

    evidence = _collect_metrics(
        paired_rows, expected_rows=manifest_comparison.expected_rows
    )
    metrics: dict[str, float | int | bool | None] = dict(evidence["metrics"])
    if not evidence["complete"]:
        return _blocked_decision(["paired_rows_incomplete"], metrics)

    reasons: list[str] = []
    contract_gate = _contract_gate(evidence, reasons)
    quality_gate = _quality_gate(
        evidence,
        judge_summary,
        judge_rows,
        judge_receipt_contract,
        holdout_summary,
        reasons,
    )
    runtime_gate = _runtime_gate(evidence, reasons)
    closure_gate = _absolute_latency_gate(evidence, reasons)
    return GateDecision(
        contract_gate=contract_gate,
        quality_gate=quality_gate,
        runtime_non_regression_gate=runtime_gate,
        phase64_latency_closure_gate=closure_gate,
        phase65_acceptance=_acceptance_status(contract_gate, quality_gate, runtime_gate),
        reasons=tuple(dict.fromkeys(reasons)),
        metrics=metrics,
    )


def _blocked_decision(
    reasons: list[str], metrics: dict[str, float | int | bool | None]
) -> GateDecision:
    return GateDecision(
        contract_gate="blocked",
        quality_gate="blocked",
        runtime_non_regression_gate="blocked",
        phase64_latency_closure_gate="blocked",
        phase65_acceptance="blocked",
        reasons=tuple(dict.fromkeys(reasons)),
        metrics=metrics,
    )


def _contract_gate(evidence: Mapping[str, object], reasons: list[str]) -> GateStatus:
    if int(evidence["unclassified_errors"]) > 0:
        reasons.append("unclassified_errors_present")
        return "fail"
    if int(evidence["repeated_completed_tools"]) > 0:
        reasons.append("repeated_completed_tools_present")
        return "fail"
    return "pass"


def _quality_gate(
    evidence: Mapping[str, object],
    judge_summary: Mapping[str, object] | None,
    judge_rows: Sequence[Mapping[str, object]] | None,
    judge_receipt_contract: JudgeReceiptContract | None,
    holdout_summary: Mapping[str, object] | None,
    reasons: list[str],
) -> GateStatus:
    if not evidence["functional_complete"]:
        reasons.append("functional_evidence_incomplete")
        return "blocked"
    if float(evidence["candidate_functional_rate"]) < float(
        evidence["baseline_functional_rate"]
    ):
        reasons.append("candidate_functional_rate_regressed")
        return "fail"
    judge_status = _judge_status(judge_summary, judge_rows, judge_receipt_contract, reasons)
    return judge_status if judge_status != "pass" else _holdout_status(holdout_summary, reasons)


def _judge_status(
    judge_summary: Mapping[str, object] | None,
    judge_rows: Sequence[Mapping[str, object]] | None,
    receipt_contract: JudgeReceiptContract | None,
    reasons: list[str],
) -> GateStatus:
    if judge_summary is None or judge_rows is None or receipt_contract is None:
        reasons.append("judge_evidence_incomplete")
        return "blocked"
    paired_count = judge_summary.get("paired_count")
    expected_pairs = judge_summary.get("judge_expected_pairs")
    seed = judge_summary.get("bootstrap_seed")
    samples = judge_summary.get("bootstrap_samples")
    case_set_sha256 = judge_summary.get("case_set_sha256")
    if (
        not _strict_nonnegative_int(paired_count)
        or not _strict_nonnegative_int(expected_pairs)
        or not _strict_nonnegative_int(seed)
        or not _strict_nonnegative_int(samples)
        or paired_count == 0
        or samples == 0
        or paired_count != receipt_contract.expected_count
        or expected_pairs != receipt_contract.expected_count
        or case_set_sha256 != receipt_contract.case_set_sha256
        or not validate_safe_judge_rows(judge_rows, receipt_contract=receipt_contract)
    ):
        reasons.append("judge_coverage_evidence_incomplete")
        return "blocked"
    expected_summary = summarize_judge_rows(judge_rows, seed=seed, samples=samples)
    for dimension in JUDGE_DIMENSIONS:
        value = _finite_number(judge_summary.get(f"{dimension}_lower_bound"))
        expected_value = _finite_number(expected_summary.get(f"{dimension}_lower_bound"))
        if value is None or expected_value is None or value != expected_value:
            reasons.append(f"judge_{dimension}_evidence_incomplete")
            return "blocked"
        if value < -0.05:
            reasons.append(f"judge_{dimension}_non_inferiority_failed")
            return "fail"
    return "pass"


def _holdout_status(
    holdout_summary: Mapping[str, object] | None, reasons: list[str]
) -> GateStatus:
    if holdout_summary is None:
        reasons.append("holdout_evidence_incomplete")
        return "blocked"
    count = holdout_summary.get("holdout_case_count")
    fingerprint = holdout_summary.get("holdout_case_set_sha256")
    proof_fields = (
        "clean",
        "tuning_exclusion_proven",
        "primary_latency_percentile_ci_exclusion_proven",
    )
    if (
        not _strict_nonnegative_int(count)
        or not isinstance(fingerprint, str)
        or not _SHA256_PATTERN.fullmatch(fingerprint)
        or any(not isinstance(holdout_summary.get(field), bool) for field in proof_fields)
    ):
        reasons.append("holdout_evidence_incomplete")
        return "blocked"
    if count < 12:
        reasons.append("holdout_case_count_insufficient")
        return "fail"
    if not holdout_summary["clean"]:
        reasons.append("holdout_not_clean")
        return "fail"
    if not holdout_summary["tuning_exclusion_proven"]:
        reasons.append("holdout_tuning_exclusion_failed")
        return "fail"
    if not holdout_summary["primary_latency_percentile_ci_exclusion_proven"]:
        reasons.append("holdout_primary_latency_exclusion_failed")
        return "fail"
    return "pass"


def _runtime_gate(evidence: Mapping[str, object], reasons: list[str]) -> GateStatus:
    ratios = evidence["relative_ratios"]
    if not isinstance(ratios, Mapping) or any(value is None for value in ratios.values()):
        reasons.append("runtime_evidence_incomplete")
        return "blocked"
    failed = [name for name, value in ratios.items() if float(value) > 1.05]
    if failed:
        reasons.extend(f"{name}_regressed" for name in failed)
        return "fail"
    return "pass"


def _absolute_latency_gate(evidence: Mapping[str, object], reasons: list[str]) -> GateStatus:
    absolute = evidence["absolute_latency"]
    if not isinstance(absolute, Mapping) or any(value is None for value in absolute.values()):
        reasons.append("phase64_latency_evidence_incomplete")
        return "blocked"
    thresholds = {
        "candidate_ttft_p50_ms": 8_000.0,
        "candidate_ttft_p95_ms": 15_000.0,
        "candidate_final_p95_ms": 30_000.0,
    }
    failed = [name for name, threshold in thresholds.items() if float(absolute[name]) > threshold]
    if failed:
        reasons.extend(f"phase64_{name}_threshold_failed" for name in failed)
        return "fail"
    return "pass"


def _acceptance_status(*gates: GateStatus) -> GateStatus:
    if "blocked" in gates:
        return "blocked"
    return "pass" if all(gate == "pass" for gate in gates) else "fail"


def _collect_metrics(
    rows: Sequence[Mapping[str, object]], *, expected_rows: int
) -> dict[str, object]:
    baseline_functional: list[bool] = []
    candidate_functional: list[bool] = []
    baseline_ttft: list[float] = []
    candidate_ttft: list[float] = []
    baseline_final: list[float] = []
    candidate_final: list[float] = []
    baseline_tokens: list[float] = []
    candidate_tokens: list[float] = []
    baseline_cost: list[float] = []
    candidate_cost: list[float] = []
    unclassified_errors = 0
    repeated_completed_tools = 0
    complete = len(rows) == expected_rows
    seen_case_runs: set[tuple[str, int]] = set()
    for row in rows:
        case_run = _case_run_key(row)
        if case_run is None or case_run in seen_case_runs:
            complete = False
        else:
            seen_case_runs.add(case_run)
        baseline = _variant_row(row, "baseline")
        candidate = _variant_row(row, "candidate")
        if baseline is None or candidate is None:
            complete = False
            continue
        base_ok = _bool_field(baseline, ("functional_ok", "deterministic_ok", "ok"))
        cand_ok = _bool_field(candidate, ("functional_ok", "deterministic_ok", "ok"))
        if base_ok is None or cand_ok is None:
            complete = False
        else:
            baseline_functional.append(base_ok)
            candidate_functional.append(cand_ok)
        for target, source, fields in (
            (baseline_ttft, baseline, ("ttft_ms", "first_token_ms")),
            (candidate_ttft, candidate, ("ttft_ms", "first_token_ms")),
            (baseline_final, baseline, ("final_ms", "elapsed_ms")),
            (candidate_final, candidate, ("final_ms", "elapsed_ms")),
        ):
            value = _nonnegative_number_field(source, fields)
            if value is None:
                complete = False
            else:
                target.append(value)
        base_tokens = _nonnegative_number_field(
            baseline, ("tokens", "token_count", "token_usage")
        )
        candidate_tokens_value = _nonnegative_number_field(
            candidate, ("tokens", "token_count", "token_usage")
        )
        base_cost = _nonnegative_number_field(baseline, ("cost", "cost_usd"))
        candidate_cost_value = _nonnegative_number_field(candidate, ("cost", "cost_usd"))
        if base_ok and base_tokens is not None and base_cost is not None:
            baseline_tokens.append(base_tokens)
            baseline_cost.append(base_cost)
        if cand_ok and candidate_tokens_value is not None and candidate_cost_value is not None:
            candidate_tokens.append(candidate_tokens_value)
            candidate_cost.append(candidate_cost_value)
        error_count = _count_field(row, ("unclassified_error_count", "unclassified_errors"))
        tool_count = _count_field(
            row, ("repeated_completed_tool_count", "repeated_completed_tools")
        )
        if error_count is None or tool_count is None:
            complete = False
        else:
            unclassified_errors += error_count
            repeated_completed_tools += tool_count

    base_rate = _rate(baseline_functional)
    candidate_rate = _rate(candidate_functional)
    base_ttft_p95 = _percentile(baseline_ttft, 0.95)
    candidate_ttft_p95 = _percentile(candidate_ttft, 0.95)
    candidate_ttft_p50 = _percentile(candidate_ttft, 0.50)
    base_final_p95 = _percentile(baseline_final, 0.95)
    candidate_final_p95 = _percentile(candidate_final, 0.95)
    token_ratio = _ratio(_mean(candidate_tokens), _mean(baseline_tokens))
    cost_ratio = _ratio(_mean(candidate_cost), _mean(baseline_cost))
    metrics: dict[str, float | int | bool | None] = {
        "paired_row_count": len(rows),
        "expected_paired_row_count": expected_rows,
        "baseline_functional_rate": base_rate,
        "candidate_functional_rate": candidate_rate,
        "baseline_ttft_p95_ms": base_ttft_p95,
        "candidate_ttft_p50_ms": candidate_ttft_p50,
        "candidate_ttft_p95_ms": candidate_ttft_p95,
        "baseline_final_p95_ms": base_final_p95,
        "candidate_final_p95_ms": candidate_final_p95,
        "candidate_ttft_p95_ratio": _ratio(candidate_ttft_p95, base_ttft_p95),
        "candidate_final_p95_ratio": _ratio(candidate_final_p95, base_final_p95),
        "candidate_token_ratio": token_ratio,
        "candidate_cost_ratio": cost_ratio,
        "unclassified_error_count": unclassified_errors,
        "repeated_completed_tool_count": repeated_completed_tools,
    }
    return {
        "complete": complete,
        "functional_complete": bool(baseline_functional)
        and len(baseline_functional) == len(rows)
        and len(candidate_functional) == len(rows),
        "baseline_functional_rate": base_rate,
        "candidate_functional_rate": candidate_rate,
        "unclassified_errors": unclassified_errors,
        "repeated_completed_tools": repeated_completed_tools,
        "relative_ratios": {
            "candidate_ttft_p95": metrics["candidate_ttft_p95_ratio"],
            "candidate_final_p95": metrics["candidate_final_p95_ratio"],
            "candidate_token": token_ratio,
            "candidate_cost": cost_ratio,
        },
        "absolute_latency": {
            "candidate_ttft_p50_ms": candidate_ttft_p50,
            "candidate_ttft_p95_ms": candidate_ttft_p95,
            "candidate_final_p95_ms": candidate_final_p95,
        },
        "metrics": metrics,
    }


def _variant_row(row: Mapping[str, object], variant: str) -> Mapping[str, object] | None:
    nested = row.get(variant)
    if isinstance(nested, Mapping):
        return nested
    prefix = f"{variant}_"
    flattened = {
        key[len(prefix):]: value
        for key, value in row.items()
        if isinstance(key, str) and key.startswith(prefix)
    }
    return flattened or None


def _case_run_key(row: Mapping[str, object]) -> tuple[str, int] | None:
    case_id = row.get("case_id")
    run = row.get("run")
    if not isinstance(case_id, str) or not _SAFE_IDENTIFIER_PATTERN.fullmatch(case_id):
        return None
    if not _strict_nonnegative_int(run) or run < 1:
        return None
    return case_id, run


def _bool_field(row: Mapping[str, object], fields: Sequence[str]) -> bool | None:
    for field in fields:
        if field in row:
            return row[field] if isinstance(row[field], bool) else None
    return None


def _nonnegative_number_field(row: Mapping[str, object], fields: Sequence[str]) -> float | None:
    for field in fields:
        if field in row:
            value = _finite_number(row[field])
            return value if value is not None and value >= 0 else None
    return None


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _strict_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _count_field(row: Mapping[str, object], fields: Sequence[str]) -> int | None:
    for field in fields:
        if field in row:
            value = row[field]
            return value if _strict_nonnegative_int(value) else None
    return None


def _rate(values: Sequence[bool]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]
