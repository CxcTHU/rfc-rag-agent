import csv
import json
from pathlib import Path

from scripts.analyze_stage35_deduction_causes import (
    analyze_deductions,
    read_rows,
    write_output,
)


def test_stage35_deduction_causes_classify_current_stage30_items() -> None:
    analyses = analyze_deductions(
        read_rows(Path("data/evaluation/stage30_quality_deductions.csv")),
        read_rows(Path("data/evaluation/stage29_real_quality_results.csv")),
        read_rows(Path("data/evaluation/stage29_new_corpus_queries.csv")),
    )

    assert analyses == []


def test_stage35_deduction_causes_classify_retrieval_and_context_fixtures() -> None:
    analyses = analyze_deductions(
        [
            {
                "query_id": "context_case",
                "dimension": "rule_based_context_answer_quality",
                "deduction_points": "0.50",
                "deduction_reason": "coverage low",
            },
            {
                "query_id": "retrieval_case",
                "dimension": "retrieval_quality",
                "deduction_points": "1.00",
                "deduction_reason": "missed expected source",
            },
        ],
        [
            {
                "query_id": "context_case",
                "precision_at_3": "false",
                "precision_at_5": "true",
                "coverage_ratio": "0.40",
                "missing_points": "inventor; method",
                "covered_points": "standard",
                "top_titles": "relevant source",
            },
            {
                "query_id": "retrieval_case",
                "precision_at_3": "false",
                "precision_at_5": "false",
                "coverage_ratio": "0.00",
                "missing_points": "standard; guideline",
                "top_titles": "metadata page",
            },
        ],
        [
            {
                "query_id": "context_case",
                "expected_answer_points": "inventor; method; standard",
            },
            {
                "query_id": "retrieval_case",
                "expected_answer_points": "standard; guideline",
            },
        ],
    )

    causes = {(item.query_id, item.dimension): item.root_cause for item in analyses}
    assert causes[("context_case", "rule_based_context_answer_quality")] == "context_expansion_miss"
    assert causes[("retrieval_case", "retrieval_quality")] == "retrieval_miss"
    assert all(item.needs_score_rerun == "true" for item in analyses)


def test_stage35_deduction_causes_handles_empty_evidence_and_writes_safe_csv(tmp_path) -> None:
    analyses = analyze_deductions(
        [
            {
                "query_id": "missing_query",
                "dimension": "rule_based_context_answer_quality",
                "deduction_points": "2.00",
                "deduction_reason": "coverage low",
            }
        ],
        [],
        [],
    )
    output = tmp_path / "root_causes.csv"

    write_output(output, analyses)

    with output.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["root_cause"] == "rule_too_strict"
    serialized = json.dumps(rows, ensure_ascii=False).lower()
    assert "api key" not in serialized
    assert "bearer token" not in serialized
    assert "raw_response" not in serialized
    assert "reasoning_content" not in serialized
    assert "hidden thought" not in serialized
