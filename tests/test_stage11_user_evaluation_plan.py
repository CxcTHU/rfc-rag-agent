from pathlib import Path
import csv


PLAN_PATH = Path("docs/stage11_user_evaluation_plan.md")
REVIEW_SAMPLES_PATH = Path("data/evaluation/user_question_review_samples.csv")


def test_stage_11_user_evaluation_plan_documents_paths_and_metrics() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "data/evaluation/user_questions.csv",
        "scripts/evaluate_user_questions.py",
        "data/evaluation/user_question_results.csv",
        "data/evaluation/user_question_review_samples.csv",
        "Faithfulness",
        "Answer Coverage",
        "Citation Quality",
        "LLM-as-judge",
    ]:
        assert phrase in plan


def test_stage_11_user_evaluation_plan_keeps_real_keys_out_of_regression() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "不依赖真实 API key",
        "不让自动测试依赖真实 API key",
        "不进入 CI",
        "deterministic provider",
    ]:
        assert phrase in plan


def test_stage_11_review_samples_schema_and_coverage() -> None:
    with REVIEW_SAMPLES_PATH.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    expected_fields = {
        "sample_id",
        "query_id",
        "language_type",
        "config_name",
        "question",
        "expected_answer_points",
        "source_titles",
        "answer_excerpt",
        "faithfulness",
        "answer_coverage",
        "citation_quality",
        "reviewer_notes",
        "judge_prompt",
        "notes",
    }
    assert set(rows[0]) == expected_fields
    assert len(rows) >= 5
    assert {row["faithfulness"] for row in rows} == {"pending"}
    assert {row["answer_coverage"] for row in rows} == {"pending"}
    assert {row["citation_quality"] for row in rows} == {"pending"}
    assert {"zh_colloquial", "en", "mixed", "engineering_cn", "unsupported"} <= {
        row["language_type"] for row in rows
    }
    assert {"default_hybrid", "vector_only"} <= {row["config_name"] for row in rows}


def test_stage_11_review_samples_do_not_store_secrets_or_restricted_fulltext() -> None:
    content = REVIEW_SAMPLES_PATH.read_text(encoding="utf-8").casefold()

    for forbidden in [
        "sk-",
        "api_key=",
        "bearer ",
        "mimo_api_key",
        "jina_api_key",
        "-----begin",
    ]:
        assert forbidden not in content

    for restricted in [
        "full abstract",
        "full paper",
        "完整全文",
        "受限全文",
    ]:
        assert restricted not in content
