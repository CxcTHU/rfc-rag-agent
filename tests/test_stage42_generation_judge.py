from argparse import Namespace
from pathlib import Path

from scripts.judge_stage42_generation_quality import (
    LOW_SCORE_FIELDS,
    RESULT_FIELDS,
    analyze_low_scores,
    build_rows,
    load_stage42_cases,
    summarize,
    write_csv,
)


def test_stage42_judge_loads_stage38_and_stage41_cases() -> None:
    cases = load_stage42_cases(Path("data/evaluation/stage41_post_import_retrieval_queries.csv"))

    assert len(cases) == 36
    assert sum(1 for case in cases if case.case_source == "stage38") == 24
    assert sum(1 for case in cases if case.case_source == "stage41") == 12
    assert any(case.query_id == "stage41_cn_rfc_flow_filling" for case in cases)
    assert any(case.expected_refused for case in cases if case.case_source == "stage38")
    assert not any(case.expected_refused for case in cases if case.case_source == "stage41")


def test_stage42_judge_dry_run_builds_one_structured_row_per_case() -> None:
    args = Namespace(
        execute=False,
        judge_provider="judge",
        judge_model="judge-model",
        judge_base_url="",
        judge_api_key="",
    )
    cases = load_stage42_cases(Path("data/evaluation/stage41_post_import_retrieval_queries.csv"))[:4]

    rows = build_rows(args, cases)

    assert len(rows) == 4
    assert {row["strategy"] for row in rows} == {"structured_final_answer"}
    assert {row["status"] for row in rows} == {"dry_run"}
    assert all(set(row) == set(RESULT_FIELDS) for row in rows)


def test_stage42_judge_summary_uses_six_metric_gate() -> None:
    rows = [
        {
            "case_source": "stage38",
            "strategy": "structured_final_answer",
            "status": "completed",
            "faithfulness": "0.900",
            "answer_coverage": "0.810",
            "citation_support": "0.830",
            "refusal_correctness": "0.900",
            "conciseness": "0.850",
            "safety_leak_check": "1.000",
            "risk_level": "low",
        },
        {
            "case_source": "stage41",
            "strategy": "structured_final_answer",
            "status": "completed",
            "faithfulness": "0.900",
            "answer_coverage": "0.790",
            "citation_support": "0.850",
            "refusal_correctness": "1.000",
            "conciseness": "0.900",
            "safety_leak_check": "1.000",
            "risk_level": "low",
        },
    ]

    summary = summarize(rows)

    assert summary["stage38_rows"] == "1"
    assert summary["stage41_rows"] == "1"
    assert summary["avg_answer_coverage"] == "0.800"
    assert summary["judge_gate"] == "pass"


def test_stage42_judge_low_score_analysis_classifies_prompt_gaps() -> None:
    rows = [
        {
            "status": "completed",
            "query_id": "q1",
            "case_source": "stage41",
            "category": "new_cn_rfc",
            "expected_refused": "false",
            "answer_coverage": "0.900",
            "citation_support": "0.650",
            "risk_level": "medium",
            "short_reason": "citation is not close enough to the claim",
            "next_action": "tighten citation instructions",
        }
    ]

    low_score_rows = analyze_low_scores(rows)

    assert len(low_score_rows) == 1
    assert set(low_score_rows[0]) == set(LOW_SCORE_FIELDS)
    assert low_score_rows[0]["root_cause"] == "prompt_citation_gap"


def test_stage42_judge_csv_omits_sensitive_raw_content(tmp_path: Path) -> None:
    args = Namespace(
        execute=False,
        judge_provider="judge",
        judge_model="judge-model",
        judge_base_url="",
        judge_api_key="",
    )
    cases = load_stage42_cases(Path("data/evaluation/stage41_post_import_retrieval_queries.csv"))[:1]
    rows = build_rows(args, cases)
    path = tmp_path / "stage42_judge.csv"

    write_csv(path, RESULT_FIELDS, rows)
    text = path.read_text(encoding="utf-8").lower()

    assert "raw_response" not in text
    assert "reasoning_content" not in text
    assert "bearer " not in text
    assert "authorization" not in text
