from pathlib import Path


DESIGN_PATH = Path("docs/stage35_retrieval_quality_calibration.md")


def test_stage35_design_documents_quality_goal_and_flow() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "overall_score >= 88",
        "grade >= A-",
        "release_decision=pass",
        "Stage 30 扣分根因分类",
        "真实 Judge 复跑",
        "stage35_deduction_root_causes.csv",
        "stage35_llm_judge_results.csv",
    ]:
        assert phrase in design


def test_stage35_design_documents_root_cause_classes() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for root_cause in [
        "retrieval_miss",
        "context_expansion_miss",
        "prompt_citation_gap",
        "answer_coverage_gap",
        "rule_too_strict",
    ]:
        assert root_cause in design


def test_stage35_design_documents_dual_gate_validation() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for metric in [
        "citation_support >= 0.80",
        "answer_coverage >= 0.80",
        "high=0",
        "python scripts/score_stage30_quality.py",
        "真实 Judge 不进入 CI",
        "skipped",
        "error",
    ]:
        assert metric in design


def test_stage35_design_keeps_provider_api_and_safety_boundaries() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for boundary in [
        "不替换默认 chat provider",
        "不替换默认 embedding provider",
        "不替换 rerank provider",
        "不新增外部数据源",
        "不做写入型 Agent 工具",
        "不做 tool-calling 协议迁移",
        "/chat",
        "/agent/query",
        "/agent/query/stream",
        "/search/*",
        "/quality-report",
    ]:
        assert boundary in design

    for forbidden in [
        "API key",
        "Bearer token",
        "raw provider response",
        "reasoning_content",
        "hidden thought",
        "受限全文",
    ]:
        assert forbidden in design
