from pathlib import Path


DESIGN_PATH = Path("docs/stage14_real_quality_calibration.md")


def test_stage_14_design_documents_core_artifacts_and_flow() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "真实 embedding",
        "deterministic baseline",
        "provider/model/dimension",
        "data/evaluation/stage14_embedding_comparison.csv",
        "data/evaluation/stage14_answer_coverage_review.csv",
        "stage13_decompose_results.csv",
        "Decompose provenance",
        "rerank explanation",
    ]:
        assert phrase in design


def test_stage_14_design_defines_quality_rubric_and_skip_rules() -> None:
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


def test_stage_14_design_keeps_boundaries_and_api_compatibility() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "POST /search",
        "POST /search/vector",
        "POST /search/hybrid",
        "POST /chat",
        "POST /agent/query",
        "不做写入型 Agent 工具",
        "不做复杂 LangGraph workflow",
        "HyDE 默认链路或自动回归",
        "不保存 API key",
        "不保存受限全文",
    ]:
        assert phrase in design
