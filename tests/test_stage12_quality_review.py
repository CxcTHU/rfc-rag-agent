from pathlib import Path
import csv


REPORT_PATH = Path("docs/stage12_quality_review.md")
RESULTS_PATH = Path("data/evaluation/stage12_quality_review_results.csv")


def test_stage_12_quality_review_report_documents_scope_and_artifacts() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    for phrase in [
        "data/evaluation/stage12_quality_review_results.csv",
        "data/evaluation/user_question_results.csv",
        "data/evaluation/user_question_review_samples.csv",
        "Faithfulness",
        "Answer Coverage",
        "Citation Quality",
        "default_hybrid",
        "vector_only",
        "HyDE",
        "阶段 13",
    ]:
        assert phrase in report


def test_stage_12_quality_review_results_schema_and_coverage() -> None:
    with RESULTS_PATH.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    expected_fields = {
        "sample_id",
        "query_id",
        "language_type",
        "config_name",
        "question",
        "expected_answer_points",
        "automatic_status",
        "faithfulness",
        "answer_coverage",
        "citation_quality",
        "risk_level",
        "reviewer_notes",
        "next_action",
    }
    assert set(rows[0]) == expected_fields
    assert len(rows) >= 6
    assert {"default_hybrid", "vector_only"} <= {row["config_name"] for row in rows}
    assert {"zh_colloquial", "en", "mixed", "engineering_cn", "unsupported"} <= {
        row["language_type"] for row in rows
    }
    assert {"pass", "review"} <= {row["faithfulness"] for row in rows}
    assert {"pass", "review", "fail"} <= {row["answer_coverage"] for row in rows}
    assert {"pass", "review"} <= {row["citation_quality"] for row in rows}
    assert {"low", "medium", "high"} <= {row["risk_level"] for row in rows}


def test_stage_12_quality_review_keeps_real_keys_and_restricted_fulltext_out() -> None:
    combined = (
        REPORT_PATH.read_text(encoding="utf-8")
        + "\n"
        + RESULTS_PATH.read_text(encoding="utf-8")
    ).casefold()

    for forbidden in [
        "sk-",
        "api_key=",
        "bearer ",
        "mimo_api_key",
        "jina_api_key",
        "-----begin",
    ]:
        assert forbidden not in combined

    for restricted in [
        "full paper",
        "完整全文",
        "受限全文内容",
    ]:
        assert restricted not in combined


def test_stage_12_quality_review_keeps_hyde_out_of_default_regression() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    for phrase in [
        "只作为离线实验建议",
        "不进入默认链路或自动回归",
        "继续使用 deterministic provider 做稳定测试",
    ]:
        assert phrase in report
