from argparse import Namespace
from pathlib import Path

from scripts.judge_stage38_tool_calling_quality import (
    EVAL_CASES,
    RESULT_FIELDS,
    STRATEGIES,
    build_rows,
    expected_refused_for_case,
    read_csv,
    summarize,
    write_csv,
)


def test_stage38_judge_dry_run_builds_two_strategy_rows_per_case() -> None:
    args = Namespace(
        execute=False,
        judge_provider="judge",
        judge_model="judge-model",
        judge_base_url="",
        judge_api_key="",
    )
    rows = build_rows(args, EVAL_CASES[:3])

    assert len(rows) == 3 * len(STRATEGIES)
    assert {row["strategy"] for row in rows} == set(STRATEGIES)
    assert {row["status"] for row in rows} == {"dry_run"}
    assert all(set(row) == set(RESULT_FIELDS) for row in rows)


def test_stage38_judge_summary_marks_pass_and_review_required() -> None:
    rows = [
        {
            "strategy": "baseline",
            "status": "completed",
            "faithfulness": "0.950",
            "answer_coverage": "0.700",
            "citation_support": "0.820",
            "refusal_correctness": "1.000",
            "conciseness": "0.900",
            "safety_leak_check": "1.000",
            "risk_level": "medium",
        },
        {
            "strategy": "structured_final_answer",
            "status": "completed",
            "faithfulness": "0.950",
            "answer_coverage": "0.810",
            "citation_support": "0.830",
            "refusal_correctness": "0.900",
            "conciseness": "0.850",
            "safety_leak_check": "1.000",
            "risk_level": "low",
        },
    ]

    by_strategy = {row["strategy"]: row for row in summarize(rows)}

    assert by_strategy["baseline"]["judge_gate"] == "review_required"
    assert by_strategy["structured_final_answer"]["judge_gate"] == "pass"
    assert by_strategy["structured_final_answer"]["avg_faithfulness"] == "0.950"
    assert by_strategy["structured_final_answer"]["avg_refusal_correctness"] == "0.900"


def test_stage38_judge_summary_requires_all_six_metrics() -> None:
    rows = [
        {
            "strategy": "baseline",
            "status": "completed",
            "faithfulness": "0.950",
            "answer_coverage": "0.900",
            "citation_support": "0.900",
            "refusal_correctness": "0.790",
            "conciseness": "0.900",
            "safety_leak_check": "1.000",
            "risk_level": "low",
        },
        {
            "strategy": "structured_final_answer",
            "status": "completed",
            "faithfulness": "0.950",
            "answer_coverage": "0.900",
            "citation_support": "0.900",
            "refusal_correctness": "0.900",
            "conciseness": "0.900",
            "safety_leak_check": "1.000",
            "risk_level": "low",
        },
    ]

    by_strategy = {row["strategy"]: row for row in summarize(rows)}

    assert by_strategy["baseline"]["judge_gate"] == "review_required"
    assert by_strategy["structured_final_answer"]["judge_gate"] == "pass"


def test_stage38_judge_expected_refusal_mapping() -> None:
    by_category = {case.category: case for case in EVAL_CASES}

    assert expected_refused_for_case(by_category["off_topic"])
    assert expected_refused_for_case(by_category["responsibility_boundary"])
    assert expected_refused_for_case(by_category["evidence_insufficient"])
    assert not expected_refused_for_case(by_category["single_hop"])


def test_stage38_judge_csv_omits_raw_sensitive_content(tmp_path: Path) -> None:
    args = Namespace(
        execute=False,
        judge_provider="judge",
        judge_model="judge-model",
        judge_base_url="",
        judge_api_key="",
    )
    rows = build_rows(args, EVAL_CASES[:1])
    path = tmp_path / "judge.csv"

    write_csv(path, RESULT_FIELDS, rows)
    text = path.read_text(encoding="utf-8")

    assert "raw_response" not in text
    assert "reasoning_content" not in text
    assert "Bearer " not in text


def test_stage38_judge_can_read_existing_results_for_summary(tmp_path: Path) -> None:
    path = tmp_path / "judge.csv"
    rows = [
        {
            field: "0.900" if field.startswith(("faithfulness", "answer", "citation", "refusal", "conciseness", "safety")) else ""
            for field in RESULT_FIELDS
        }
    ]
    rows[0]["strategy"] = "structured_final_answer"
    rows[0]["status"] = "completed"
    rows[0]["risk_level"] = "low"

    write_csv(path, RESULT_FIELDS, rows)

    assert read_csv(path)[0]["strategy"] == "structured_final_answer"
