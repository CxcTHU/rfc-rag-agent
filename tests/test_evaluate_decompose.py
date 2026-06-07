from pathlib import Path

from scripts.evaluate_decompose import (
    PRIORITY_QUERY_IDS,
    RESULT_FIELDS,
    EvaluatedDecomposeResult,
    actual_source_hit_for_expected_question,
    failure_reason,
    select_questions,
)
from scripts.evaluate_user_questions import read_expected_questions


def test_decompose_evaluation_selects_priority_questions() -> None:
    questions = read_expected_questions(Path("data/evaluation/user_questions.csv"))
    selected = select_questions(questions)

    assert {question.query_id for question in selected} == PRIORITY_QUERY_IDS
    assert "user_unsupported_random" in {question.query_id for question in selected}


def test_decompose_evaluation_result_fields_include_stage_13_metrics() -> None:
    for field in [
        "decompose_applied",
        "sub_query_count",
        "deduplicated_count",
        "provenance_present",
        "answer_coverage_proxy",
        "rerank_explanations",
    ]:
        assert field in RESULT_FIELDS


def test_decompose_evaluation_row_serializes_bool_fields() -> None:
    result = EvaluatedDecomposeResult(
        query_id="q",
        question="question",
        language_type="mixed",
        passed=True,
        expected_refused=False,
        brain_refused=False,
        refusal_matched=True,
        decompose_applied=True,
        sub_query_count=2,
        sub_queries=("a", "b"),
        raw_result_count=4,
        merged_result_count=3,
        deduplicated_count=1,
        provenance_present=True,
        expected_source_hit=True,
        actual_source_hit=True,
        source_hit_matched=True,
        answer_coverage_proxy=True,
        top_source_titles="title",
        rerank_explanations="explanation",
        failed_reason="",
        notes="notes",
    )

    row = result.to_row()

    assert row["passed"] == "yes"
    assert row["decompose_applied"] == "yes"
    assert row["sub_queries"] == "a || b"
    assert row["deduplicated_count"] == "1"


def test_decompose_failure_reason_combines_failed_checks() -> None:
    reason = failure_reason(
        passed=False,
        refusal_matched=False,
        source_hit_matched=False,
        provenance_present=True,
        answer_coverage_proxy=False,
    )

    assert reason == "refusal_mismatch|source_hit_mismatch|answer_coverage_proxy_failed"


def test_decompose_actual_source_hit_treats_no_source_expected_as_no_sources() -> None:
    question = next(
        item
        for item in read_expected_questions(Path("data/evaluation/user_questions.csv"))
        if item.query_id == "user_unsupported_random"
    )

    assert actual_source_hit_for_expected_question(question, []) is False
    assert actual_source_hit_for_expected_question(question, [object()]) is True
