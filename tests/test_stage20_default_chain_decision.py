"""阶段 20 默认链路接入决策测试。"""

from __future__ import annotations

from scripts.build_stage20_default_chain_decision import (
    BASELINE_CONFIG,
    SummaryMetrics,
    build_decision_rows,
    evaluate_gate,
)


def metrics(
    config: str,
    p1: float,
    deep: float,
    refusal: float,
    status: str = "completed",
) -> SummaryMetrics:
    return SummaryMetrics(
        config=config,
        precision_at_1=p1,
        deep_fulltext_top1_rate=deep,
        refusal_accuracy=refusal,
        source_decision="",
        real_config_status=status,
    )


def test_evaluate_gate_requires_p1_deep_and_refusal() -> None:
    baseline = metrics(BASELINE_CONFIG, p1=0.4, deep=0.0, refusal=0.75)
    passed = metrics("candidate", p1=0.5, deep=0.2, refusal=0.75)
    failed = metrics("candidate", p1=0.49, deep=0.2, refusal=0.75)

    assert evaluate_gate(passed, baseline).passed is True
    failed_gate = evaluate_gate(failed, baseline)
    assert failed_gate.passed is False
    assert any("delta_precision_at_1" in blocker for blocker in failed_gate.blockers)


def test_build_decision_rows_keeps_existing_when_real_missing() -> None:
    deterministic = {
        BASELINE_CONFIG: metrics(BASELINE_CONFIG, p1=0.4, deep=0.0, refusal=0.75),
        "candidate": metrics("candidate", p1=0.6, deep=0.3, refusal=0.75),
    }
    rows = build_decision_rows(deterministic, real={})

    candidate = next(row for row in rows if row["config"] == "candidate")
    assert candidate["final_decision"] == "keep_existing_hybrid"
    assert "real:real_jina_summary_missing" in candidate["blocker"]


def test_build_decision_rows_promotes_only_when_both_summaries_pass() -> None:
    deterministic = {
        BASELINE_CONFIG: metrics(BASELINE_CONFIG, p1=0.4, deep=0.0, refusal=0.75),
        "candidate": metrics("candidate", p1=0.6, deep=0.3, refusal=0.75),
    }
    real = {
        BASELINE_CONFIG: metrics(BASELINE_CONFIG, p1=0.4, deep=0.0, refusal=0.75),
        "candidate": metrics("candidate", p1=0.6, deep=0.3, refusal=0.75),
    }
    rows = build_decision_rows(deterministic, real=real)

    candidate = next(row for row in rows if row["config"] == "candidate")
    assert candidate["final_decision"] == "switch_default_candidate"
