import csv
import json
from pathlib import Path

from scripts.score_stage30_quality import (
    load_scoring_config,
    score_quality,
    write_deductions,
    write_scores,
    write_summary,
)


def stage29_rows() -> list[dict[str, str]]:
    return [
        {
            "query_id": "stage29_good",
            "expected_refused": "false",
            "expected_source_type": "web_page",
            "precision_at_5": "true",
            "coverage_ratio": "0.750",
            "source_type_distribution": "web_page:3;wikipedia:2",
        },
        {
            "query_id": "stage29_low_coverage",
            "expected_refused": "false",
            "expected_source_type": "wikipedia",
            "precision_at_5": "false",
            "coverage_ratio": "0.250",
            "source_type_distribution": "web_page:5",
        },
        {
            "query_id": "stage29_refusal",
            "expected_refused": "true",
            "expected_source_type": "",
            "precision_at_5": "false",
            "coverage_ratio": "0.000",
            "source_type_distribution": "",
        },
    ]


def stage29_summary() -> dict[str, str]:
    return {
        "precision_at_1": "0.600",
        "precision_at_3": "0.867",
        "precision_at_5": "0.933",
        "avg_coverage_ratio": "0.664",
        "refusal_accuracy": "1.000",
        "source_type_distribution": "metadata_record:2;web_page:5;wikipedia:3;standard_document:1",
    }


def health() -> dict[str, object]:
    return {
        "full_tests_status": "556 passed, 1 warning",
        "chunk_count": 10,
        "embedding_count": 20,
        "jina_embedding_count": 10,
        "deterministic_embedding_count": 10,
        "orphan_embeddings": 0,
        "duplicate_provider_model_groups": 0,
        "quality_report_smoke": "passed",
    }


def test_stage30_weights_sum_to_100_and_keep_rule_based_names() -> None:
    config = load_scoring_config(Path("data/evaluation/stage30_scoring_weights.yaml"))

    assert sum(config.weights.values()) == 100
    assert "rule_based_context_answer_quality" in config.weights
    assert "faithfulness" not in config.weights
    assert config.scoring_mode == "deterministic_rule_based"


def test_stage30_score_outputs_review_required_for_known_risks(tmp_path) -> None:
    config = load_scoring_config(Path("data/evaluation/stage30_scoring_weights.yaml"))

    result = score_quality(
        stage29_rows(),
        stage29_summary(),
        health(),
        config,
        run_id="test-run",
        run_at="2026-06-12T00:00:00+00:00",
        previous_scores_path=tmp_path / "missing.csv",
    )

    assert result.grade == "B"
    assert result.release_decision == "review_required"
    assert result.dimension_scores["engineering_health"] == 10
    assert any(item.query_id == "stage29_low_coverage" for item in result.deductions)
    assert "faithfulness" not in json.dumps(result.dimension_scores)


def test_stage30_score_writers_create_expected_csvs(tmp_path) -> None:
    config = load_scoring_config(Path("data/evaluation/stage30_scoring_weights.yaml"))
    result = score_quality(
        stage29_rows(),
        stage29_summary(),
        health(),
        config,
        run_id="test-run",
        run_at="2026-06-12T00:00:00+00:00",
        previous_scores_path=tmp_path / "scores.csv",
    )
    scores_path = tmp_path / "scores.csv"
    summary_path = tmp_path / "summary.csv"
    deductions_path = tmp_path / "deductions.csv"

    write_scores(scores_path, result, append=False)
    write_summary(summary_path, result, config)
    write_deductions(deductions_path, result)

    with scores_path.open("r", encoding="utf-8", newline="") as file:
        score_rows = list(csv.DictReader(file))
    assert score_rows[0]["run_id"] == "test-run"
    assert score_rows[0]["dimension_scores"]
    assert "recommended_actions" in score_rows[0]

    with summary_path.open("r", encoding="utf-8", newline="") as file:
        summary_rows = list(csv.DictReader(file))
    assert {row["dimension"] for row in summary_rows} >= {"retrieval_quality", "overall"}

    with deductions_path.open("r", encoding="utf-8", newline="") as file:
        deduction_rows = list(csv.DictReader(file))
    assert deduction_rows
    assert all("raw_response" not in json.dumps(row).lower() for row in deduction_rows)
