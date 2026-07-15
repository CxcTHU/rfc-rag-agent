from dataclasses import replace

import pytest

from scripts.phase65_agent_gate import (
    ManifestComparison,
    build_paired_execution_preflight,
    build_phase65_gate_decision,
    compare_manifests,
)
from scripts.phase65_gate_manifest import AgentGateManifest
from scripts.judge_phase65_agent_gate import (
    JudgeReceiptContract,
    anonymous_mapping_hash,
    canonical_judge_receipt_contract_sha256,
    build_safe_judge_row,
    summarize_judge_rows,
)


def baseline_manifest(**changes: object) -> AgentGateManifest:
    manifest = AgentGateManifest(
        schema_version="phase65-agent-gate-v1",
        run_id="baseline-run",
        variant="baseline",
        status="complete",
        base_commit="a" * 40,
        tracked_patch_sha256="b" * 64,
        scoped_content_sha256="a" * 64,
        scoped_paths=("app/services/agent/runtime.py",),
        evaluator_sha256="c" * 64,
        case_set_sha256="d" * 64,
        prompt_sha256="e" * 64,
        tool_schema_sha256="f" * 64,
        corpus_fingerprint="corpus",
        index_fingerprint="index",
        provider_models=("provider/model",),
        endpoint_identity_sha256="0" * 64,
        judge_receipt_contract_sha256=canonical_judge_receipt_contract_sha256(
            passing_judge_contract()
        ),
        cache_policy="cold",
        environment_class="local-production-topology",
        expected_rows=3,
        completed_rows=3,
        started_at="2026-07-14T00:00:00+00:00",
        completed_at="2026-07-14T01:00:00+00:00",
    )
    return replace(manifest, **changes)


def candidate_manifest(**changes: object) -> AgentGateManifest:
    values = {
        **baseline_manifest().__dict__,
        "run_id": "candidate-run",
        "variant": "candidate",
        "base_commit": "1" * 40,
        "tracked_patch_sha256": "2" * 64,
        "endpoint_identity_sha256": "1" * 64,
        "started_at": "2026-07-14T02:00:00+00:00",
        "completed_at": "2026-07-14T03:00:00+00:00",
        **changes,
    }
    return AgentGateManifest(**values)


def passing_comparison() -> ManifestComparison:
    return ManifestComparison(
        comparable=True,
        violations=(),
        expected_rows=3,
        case_set_sha256="d" * 64,
        judge_receipt_contract_sha256=canonical_judge_receipt_contract_sha256(
            passing_judge_contract()
        ),
    )


def passing_judge_contract() -> JudgeReceiptContract:
    mapping_a = anonymous_mapping_hash({"A": "baseline", "B": "candidate"})
    mapping_b = anonymous_mapping_hash({"A": "candidate", "B": "baseline"})
    return JudgeReceiptContract(
        case_set_sha256="d" * 64,
        expected_pairs=tuple((f"{index:x}" * 64, 1, "ordinary_text") for index in range(1, 4)),
        expected_mapping_hashes=(mapping_a, mapping_b, mapping_a),
    )


def passing_judge_rows() -> list[dict[str, object]]:
    contract = passing_judge_contract()
    mapping_a = {"A": "baseline", "B": "candidate"}
    mapping_b = {"A": "candidate", "B": "baseline"}
    mapping_a_hash = anonymous_mapping_hash(mapping_a)
    return [
        build_safe_judge_row(
            case_id=case_id,
            run=run,
            category=category,
            mapping=(mapping_a if mapping_hash == mapping_a_hash else mapping_b),
            winner_label="tie",
            label_deltas={
                "completion": -0.05,
                "accuracy": -0.05,
                "citation_support": -0.05,
                "overall_quality": -0.05,
            },
            judge_latency_ms=1.0,
            judge_provider="provider",
            judge_model="judge-model",
            reason="",
            receipt_contract=contract,
        )
        for (case_id, run, category), mapping_hash in zip(
            contract.expected_pairs, contract.expected_mapping_hashes
        )
    ]


def passing_judge_summary() -> dict[str, float | int | str]:
    return summarize_judge_rows(
        passing_judge_rows(),
        seed=650013,
        samples=10_000,
        receipt_contract=passing_judge_contract(),
    )


def passing_holdout_summary() -> dict[str, object]:
    return {
        "clean": True,
        "holdout_case_count": 12,
        "holdout_case_set_sha256": "f" * 64,
        "tuning_exclusion_proven": True,
        "primary_latency_percentile_ci_exclusion_proven": True,
    }


def passing_rows(
    *, candidate_ttft_p95: float = 10_500.0, candidate_final_p95: float = 21_000.0
) -> list[dict[str, object]]:
    return [
        {
            "case_id": f"case-{run}",
            "run": run,
            "baseline": {
                "functional_ok": True,
                "ttft_ms": candidate_ttft_p95 / 1.05,
                "final_ms": candidate_final_p95 / 1.05,
                "tokens": 100.0,
                "cost": 1.0,
            },
            "candidate": {
                "functional_ok": True,
                "ttft_ms": candidate_ttft_p95,
                "final_ms": candidate_final_p95,
                "tokens": 105.0,
                "cost": 1.05,
            },
            "unclassified_error_count": 0,
            "repeated_completed_tool_count": 0,
        }
        for run in range(1, 4)
    ]


def test_manifest_mismatch_blocks_every_release_decision() -> None:
    comparison = compare_manifests(
        baseline_manifest(), candidate_manifest(corpus_fingerprint="other")
    )

    assert comparison.comparable is False
    assert comparison.violations == ("corpus_fingerprint_mismatch",)


def test_incomplete_or_warm_manifests_are_incomparable() -> None:
    incomplete = compare_manifests(
        baseline_manifest(completed_rows=2), candidate_manifest()
    )
    warm = compare_manifests(
        baseline_manifest(cache_policy="warm"), candidate_manifest()
    )

    assert incomplete == ManifestComparison(False, ("baseline_manifest_incomplete",))
    assert "baseline_cache_policy_not_cold" in warm.violations


def test_endpoint_identity_mismatch_blocks_manifest_comparison() -> None:
    comparison = compare_manifests(
        baseline_manifest(), candidate_manifest(endpoint_identity_sha256="0" * 64)
    )

    assert comparison.comparable is False
    assert comparison.violations == ("endpoint_identity_not_distinct",)


def test_paired_execution_preflight_blocks_without_paid_run_authorization() -> None:
    summary = build_paired_execution_preflight(
        baseline_manifest=baseline_manifest(),
        candidate_manifest=candidate_manifest(),
        contract_gate="pass",
        topology_gate="pass",
        fault_gate="pass",
        paid_execution_authorized=False,
    )

    assert summary["schema_version"] == "phase65-paired-preflight-v1"
    assert summary["gate"] == "blocked"
    assert summary["ready_to_execute"] is False
    assert "paid_execution_not_authorized" in summary["failed_required"]


def test_paired_execution_preflight_passes_only_for_cold_distinct_authorized_lanes() -> None:
    summary = build_paired_execution_preflight(
        baseline_manifest=baseline_manifest(),
        candidate_manifest=candidate_manifest(),
        contract_gate="pass",
        topology_gate="pass",
        fault_gate="pass",
        paid_execution_authorized=True,
    )

    assert summary["gate"] == "pass"
    assert summary["ready_to_execute"] is True
    assert summary["failed_required"] == []


def test_invalid_runtime_values_block_before_threshold_comparison() -> None:
    rows = passing_rows()
    rows[0]["candidate"]["ttft_ms"] = float("nan")  # type: ignore[index]
    rows[1]["candidate"]["final_ms"] = -1.0  # type: ignore[index]
    rows[2]["candidate"]["tokens"] = float("inf")  # type: ignore[index]
    rows[2]["candidate"]["cost"] = -0.1  # type: ignore[index]

    decision = build_phase65_gate_decision(
        paired_rows=rows,
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=passing_holdout_summary(),
    )

    assert decision.runtime_non_regression_gate == "blocked"
    assert decision.phase65_acceptance == "blocked"


def test_non_integer_or_missing_error_counts_block() -> None:
    rows = passing_rows()
    rows[0]["unclassified_error_count"] = 0.0
    rows[1].pop("repeated_completed_tool_count")

    decision = build_phase65_gate_decision(
        paired_rows=rows,
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=passing_holdout_summary(),
    )

    assert decision.contract_gate == "blocked"


def test_expected_pair_count_and_case_run_uniqueness_are_required() -> None:
    rows = passing_rows()
    rows[1]["case_id"] = "case-1"
    rows[1]["run"] = 1

    decision = build_phase65_gate_decision(
        paired_rows=rows,
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=passing_holdout_summary(),
    )

    assert decision.contract_gate == "blocked"
    assert decision.metrics["paired_row_count"] == 3


def test_missing_or_extra_pair_count_blocks() -> None:
    missing = build_phase65_gate_decision(
        paired_rows=passing_rows()[:2],
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=passing_holdout_summary(),
    )
    extra = build_phase65_gate_decision(
        paired_rows=passing_rows() + passing_rows()[:1],
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=passing_holdout_summary(),
    )

    assert missing.phase65_acceptance == "blocked"
    assert extra.phase65_acceptance == "blocked"


def test_missing_token_or_cost_receipts_do_not_make_paired_rows_incomplete() -> None:
    rows = passing_rows()
    for row in rows:
        row["baseline"].pop("tokens")  # type: ignore[index]
        row["baseline"].pop("cost")  # type: ignore[index]
        row["candidate"].pop("tokens")  # type: ignore[index]
        row["candidate"].pop("cost")  # type: ignore[index]

    decision = build_phase65_gate_decision(
        paired_rows=rows,
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=passing_holdout_summary(),
        judge_rows=passing_judge_rows(),
        judge_receipt_contract=passing_judge_contract(),
    )

    assert "paired_rows_incomplete" not in decision.reasons
    assert decision.metrics["candidate_token_ratio"] is None
    assert decision.metrics["candidate_cost_ratio"] is None


def test_relative_pass_does_not_claim_absolute_latency_closure() -> None:
    decision = build_phase65_gate_decision(
        paired_rows=passing_rows(candidate_ttft_p95=18_000.0),
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=passing_holdout_summary(),
        judge_rows=passing_judge_rows(),
        judge_receipt_contract=passing_judge_contract(),
    )

    assert decision.runtime_non_regression_gate == "pass"
    assert decision.phase64_latency_closure_gate == "fail"
    assert decision.phase65_acceptance == "pass"


def test_exact_non_regression_boundaries_pass() -> None:
    decision = build_phase65_gate_decision(
        paired_rows=passing_rows(),
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=passing_holdout_summary(),
        judge_rows=passing_judge_rows(),
        judge_receipt_contract=passing_judge_contract(),
    )

    assert decision.contract_gate == "pass"
    assert decision.quality_gate == "pass"
    assert decision.runtime_non_regression_gate == "pass"
    assert decision.phase65_acceptance == "pass"
    assert decision.metrics["candidate_ttft_p95_ratio"] == 1.05
    assert decision.metrics["candidate_token_ratio"] == 1.05


def test_missing_judge_evidence_blocks_instead_of_passing() -> None:
    decision = build_phase65_gate_decision(
        paired_rows=passing_rows(),
        manifest_comparison=passing_comparison(),
        judge_summary={},
        holdout_summary=passing_holdout_summary(),
    )

    assert decision.quality_gate == "blocked"
    assert decision.phase65_acceptance == "blocked"


def test_fabricated_lower_bounds_without_safe_judge_rows_block_quality() -> None:
    decision = build_phase65_gate_decision(
        paired_rows=passing_rows(),
        manifest_comparison=passing_comparison(),
        judge_summary={
            "paired_count": 3,
            "bootstrap_seed": 650013,
            "bootstrap_samples": 10_000,
            "completion_lower_bound": 0.0,
            "accuracy_lower_bound": 0.0,
            "citation_support_lower_bound": 0.0,
            "overall_quality_lower_bound": 0.0,
        },
        judge_rows=(),
        judge_receipt_contract=passing_judge_contract(),
        holdout_summary=passing_holdout_summary(),
    )

    assert decision.quality_gate == "blocked"
    assert decision.phase65_acceptance == "blocked"


def test_judge_summary_requires_matching_case_set_receipt() -> None:
    summary = passing_judge_summary()
    summary.pop("case_set_sha256")

    decision = build_phase65_gate_decision(
        paired_rows=passing_rows(),
        manifest_comparison=passing_comparison(),
        judge_summary=summary,
        judge_rows=passing_judge_rows(),
        judge_receipt_contract=passing_judge_contract(),
        holdout_summary=passing_holdout_summary(),
    )

    assert decision.quality_gate == "blocked"
    assert decision.phase65_acceptance == "blocked"


def test_single_anonymous_mapping_schedule_is_blocked() -> None:
    contract = passing_judge_contract()
    rows = passing_judge_rows()
    rows[1]["mapping_hash"] = rows[0]["mapping_hash"]
    summary = summarize_judge_rows(rows, receipt_contract=contract)

    decision = build_phase65_gate_decision(
        paired_rows=passing_rows(),
        manifest_comparison=passing_comparison(),
        judge_summary=summary,
        judge_rows=rows,
        judge_receipt_contract=contract,
        holdout_summary=passing_holdout_summary(),
    )

    assert decision.quality_gate == "blocked"


def test_judge_contract_case_set_must_match_manifest_comparison() -> None:
    trusted_contract = passing_judge_contract()
    unrelated_contract = JudgeReceiptContract(
        case_set_sha256="c" * 64,
        expected_pairs=trusted_contract.expected_pairs,
        expected_mapping_hashes=trusted_contract.expected_mapping_hashes,
    )
    rows = passing_judge_rows()
    summary = summarize_judge_rows(rows, receipt_contract=unrelated_contract)

    decision = build_phase65_gate_decision(
        paired_rows=passing_rows(),
        manifest_comparison=passing_comparison(),
        judge_summary=summary,
        judge_rows=rows,
        judge_receipt_contract=unrelated_contract,
        holdout_summary=passing_holdout_summary(),
    )

    assert decision.quality_gate == "blocked"


def test_contract_rejects_noncanonical_anonymous_mapping_hashes() -> None:
    trusted = passing_judge_contract()

    with pytest.raises(ValueError):
        JudgeReceiptContract(
            case_set_sha256=trusted.case_set_sha256,
            expected_pairs=trusted.expected_pairs,
            expected_mapping_hashes=("1" * 64, "2" * 64, "1" * 64),
        )


def test_same_case_set_but_unrelated_expected_pairs_are_blocked() -> None:
    trusted = passing_judge_contract()
    unrelated = JudgeReceiptContract(
        case_set_sha256=trusted.case_set_sha256,
        expected_pairs=(
            ("a" * 64, 1, "ordinary_text"),
            ("b" * 64, 1, "ordinary_text"),
            ("c" * 64, 1, "ordinary_text"),
        ),
        expected_mapping_hashes=trusted.expected_mapping_hashes,
    )
    mapping_a = {"A": "baseline", "B": "candidate"}
    mapping_b = {"A": "candidate", "B": "baseline"}
    mapping_a_hash = anonymous_mapping_hash(mapping_a)
    rows = [
        build_safe_judge_row(
            case_id=case_id,
            run=run,
            category=category,
            mapping=(mapping_a if mapping_hash == mapping_a_hash else mapping_b),
            winner_label="tie",
            label_deltas={dimension: 0.0 for dimension in (
                "completion", "accuracy", "citation_support", "overall_quality"
            )},
            judge_latency_ms=1.0,
            judge_provider="provider",
            judge_model="judge-model",
            reason="",
            receipt_contract=unrelated,
        )
        for (case_id, run, category), mapping_hash in zip(
            unrelated.expected_pairs, unrelated.expected_mapping_hashes
        )
    ]
    summary = summarize_judge_rows(rows, receipt_contract=unrelated)

    decision = build_phase65_gate_decision(
        paired_rows=passing_rows(),
        manifest_comparison=passing_comparison(),
        judge_summary=summary,
        judge_rows=rows,
        judge_receipt_contract=unrelated,
        holdout_summary=passing_holdout_summary(),
    )

    assert decision.quality_gate == "blocked"


def test_incomplete_holdout_proof_blocks_quality_gate() -> None:
    holdout = passing_holdout_summary()
    holdout.pop("primary_latency_percentile_ci_exclusion_proven")

    decision = build_phase65_gate_decision(
        paired_rows=passing_rows(),
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=holdout,
        judge_rows=passing_judge_rows(),
        judge_receipt_contract=passing_judge_contract(),
    )

    assert decision.quality_gate == "blocked"
    assert decision.phase65_acceptance == "blocked"


def test_holdout_requires_at_least_twelve_cases() -> None:
    holdout = passing_holdout_summary()
    holdout["holdout_case_count"] = 11

    decision = build_phase65_gate_decision(
        paired_rows=passing_rows(),
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=holdout,
        judge_rows=passing_judge_rows(),
        judge_receipt_contract=passing_judge_contract(),
    )

    assert decision.quality_gate == "fail"
    assert decision.phase65_acceptance == "fail"


def test_unclassified_error_fails_contract_gate() -> None:
    rows = passing_rows()
    rows[0]["unclassified_error_count"] = 1

    decision = build_phase65_gate_decision(
        paired_rows=rows,
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=passing_holdout_summary(),
        judge_rows=passing_judge_rows(),
        judge_receipt_contract=passing_judge_contract(),
    )

    assert decision.contract_gate == "fail"
    assert decision.phase65_acceptance == "fail"


def test_missing_error_counter_evidence_blocks_contract_gate() -> None:
    rows = passing_rows()
    del rows[0]["unclassified_error_count"]

    decision = build_phase65_gate_decision(
        paired_rows=rows,
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=passing_holdout_summary(),
    )

    assert decision.contract_gate == "blocked"
    assert decision.runtime_non_regression_gate == "blocked"
    assert decision.phase64_latency_closure_gate == "blocked"
    assert decision.phase65_acceptance == "blocked"
