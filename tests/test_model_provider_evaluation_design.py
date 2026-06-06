from pathlib import Path


def test_stage_9_model_provider_design_documents_core_boundaries() -> None:
    design = Path("docs/model_provider_evaluation.md").read_text(encoding="utf-8")

    for phrase in [
        "ChatModelProvider",
        "EmbeddingProvider",
        "OpenAICompatibleEmbeddingProvider",
        "DeterministicEmbeddingProvider",
        "OpenAI-compatible embedding provider",
        "EMBEDDING_DIMENSION",
        "EMBEDDING_TIMEOUT_SECONDS",
    ]:
        assert phrase in design

    for boundary in [
        "不做登录系统",
        "不做部署优化",
        "不做大规模前端重构",
        "不做写入型 Agent 工具",
        "不让测试依赖真实 API key",
    ]:
        assert boundary in design


def test_stage_9_model_provider_design_documents_index_and_evaluation() -> None:
    design = Path("docs/model_provider_evaluation.md").read_text(encoding="utf-8")

    for phrase in [
        "scripts/build_vector_index.py",
        "--model-name",
        "--dimension",
        "provider",
        "model_name",
        "content_hash",
        "scripts/evaluate_model_configs.py",
        "data/evaluation/model_config_results.csv",
        "deterministic_baseline",
        "real_config",
        "skipped",
    ]:
        assert phrase in design
