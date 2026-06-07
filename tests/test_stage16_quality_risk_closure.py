from pathlib import Path


DESIGN_PATH = Path("docs/stage16_quality_risk_closure.md")


def test_stage_16_design_documents_core_artifacts_and_flow() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "真实质量风险闭环",
        "stage15 quality report",
        "data/evaluation/stage16_decompose_diagnostics.csv",
        "data/evaluation/stage16_answer_coverage_closure.csv",
        "data/evaluation/stage16_quality_closure_summary.csv",
        "docs/stage16_quality_closure_report.md",
        "quality gate",
    ]:
        assert phrase in design


def test_stage_16_design_defines_decompose_error_and_coverage_closure() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "SSL: UNEXPECTED_EOF_WHILE_READING",
        "provider_network_ssl_eof",
        "provider_timeout",
        "script_timeout_or_partial_output",
        "risk_before",
        "risk_after",
        "root_cause",
        "user_mixed_itz_strength",
        "Answer Coverage",
        "Faithfulness",
        "Citation Quality",
    ]:
        assert phrase in design


def test_stage_16_design_keeps_read_only_api_safe_manual_verification_boundary() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "POST /search",
        "POST /search/vector",
        "POST /search/hybrid",
        "POST /chat",
        "POST /agent/query",
        "不做写入型 Agent 工具",
        "不做复杂 LangGraph workflow",
        "不把 HyDE 接入默认链路或自动回归",
        "不保存 API key",
        "不保存受限全文",
        "不触发真实 API 调用",
        "不执行 `git add`",
        "等待用户人工核验",
    ]:
        assert phrase in design
