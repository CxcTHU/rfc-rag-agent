from pathlib import Path

from scripts.build_stage30_quality_report import render_report, validated_report_score, write_html, write_markdown


def score_row() -> dict[str, str]:
    return {"run_id": "stage30-test", "scoring_version": "stage30-v1", "scoring_mode": "deterministic_rule_based", "overall_score": "83.17", "grade": "B", "release_decision": "review_required", "score_delta": "", "recommended_actions": "Review low coverage | Keep human review"}


def summary_rows() -> list[dict[str, str]]:
    return [{"dimension": "retrieval_quality", "weight": "35.00", "score": "26.83", "max_score": "35.00", "normalized_score": "0.767", "status": "review_required", "evidence": "precision_at_1/3/5"}, {"dimension": "overall", "weight": "100.00", "score": "83.17", "max_score": "100.00", "normalized_score": "0.832", "status": "review_required", "evidence": "grade=B"}]


def deductions() -> list[dict[str, str]]:
    return [{"severity": "medium", "dimension": "rule_based_context_answer_quality", "query_id": "stage29_web_rfc_advantages", "deduction_points": "2.00", "deduction_reason": "Rule-based coverage is low; this is not semantic faithfulness.", "recommended_action": "Review missing points."}]


def health() -> dict[str, object]:
    return {"schema_version": "stage30-engineering-health-v2", "manifest_run_id": "phase65-current", "evidence_status": "current", "evidence_reasons": [], "full_tests_status": "556 passed", "quality_report_smoke": "passed", "chunk_count": 12716, "embedding_count": 25432, "jina_embedding_count": 12716, "deterministic_embedding_count": 12716, "orphan_embeddings": 0, "duplicate_provider_model_groups": 0}


def test_stage30_quality_report_markdown_documents_score_and_boundaries(tmp_path) -> None:
    path = tmp_path / "report.md"
    write_markdown(path, score_row(), summary_rows(), deductions(), health())
    report = path.read_text(encoding="utf-8")
    assert "overall_score：83.17" in report
    assert "release_decision：review_required" in report
    assert "不是 faithfulness" in report
    assert "不调用真实模型" in report


def test_stage30_quality_report_html_renders_score_payload(tmp_path) -> None:
    path = tmp_path / "quality_report.html"
    write_html(path, score_row(), summary_rows(), deductions(), health())
    rendered = path.read_text(encoding="utf-8")
    assert "阶段 30 RAG 质量评分与诚实门禁" in rendered
    assert "83.17" in rendered
    assert "review_required" in rendered
    assert "stage30_quality_summary.csv" in rendered
    assert "raw_response" not in rendered


def test_html_labels_historical_score_when_evidence_is_stale() -> None:
    rendered = render_report(evidence_status="stale", release_decision="pass")
    assert "历史评分，不可作为当前发布门禁" in rendered
    assert "当前发布门禁：PASS" not in rendered


def test_dynamic_html_explicitly_blocks_local_integrity_only_evidence(tmp_path) -> None:
    path = tmp_path / "quality_report.html"
    local_score = score_row() | {"evidence_status": "blocked", "evidence_reasons": "local_integrity_only", "release_decision": "blocked", "trust_level": "local_integrity_only"}
    write_html(path, local_score, summary_rows(), deductions(), health())
    rendered = path.read_text(encoding="utf-8")
    assert '"trust_level": "local_integrity_only"' in rendered
    assert "本地完整性证据，不是可信执行证明" in rendered
    assert "需要 CI/可信 runner 证明" in rendered


def test_stale_report_masks_current_pass_and_escapes_stored_fields(tmp_path) -> None:
    path = tmp_path / "quality_report.html"
    stale_score = score_row() | {"overall_score": "91.52", "grade": "A", "release_decision": "pass", "evidence_status": "stale", "evidence_reasons": "worktree_scoped_content_mismatch", "manifest_run_id": "phase65-current", "recommended_actions": '<img src=x onerror=alert(1)>'}
    write_html(path, stale_score, summary_rows(), deductions(), health())
    rendered = path.read_text(encoding="utf-8")
    assert '"release_decision": "pass"' not in rendered
    assert "<img src=x onerror=alert(1)>" not in rendered
    assert "\\u003cimg src=x onerror=alert(1)\\u003e" in rendered
    assert "function csvSafe" in rendered


def test_static_quality_page_does_not_keep_historical_pass_in_export_payload() -> None:
    static_html = (Path(__file__).resolve().parents[1] / "app" / "frontend" / "quality_report.html").read_text(encoding="utf-8")
    assert "历史评分，不可作为当前发布门禁" in static_html
    assert '"release_decision": "pass"' not in static_html


def test_report_builder_blocks_score_csv_without_revalidated_evidence() -> None:
    validated = validated_report_score(score_row() | {"release_decision": "pass"}, health=health(), manifest=None, test_receipt=None)
    assert validated["release_decision"] == "blocked"
    assert validated["evidence_status"] == "blocked"


def test_markdown_report_neutralizes_table_formula_links_and_controls(tmp_path) -> None:
    path = tmp_path / "report.md"
    write_markdown(path, score_row() | {"run_id": "=unsafe|column", "recommended_actions": "x`[link](javascript:alert(1))\r\nnext"}, summary_rows(), deductions(), health())
    report = path.read_text(encoding="utf-8")
    assert "'=unsafe\\|column" in report
    assert "x\\`\\[link\\]\\(javascript:alert\\(1\\)\\) next" in report


def test_report_csv_safe_normalizes_controls_before_formula_check() -> None:
    source = Path(__file__).resolve().parents[1] / "scripts" / "build_stage30_quality_report.py"
    assert 'replace(/[\\r\\n\\t]/g, " ").trim()' in source.read_text(encoding="utf-8")
