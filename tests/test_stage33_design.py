from pathlib import Path


def test_stage33_design_documents_performance_scope_and_boundaries() -> None:
    design = Path("docs/stage33_rag_performance_embedding_validation.md").read_text(
        encoding="utf-8"
    )

    for phrase in [
        "VectorIndexCache",
        "FAISS-only",
        "numpy_fallback",
        "GLM-Embedding-3",
        "2048",
        "Jina",
        "DeepSeek",
        "MIMO",
    ]:
        assert phrase in design

    for boundary in [
        "不删除旧 Jina",
        "不直接切换默认 MIMO provider",
        "不新增外部数据源",
        "不新增写入型 Agent 工具",
        "不让真实 API 成为 CI 或本地全量测试前提",
    ]:
        assert boundary in design


def test_stage33_design_documents_safe_latency_trace() -> None:
    design = Path("docs/stage33_rag_performance_embedding_validation.md").read_text(
        encoding="utf-8"
    )

    for metric in [
        "query_embedding_latency_ms",
        "faiss_search_latency_ms",
        "rerank_latency_ms",
        "planner_latency_ms",
        "answer_latency_ms",
        "tool_latency_ms",
        "time_to_first_token_ms",
        "time_to_final_ms",
        "iteration_count",
        "tool_call_count",
    ]:
        assert metric in design

    for forbidden in [
        "hidden thought",
        "reasoning_content",
        "provider raw response",
        "API key",
        "Bearer token",
        "受限全文",
    ]:
        assert forbidden in design
