"""阶段 20 quality gate 汇总生成测试。"""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.build_stage20_quality_report import build_quality_rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_build_quality_rows_closes_responsibility_and_keeps_hybrid(tmp_path) -> None:
    det = tmp_path / "det.csv"
    real = tmp_path / "real.csv"
    results = tmp_path / "results.csv"
    decision = tmp_path / "decision.csv"

    summary_fields = [
        "config",
        "judge_mode",
        "real_config_status",
        "precision_at_1",
        "deep_fulltext_top1_rate",
        "refusal_accuracy",
    ]
    write_csv(
        det,
        summary_fields,
        [
            {"config": "hybrid_baseline", "judge_mode": "coverage_ratio", "real_config_status": "", "precision_at_1": "0.133", "deep_fulltext_top1_rate": "0.267", "refusal_accuracy": "1.000"},
            {"config": "hybrid_topic_anchor_strict", "judge_mode": "coverage_ratio", "real_config_status": "", "precision_at_1": "0.133", "deep_fulltext_top1_rate": "0.733", "refusal_accuracy": "1.000"},
        ],
    )
    write_csv(
        real,
        summary_fields,
        [
            {"config": "hybrid_baseline", "judge_mode": "coverage_ratio_real_jina", "real_config_status": "completed", "precision_at_1": "0.133", "deep_fulltext_top1_rate": "0.267", "refusal_accuracy": "1.000"},
            {"config": "hybrid_topic_anchor_strict", "judge_mode": "coverage_ratio_real_jina", "real_config_status": "completed", "precision_at_1": "0.133", "deep_fulltext_top1_rate": "0.733", "refusal_accuracy": "1.000"},
        ],
    )
    write_csv(
        results,
        ["query_id", "config", "refusal_matched", "refused"],
        [
            {"query_id": "cn_hq_refusal_engineering_responsibility", "config": "hybrid_baseline", "refusal_matched": "true", "refused": "true"},
            {"query_id": "cn_hq_refusal_engineering_responsibility", "config": "hybrid_topic_anchor_strict", "refusal_matched": "true", "refused": "true"},
        ],
    )
    write_csv(
        decision,
        ["config", "final_decision", "blocker"],
        [
            {"config": "hybrid_baseline", "final_decision": "baseline", "blocker": ""},
            {"config": "hybrid_topic_anchor_strict", "final_decision": "keep_existing_hybrid", "blocker": "delta_precision_at_1=+0.000<0.10"},
        ],
    )

    rows = build_quality_rows(
        deterministic_summary_path=det,
        real_summary_path=real,
        results_path=results,
        decision_path=decision,
        full_tests_status="passed",
    )
    by_section = {row.section: row for row in rows}

    assert by_section["eval_judge_upgrade"].status == "completed"
    assert by_section["real_jina_query_validation"].status == "completed"
    assert by_section["default_chain_decision"].status == "keep_existing_hybrid"
    assert by_section["responsibility_gate"].status == "closed"
    assert by_section["api_regression"].status == "passed"
    assert by_section["overall"].status == "pass"
