from pathlib import Path

from scripts.build_stage15_quality_report import (
    build_quality_summary,
    write_html_report,
    write_markdown_report,
    write_summary,
)


def write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def seed_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    comparison = tmp_path / "stage14_embedding_comparison.csv"
    status = tmp_path / "real_config_status.csv"
    coverage = tmp_path / "stage15_answer_coverage_review.csv"
    provenance = tmp_path / "stage14_decompose_provenance_review.csv"
    write_csv(
        comparison,
        "config_name,suite,status,passed,total,failed,pass_rate,skipped_reason\n"
        "deterministic_baseline,vector,completed,13,15,2,0.867,\n"
        "real_config,vector,completed,15,15,0,1.000,\n"
        "deterministic_baseline,decompose,completed,10,10,0,1.000,\n"
        "real_config,decompose,error,0,0,0,,SSL failed\n",
    )
    write_csv(
        status,
        "suite,status,output_file,embedding_provider,embedding_model_name,embedding_dimension,chat_provider,chat_model_name,skipped_reason,error_summary,notes\n"
        "vector,completed,vector.csv,openai-compatible,jina,1024,openai-compatible,mimo,,,\n"
        "decompose,error,decompose.csv,openai-compatible,jina,1024,openai-compatible,mimo,,SSL failed,\n",
    )
    write_csv(
        coverage,
        "review_id,query_id,risk_level,faithfulness,answer_coverage,citation_quality\n"
        "r1,q1,medium,pass,review,pass\n"
        "r2,q2,high,fail,fail,review\n",
    )
    write_csv(
        provenance,
        "query_id,decompose_applied,both_match\n"
        "q1,yes,yes\n"
        "q1,no,no\n",
    )
    return comparison, status, coverage, provenance


def test_build_quality_summary_combines_real_status_coverage_and_provenance(tmp_path) -> None:
    comparison, status, coverage, provenance = seed_inputs(tmp_path)

    rows = build_quality_summary(
        comparison_path=comparison,
        real_status_path=status,
        coverage_review_path=coverage,
        provenance_review_path=provenance,
    )

    assert any(row.section == "real_config" and row.metric == "vector" and row.value.startswith("15/15") for row in rows)
    assert any(row.section == "real_config" and row.metric == "decompose" and row.risk_level == "high" for row in rows)
    assert any(row.section == "answer_coverage" and row.metric == "risk_high" and row.value == "1" for row in rows)
    assert any(row.section == "provenance" and row.metric == "both_match_rows" and row.value == "1" for row in rows)
    assert rows[-1].section == "overall"


def test_report_writers_create_summary_markdown_and_html(tmp_path) -> None:
    comparison, status, coverage, provenance = seed_inputs(tmp_path)
    rows = build_quality_summary(
        comparison_path=comparison,
        real_status_path=status,
        coverage_review_path=coverage,
        provenance_review_path=provenance,
    )
    summary_out = tmp_path / "stage15_quality_summary.csv"
    markdown_out = tmp_path / "stage15_quality_report.md"
    html_out = tmp_path / "quality_report.html"

    write_summary(summary_out, rows)
    write_markdown_report(markdown_out, rows)
    write_html_report(html_out, rows)

    assert "section,metric,status,value" in summary_out.read_text(encoding="utf-8")
    assert "阶段 15 质量审阅报告" in markdown_out.read_text(encoding="utf-8")
    html = html_out.read_text(encoding="utf-8")
    assert "只读质量报告" in html
    assert "不触发真实 API 调用" in html
    assert "api_key" not in html.casefold()
