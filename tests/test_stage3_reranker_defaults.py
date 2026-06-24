from app.core.config import Settings
from app.schemas.agent import AgentQueryRequest
from app.schemas.chat import ChatRequest
from app.services.brain.config import RetrievalConfig


def test_stage3_quality_first_reranker_defaults(monkeypatch) -> None:
    for key in [
        "RERANKING_PROVIDER",
        "RERANKING_MODEL_NAME",
        "RERANKING_API_KEY",
        "RERANKING_BASE_URL",
        "RERANKING_RECALL_K",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.reranking_provider == "remote-bge-lora"
    assert settings.reranking_model_name == "rfc-domain-bge-lora"
    assert settings.reranking_base_url == "http://127.0.0.1:8091"
    assert settings.reranking_recall_k == 75
    assert settings.reranking_api_key == ""


def test_stage3_quality_first_final_top_k_defaults() -> None:
    assert ChatRequest(question="What is RFC?").top_k == 8
    assert AgentQueryRequest(question="What is RFC?").top_k == 8
    assert RetrievalConfig().top_k == 8
    assert RetrievalConfig.from_chat_request().top_k == 8
