from pathlib import Path


DESIGN_PATH = Path("docs/stage15_real_review_report.md")


def test_stage_15_design_documents_core_artifacts_and_flow() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "真实配置复跑",
        "deterministic baseline",
        "data/evaluation/stage14_real/",
        "data/evaluation/stage15_answer_coverage_review.csv",
        "data/evaluation/stage15_quality_summary.csv",
        "只读报告",
        "stage14 quality tables",
        "real provider readiness check",
    ]:
        assert phrase in design


def test_stage_15_design_defines_review_rubric_and_skip_rules() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "Faithfulness",
        "Answer Coverage",
        "Citation Quality",
        "Graceful Skip",
        "skipped",
        "HTTP 429",
        "不伪造成功结果",
        "不访问真实网络",
    ]:
        assert phrase in design


def test_stage_15_design_keeps_report_read_only_and_api_compatible() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "POST /search",
        "POST /search/vector",
        "POST /search/hybrid",
        "POST /chat",
        "POST /agent/query",
        "不做写入型 Agent 工具",
        "不做复杂 LangGraph workflow",
        "不做 HyDE 默认链路或自动回归",
        "不保存 API key",
        "不保存受限全文",
        "不触发真实 API 调用",
    ]:
        assert phrase in design
