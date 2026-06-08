from pathlib import Path


DESIGN_PATH = Path("docs/stage17_retrieval_architecture_upgrade.md")


def test_stage_17_design_documents_core_artifacts_and_flow() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "检索架构升级",
        "stage16 quality conclusion",
        "app/services/retrieval/bm25_search.py",
        "app/services/retrieval/rrf_fusion.py",
        "data/evaluation/stage17_retrieval_upgrade_results.csv",
        "docs/stage17_retrieval_upgrade_report.md",
        "baseline comparison report",
    ]:
        assert phrase in design


def test_stage_17_design_defines_bm25_rrf_context_and_baseline_rules() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "BM25",
        "lexical retriever",
        "RRF",
        "Reciprocal Rank Fusion",
        "deduplicate by chunk_id",
        "context expansion",
        "parent chunk",
        "child chunk",
        "不覆盖旧 baseline",
        "不得用不同尺度分数硬加权冒充融合",
    ]:
        assert phrase in design


def test_stage_17_design_keeps_api_safety_and_manual_verification_boundary() -> None:
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
        "不把 HyDE 接入默认链路或自动回归",
        "不优先引入 HNSW",
        "不保存 API key",
        "不保存受限全文",
        "不让真实 API 成为 CI",
        "不执行 `git add`",
        "等待用户人工核验",
    ]:
        assert phrase in design
