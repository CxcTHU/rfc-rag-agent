from scripts.judge_phase65_agent_gate import (
    JUDGE_OUTPUT_FIELDS,
    JudgeReceiptContract,
    anonymous_mapping_hash,
    build_safe_judge_row,
    paired_bootstrap_lower_bound,
    summarize_judge_rows,
)
import pytest


RECEIPT_CONTRACT = JudgeReceiptContract(
    case_set_sha256="f" * 64,
    expected_pairs=(
        ("a" * 64, 1, "ordinary_text"),
        ("b" * 64, 1, "ordinary_text"),
    ),
    expected_mapping_hashes=(
        anonymous_mapping_hash({"A": "baseline", "B": "candidate"}),
        anonymous_mapping_hash({"A": "candidate", "B": "baseline"}),
    ),
)
REVERSED_RECEIPT_CONTRACT = JudgeReceiptContract(
    case_set_sha256="f" * 64,
    expected_pairs=RECEIPT_CONTRACT.expected_pairs,
    expected_mapping_hashes=(
        anonymous_mapping_hash({"A": "candidate", "B": "baseline"}),
        anonymous_mapping_hash({"A": "baseline", "B": "candidate"}),
    ),
)


def test_bootstrap_is_deterministic_for_each_dimension() -> None:
    deltas = [0.0, 0.01, -0.01, 0.02] * 10

    assert paired_bootstrap_lower_bound(deltas) == paired_bootstrap_lower_bound(deltas)


def test_judge_receipt_contract_requires_balanced_mapping_by_default() -> None:
    with pytest.raises(ValueError, match="invalid_judge_receipt_contract"):
        JudgeReceiptContract(
            case_set_sha256="f" * 64,
            expected_pairs=(("a" * 64, 1, "ordinary_text"),),
            expected_mapping_hashes=(
                anonymous_mapping_hash({"A": "baseline", "B": "candidate"}),
            ),
        )


def test_lane_only_receipt_contract_allows_single_mapping_without_judge_balance() -> None:
    contract = JudgeReceiptContract(
        case_set_sha256="f" * 64,
        expected_pairs=(("a" * 64, 1, "ordinary_text"),),
        expected_mapping_hashes=(
            anonymous_mapping_hash({"A": "baseline", "B": "candidate"}),
        ),
        require_balanced_mapping=False,
    )

    assert contract.expected_count == 1


def test_safe_judge_row_projects_only_safe_numeric_categorical_fields() -> None:
    row = build_safe_judge_row(
        case_id="a" * 64,
        run=1,
        category="ordinary_text",
        mapping={"A": "baseline", "B": "candidate"},
        winner_label="B",
        label_deltas={
            "completion": 2.0,
            "accuracy": -2.0,
            "citation_support": 0.25,
            "overall_quality": -0.25,
        },
        judge_latency_ms=12.0,
        judge_provider="provider",
        judge_model="judge-model",
        reason="raw judge rationale must not persist",
        receipt_contract=RECEIPT_CONTRACT,
    )

    assert tuple(row) == JUDGE_OUTPUT_FIELDS
    assert row["winner"] == "candidate"
    assert row["completion_delta"] == 1.0
    assert row["accuracy_delta"] == -1.0
    assert row["sanitized_reason"] == "judge_rationale_received"
    assert {"answer", "prompt", "raw judge rationale must not persist"}.isdisjoint(row)


def test_safe_judge_row_reverses_anonymous_direction_for_candidate_projection() -> None:
    row = build_safe_judge_row(
        case_id="a" * 64,
        run=1,
        category="ordinary_text",
        mapping={"A": "candidate", "B": "baseline"},
        winner_label="A",
        label_deltas={dimension: 0.4 for dimension in (
            "completion", "accuracy", "citation_support", "overall_quality"
        )},
        judge_latency_ms=12.0,
        judge_provider="provider",
        judge_model="judge-model",
        reason="",
        receipt_contract=REVERSED_RECEIPT_CONTRACT,
    )

    assert row["winner"] == "candidate"
    assert row["overall_quality_delta"] == -0.4
    assert row["sanitized_reason"] == "judge_rationale_unavailable"


def test_judge_summary_uses_all_four_non_inferiority_dimensions() -> None:
    rows = [
        {
            "completion_delta": -0.05,
            "accuracy_delta": -0.05,
            "citation_support_delta": -0.05,
            "overall_quality_delta": -0.05,
        }
        for _ in range(3)
    ]

    summary = summarize_judge_rows(rows, seed=9, samples=100)

    assert summary["schema_version"] == "phase65-judge-summary-v1"
    assert summary["paired_count"] == 3
    assert all(summary[f"{dimension}_lower_bound"] == -0.05 for dimension in (
        "completion", "accuracy", "citation_support", "overall_quality"
    ))


def test_judge_summary_binds_receipt_contract_when_available() -> None:
    rows = [
        {
            "completion_delta": 0.0,
            "accuracy_delta": 0.0,
            "citation_support_delta": 0.0,
            "overall_quality_delta": 0.0,
        },
        {
            "completion_delta": 0.0,
            "accuracy_delta": 0.0,
            "citation_support_delta": 0.0,
            "overall_quality_delta": 0.0,
        },
    ]

    summary = summarize_judge_rows(
        rows,
        seed=9,
        samples=100,
        receipt_contract=RECEIPT_CONTRACT,
    )

    assert summary["schema_version"] == "phase65-judge-summary-v1"
    assert summary["case_set_sha256"] == RECEIPT_CONTRACT.case_set_sha256
    assert summary["receipt_contract_sha256"] == RECEIPT_CONTRACT.canonical_sha256
    assert summary["judge_expected_pairs"] == RECEIPT_CONTRACT.expected_count


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_id", "unsafe marker\nsecret"),
        ("category", "unsafe category!"),
        ("judge_provider", "provider;payload"),
        ("judge_model", "model\x00name"),
        ("judge_latency_ms", float("nan")),
        ("judge_latency_ms", -1.0),
    ],
)
def test_safe_judge_row_rejects_unsafe_identifiers_and_latency(
    field: str, value: object
) -> None:
    kwargs: dict[str, object] = {
        "case_id": "a" * 64,
        "run": 1,
        "category": "ordinary_text",
        "mapping": {"A": "baseline", "B": "candidate"},
        "winner_label": "B",
        "label_deltas": {dimension: 0.0 for dimension in (
            "completion", "accuracy", "citation_support", "overall_quality"
        )},
        "judge_latency_ms": 12.0,
        "judge_provider": "provider",
        "judge_model": "judge-model",
        "reason": "answer body that must not be reflected",
        "receipt_contract": RECEIPT_CONTRACT,
    }
    kwargs[field] = value

    with pytest.raises(ValueError) as exc_info:
        build_safe_judge_row(**kwargs)  # type: ignore[arg-type]

    assert "answer body" not in str(exc_info.value)


def test_safe_judge_row_rejects_secret_shaped_provider_before_persistence() -> None:
    with pytest.raises(ValueError) as exc_info:
        build_safe_judge_row(
            case_id="a" * 64,
            run=1,
            category="ordinary_text",
            mapping={"A": "baseline", "B": "candidate"},
            winner_label="B",
            label_deltas={dimension: 0.0 for dimension in (
                "completion", "accuracy", "citation_support", "overall_quality"
            )},
            judge_latency_ms=1.0,
            judge_provider="sk-live-secret-token",
            judge_model="judge-model",
            reason="",
            receipt_contract=RECEIPT_CONTRACT,
        )

    assert "sk-live-secret-token" not in str(exc_info.value)
