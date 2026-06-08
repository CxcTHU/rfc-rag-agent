from pathlib import Path

from scripts.evaluate_stage17_retrieval_upgrade import (
    BaselineRow,
    EvaluatedUpgradeResult,
    decide_upgrade,
    read_baseline_rows,
    write_report,
    write_results,
)


def test_decide_upgrade_classifies_outcomes() -> None:
    assert decide_upgrade(True, False, 1, None) == "regression"
    assert decide_upgrade(False, True, None, 2) == "improved"
    assert decide_upgrade(False, False, None, None) == "unresolved"
    assert decide_upgrade(True, True, 4, 2) == "improved"
    assert decide_upgrade(True, True, 2, 2) == "neutral"


def test_read_baseline_rows_parses_hybrid_results(tmp_path) -> None:
    path = tmp_path / "hybrid_results.csv"
    path.write_text(
        "query_id,passed,hit_rank,hit_title,top_titles\n"
        "q1,yes,2,Expected Title,Expected Title || Other\n"
        "q2,no,,,Other\n",
        encoding="utf-8",
    )

    rows = read_baseline_rows(path)

    assert rows["q1"] == BaselineRow(
        passed=True,
        hit_rank=2,
        hit_title="Expected Title",
        top_titles="Expected Title || Other",
    )
    assert rows["q2"].passed is False
    assert rows["q2"].hit_rank is None


def test_write_results_and_report_include_required_stage17_fields(tmp_path) -> None:
    results = [
        EvaluatedUpgradeResult(
            query_id="q1",
            query="ITZ strength",
            baseline_hit=True,
            upgraded_hit=True,
            source_match=True,
            rank_before=2,
            rank_after=1,
            retrieval_mode="bm25_vector_rrf",
            decision="improved",
            evidence="channels=bm25+vector; rrf_score=0.1",
            baseline_top_titles="Old",
            upgraded_top_titles="New",
            matched_channels="bm25+vector",
            provider="deterministic",
            model_name="deterministic-embedding-v1",
            notes="sample",
        )
    ]
    output_path = tmp_path / "stage17_results.csv"
    report_path = tmp_path / "stage17_report.md"

    write_results(output_path, results)
    write_report(report_path, results, Path("data/evaluation/stage17_retrieval_upgrade_results.csv"))

    output = output_path.read_text(encoding="utf-8")
    report = report_path.read_text(encoding="utf-8")

    for phrase in [
        "query_id",
        "baseline_hit",
        "upgraded_hit",
        "source_match",
        "rank_before",
        "rank_after",
        "retrieval_mode",
        "decision",
        "evidence",
    ]:
        assert phrase in output

    for phrase in [
        "阶段 17 检索架构升级评测报告",
        "BM25+vector RRF",
        "default_decision",
        "不保存 API key",
        "不提交、不打 tag、不推送",
    ]:
        assert phrase in report
