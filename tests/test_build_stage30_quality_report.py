from pathlib import Path

from scripts.build_stage30_quality_report import write_html, write_markdown


def score_row() -> dict[str, str]:
    return {
        "run_id": "stage30-test",
        "scoring_version": "stage30-v1",
        "scoring_mode": "deterministic_rule_based",
        "overall_score": "83.17",
        "grade": "B",
        "release_decision": "review_required",
        "score_delta": "",
        "recommended_actions": "Review low coverage | Keep human review",
    }


def summary_rows() -> list[dict[str, str]]:
    return [
        {
            "dimension": "retrieval_quality",
            "weight": "35.00",
            "score": "26.83",
            "max_score": "35.00",
            "normalized_score": "0.767",
            "status": "review_required",
            "evidence": "precision_at_1/3/5",
        },
        {
            "dimension": "overall",
            "weight": "100.00",
            "score": "83.17",
            "max_score": "100.00",
            "normalized_score": "0.832",
            "status": "review_required",
            "evidence": "grade=B",
        },
    ]


def deductions() -> list[dict[str, str]]:
    return [
        {
            "severity": "medium",
            "dimension": "rule_based_context_answer_quality",
            "query_id": "stage29_web_rfc_advantages",
            "deduction_points": "2.00",
            "deduction_reason": "Rule-based coverage is low; this is not semantic faithfulness.",
            "recommended_action": "Review missing points.",
        }
    ]


def health() -> dict[str, object]:
    return {
        "full_tests_status": "556 passed",
        "quality_report_smoke": "passed",
        "chunk_count": 12716,
        "embedding_count": 25432,
        "jina_embedding_count": 12716,
        "deterministic_embedding_count": 12716,
        "orphan_embeddings": 0,
        "duplicate_provider_model_groups": 0,
    }


def test_stage30_quality_report_markdown_documents_score_and_boundaries(tmp_path) -> None:
    path = tmp_path / "report.md"

    write_markdown(path, score_row(), summary_rows(), deductions(), health())

    report = path.read_text(encoding="utf-8")
    assert "overall_score：83.17" in report
    assert "release_decision：review_required" in report
    assert "rule_based_context_answer_quality" in report
    assert "不是 faithfulness" in report
    assert "不调用真实模型" in report


def test_stage30_quality_report_html_renders_score_payload(tmp_path) -> None:
    path = tmp_path / "quality_report.html"

    write_html(path, score_row(), summary_rows(), deductions(), health())

    html = path.read_text(encoding="utf-8")
    assert "阶段 30 RAG 质量评分与诚实门禁" in html
    assert "83.17" in html
    assert "review_required" in html
    assert "stage30_quality_summary.csv" in html
    assert "raw_response" not in html
