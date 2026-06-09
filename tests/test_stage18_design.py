from pathlib import Path


DESIGN_PATH = Path("docs/stage18_corpus_evaluation_quality.md")


def test_stage_18_design_documents_core_artifacts_and_flow() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "语料扩充与评测/质量体系增强",
        "keep_existing_hybrid",
        "app/services/ingestion/pdf_text.py",
        "scripts/expand_open_access_corpus.py",
        "data/evaluation/stage18_hard_queries.csv",
        "scripts/evaluate_stage18_hard_set.py",
        "data/evaluation/stage18_hard_results.csv",
        "scripts/build_stage18_quality_report.py",
        "data/evaluation/stage18_quality_summary.csv",
        "docs/stage18_quality_report.md",
    ]:
        assert phrase in design


def test_stage_18_design_defines_corpus_eval_and_quality_rules() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "PDF 解析加固",
        "heading",
        "table",
        "难评测集",
        "跨段证据",
        "易混淆术语",
        "需拒答边界",
        "多配置对比",
        "bm25_rrf",
        "context expansion",
        "quality gate",
        "诚实报数",
        "不用静默 fallback 掩盖差异",
        "mesoscopic_modeling",
    ]:
        assert phrase in design


def test_stage_18_design_keeps_api_safety_and_manual_verification_boundary() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "POST /search",
        "POST /search/vector",
        "POST /search/hybrid",
        "POST /chat",
        "POST /agent/query",
        "GET /quality-report",
        "不做写入型 Agent 工具",
        "不做复杂 LangGraph workflow",
        "不做登录系统",
        "不把 HyDE 接入默认链路或自动回归",
        "不绕付费墙",
        "不保存 API key",
        "deterministic baseline 可复跑",
        "不执行 `git add`",
        "等待用户人工核验",
    ]:
        assert phrase in design
