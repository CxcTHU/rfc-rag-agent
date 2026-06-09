"""阶段 18：质量门槛汇总生成逻辑测试（不联网、不写真实产物）。"""

import csv
from pathlib import Path

from scripts.build_stage18_quality_report import (
    GateRow,
    build_quality_gate_rows,
    _default_chain_decision,
    _overall_gate,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_default_chain_decision_keeps_hybrid() -> None:
    comparison = {
        "hybrid": {"hits": "15", "rank1_hits": "14"},
        "bm25_rrf": {"hits": "15", "rank1_hits": "14"},
    }
    assert _default_chain_decision(comparison) == "keep_existing_hybrid"


def test_overall_gate_blocks_on_high_risk() -> None:
    rows = [
        GateRow("corpus", "depth", "expanded", "11->16", "low", "f", "ok"),
        GateRow("refusal_boundary", "off_topic", "review_required", "1/5", "high", "f", "fix"),
    ]
    overall = _overall_gate(rows)
    assert overall.section == "overall"
    assert overall.status == "review_required"
    assert overall.value == "high"


def test_build_quality_gate_rows_surfaces_refusal_risk(tmp_path) -> None:
    corpus = tmp_path / "corpus.csv"
    comparison = tmp_path / "cmp.csv"
    hard = tmp_path / "hard.csv"

    _write_csv(corpus, ["metric", "value"], [
        {"metric": "deep_fulltext_before", "value": "11"},
        {"metric": "deep_fulltext_after", "value": "16"},
        {"metric": "open_access_pdf", "value": "15"},
        {"metric": "total_chunks", "value": "1332"},
    ])
    _write_csv(comparison, ["config", "hits", "rank1_hits", "precision_at_1"], [
        {"config": "hybrid", "hits": "15", "rank1_hits": "14", "precision_at_1": "0.93"},
        {"config": "vector", "hits": "15", "rank1_hits": "11", "precision_at_1": "0.73"},
        {"config": "bm25_rrf", "hits": "15", "rank1_hits": "14", "precision_at_1": "0.93"},
    ])
    _write_csv(hard, ["expected_refused", "refusal_matched"], [
        {"expected_refused": "yes", "refusal_matched": "no"},
        {"expected_refused": "yes", "refusal_matched": "yes"},
        {"expected_refused": "yes", "refusal_matched": "no"},
        {"expected_refused": "no", "refusal_matched": ""},
    ])

    rows = build_quality_gate_rows(
        corpus_path=corpus,
        comparison_path=comparison,
        comparison_real_path=tmp_path / "missing_real.csv",
        hard_results_path=hard,
    )
    by_section = {r.section: r for r in rows}
    assert by_section["default_chain"].status == "keep_existing_hybrid"
    assert by_section["refusal_boundary"].risk == "high"
    assert by_section["overall"].status == "review_required"
    assert by_section["overall"].value == "high"
