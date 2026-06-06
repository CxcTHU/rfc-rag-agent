from types import SimpleNamespace

from app.services.retrieval.embedding import OpenAICompatibleEmbeddingProvider
from scripts.build_vector_index import build_embedding_provider_from_args


def test_build_vector_index_provider_defaults_to_deterministic() -> None:
    args = SimpleNamespace(
        provider="",
        model_name="",
        api_key="",
        base_url="",
        dimension=0,
        timeout_seconds=0,
    )
    settings = SimpleNamespace(
        embedding_provider="",
        embedding_model_name="",
        embedding_api_key="",
        embedding_base_url="",
        embedding_dimension=0,
        embedding_timeout_seconds=30.0,
    )

    provider = build_embedding_provider_from_args(args, settings)

    assert provider.provider_name == "deterministic"


def test_build_vector_index_provider_uses_cli_embedding_configuration() -> None:
    args = SimpleNamespace(
        provider="openai-compatible",
        model_name="text-embedding-test",
        api_key="cli-key",
        base_url="https://models.example/v1",
        dimension=3,
        timeout_seconds=9,
    )
    settings = SimpleNamespace(
        embedding_provider="deterministic",
        embedding_model_name="settings-model",
        embedding_api_key="settings-key",
        embedding_base_url="https://settings.example/v1",
        embedding_dimension=64,
        embedding_timeout_seconds=30.0,
    )

    provider = build_embedding_provider_from_args(args, settings)

    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider.model_name == "text-embedding-test"
    assert provider.dimension == 3
    assert provider.timeout_seconds == 9


def test_build_vector_index_provider_falls_back_to_settings() -> None:
    args = SimpleNamespace(
        provider="",
        model_name="",
        api_key="",
        base_url="",
        dimension=0,
        timeout_seconds=0,
    )
    settings = SimpleNamespace(
        embedding_provider="openai-compatible",
        embedding_model_name="settings-model",
        embedding_api_key="settings-key",
        embedding_base_url="https://settings.example/v1",
        embedding_dimension=5,
        embedding_timeout_seconds=11.0,
    )

    provider = build_embedding_provider_from_args(args, settings)

    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider.model_name == "settings-model"
    assert provider.dimension == 5
    assert provider.timeout_seconds == 11.0
