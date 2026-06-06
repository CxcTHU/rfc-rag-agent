from pathlib import Path


def test_stage_8_brain_workflow_design_documents_core_boundaries() -> None:
    design = Path("docs/brain_workflow_design.md").read_text(encoding="utf-8")

    for phrase in [
        "BrainService",
        "RetrievalConfig",
        "WorkflowConfig",
        "filter_history",
        "rewrite_query",
        "retrieve",
        "optional_rerank",
        "generate_answer",
    ]:
        assert phrase in design

    for boundary in [
        "不引入复杂 LangGraph workflow",
        "不照搬 Quivr",
        "不直接写 SQL",
        "不自动执行 source reindex",
        "不联网爬取新资料",
    ]:
        assert boundary in design


def test_stage_8_brain_workflow_design_documents_reuse_and_evaluation() -> None:
    design = Path("docs/brain_workflow_design.md").read_text(encoding="utf-8")

    for phrase in [
        "POST /chat",
        "POST /agent/query",
        "AgentToolbox.answer_with_citations",
        "scripts/evaluate_brain_workflow.py",
        "data/evaluation/brain_workflow_results.csv",
        "default_hybrid",
        "keyword_baseline",
        "vector_only",
    ]:
        assert phrase in design
