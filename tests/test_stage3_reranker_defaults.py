from app.core.config import Settings
from app.schemas.agent import AgentQueryRequest
from app.schemas.chat import ChatRequest
from app.services.brain.config import RetrievalConfig


def test_default_reranker_uses_glm_when_bge_gpu_is_unavailable(monkeypatch) -> None:
    for key in [
        "RERANKING_PROVIDER",
        "RERANKING_MODEL_NAME",
        "RERANKING_API_KEY",
        "RERANKING_BASE_URL",
        "RERANKING_RECALL_K",
        "RERANKING_FALLBACK_ENABLED",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.reranking_provider == "paratera"
    assert settings.reranking_model_name == "GLM-Rerank"
    assert settings.reranking_base_url == "https://llmapi.paratera.com/v1/p002"
    assert settings.reranking_fallback_enabled is False
    assert settings.reranking_recall_k == 75
    assert settings.reranking_api_key == ""


def test_stage3_quality_first_final_top_k_defaults() -> None:
    assert ChatRequest(question="What is RFC?").top_k == 8
    assert AgentQueryRequest(question="What is RFC?").top_k == 8
    assert RetrievalConfig().top_k == 8
    assert RetrievalConfig.from_chat_request().top_k == 8


def test_paratera_primary_reranker_reuses_existing_embedding_key(monkeypatch) -> None:
    monkeypatch.setenv("RERANKING_PROVIDER", "paratera")
    monkeypatch.delenv("RERANKING_API_KEY", raising=False)
    monkeypatch.delenv("RERANKING_FALLBACK_API_KEY", raising=False)
    monkeypatch.setenv("EMBEDDING_API_KEY", "embedding-route-key")

    settings = Settings(_env_file=None)

    assert settings.reranking_provider == "paratera"
    assert settings.reranking_api_key == "embedding-route-key"
