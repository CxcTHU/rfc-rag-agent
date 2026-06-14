from pathlib import Path


DESIGN_PATH = Path("docs/stage34_rag_diagnosis_embedding_judge.md")


def test_stage34_design_documents_core_scope_and_outputs() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "GLM-Embedding-3",
        "2048",
        "Jina",
        "1024",
        "同环境",
        "latency trace",
        "LLM Judge",
        "stage34_decision_summary.csv",
        "stage34_rag_diagnosis_decision_report.md",
    ]:
        assert phrase in design


def test_stage34_design_documents_required_metrics() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for metric in [
        "precision@1",
        "precision@3",
        "precision@5",
        "hit@5",
        "coverage",
        "refusal boundary",
        "latency_ms",
        "p50",
        "p90",
        "stage_share",
    ]:
        assert metric in design


def test_stage34_design_documents_judge_rubric_and_dry_run_boundary() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for metric in [
        "faithfulness",
        "answer_coverage",
        "citation_support",
        "refusal_correctness",
        "conciseness",
        "safety_leak_check",
    ]:
        assert metric in design

    assert "默认 dry-run" in design
    assert "--execute" in design


def test_stage34_design_documents_safety_and_no_default_switch() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for boundary in [
        "不删除旧 Jina",
        "不直接替换默认 GLM/Jina/MIMO/DeepSeek",
        "不新增外部数据源",
        "不新增写入型 Agent 工具",
        "不让真实 API",
        "不提交、不 tag、不 push、不建 PR",
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
