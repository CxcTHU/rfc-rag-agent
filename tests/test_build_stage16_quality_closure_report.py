from pathlib import Path

from scripts.build_stage16_quality_closure_report import (
    build_quality_closure_summary,
    write_html_report,
    write_markdown_report,
    write_summary,
)


def write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def seed_inputs(tmp_path: Path) -> tuple[Path, Path]:
    diagnostics = tmp_path / "stage16_decompose_diagnostics.csv"
    closure = tmp_path / "stage16_answer_coverage_closure.csv"
    write_csv(
        diagnostics,
        "diagnostic_id,suite,status_before,status_after,error_type,root_cause,reproducibility,safe_to_retry,blocking_status,evidence,next_action\n"
        "d1,decompose,error,classified_external_provider_error,ssl_eof,provider_network_ssl_eof,recorded,yes,manual_retry_required,evidence,retry\n",
    )
    write_csv(
        closure,
        "closure_id,source_review_id,query_id,risk_before,risk_after,faithfulness,answer_coverage,citation_quality,root_cause,evidence,decision,next_action,manual_review_note\n"
        "c1,r1,q1,high,high,review,fail,review,provider_timeout,evidence,blocking,retry,note\n"
        "c2,r2,q2,medium,low,pass,pass,pass,reviewed_sufficient,evidence,accepted,done,note\n"
        "c3,r3,q3,medium,medium,pass,review,pass,source_detail_limited,evidence,accepted_with_review,review,note\n",
    )
    return diagnostics, closure


def test_build_quality_closure_summary_combines_decompose_and_coverage(tmp_path) -> None:
    diagnostics, closure = seed_inputs(tmp_path)

    rows = build_quality_closure_summary(
        decompose_diagnostics_path=diagnostics,
        coverage_closure_path=closure,
    )

    assert any(row.section == "decompose" and row.metric == "decompose" for row in rows)
    assert any(row.section == "answer_coverage" and row.metric == "risk_after_high" and row.value == "1" for row in rows)
    assert rows[-1].section == "overall"
    assert rows[-1].status == "review_required"
    assert rows[-1].risk_after == "high"


def test_overall_gate_points_to_answer_coverage_when_decompose_retry_passes(tmp_path) -> None:
    diagnostics = tmp_path / "stage16_decompose_diagnostics.csv"
    closure = tmp_path / "stage16_answer_coverage_closure.csv"
    write_csv(
        diagnostics,
        "diagnostic_id,suite,status_before,status_after,error_type,root_cause,reproducibility,safe_to_retry,blocking_status,evidence,next_action\n"
        "d1,decompose,error,retry_completed,none_after_retry,embedding_header_compatibility_and_chat_timeout,retry,no,not_blocking,evidence,keep retry result\n",
    )
    write_csv(
        closure,
        "closure_id,source_review_id,query_id,risk_before,risk_after,faithfulness,answer_coverage,citation_quality,root_cause,evidence,decision,next_action,manual_review_note\n"
        "c1,r1,user_mixed_itz_strength,high,high,review,fail,review,provider_timeout,evidence,blocking,retry,note\n",
    )

    rows = build_quality_closure_summary(
        decompose_diagnostics_path=diagnostics,
        coverage_closure_path=closure,
    )

    assert rows[-1].section == "overall"
    assert "Answer Coverage" in rows[-1].recommendation
    assert "重试真实 provider" not in rows[-1].recommendation


def test_report_writers_create_stage16_outputs(tmp_path) -> None:
    diagnostics, closure = seed_inputs(tmp_path)
    rows = build_quality_closure_summary(
        decompose_diagnostics_path=diagnostics,
        coverage_closure_path=closure,
    )
    summary_out = tmp_path / "stage16_quality_closure_summary.csv"
    markdown_out = tmp_path / "stage16_quality_closure_report.md"
    html_out = tmp_path / "quality_report.html"

    write_summary(summary_out, rows)
    write_markdown_report(markdown_out, rows)
    write_html_report(html_out, rows)

    assert "section,metric,status,value" in summary_out.read_text(encoding="utf-8")
    assert "阶段 16 质量风险闭环报告" in markdown_out.read_text(encoding="utf-8")
    html = html_out.read_text(encoding="utf-8")
    assert "阶段 16 质量风险闭环报告" in html
    assert "不触发真实 API 调用" in html
    assert "api_key" not in html.casefold()
