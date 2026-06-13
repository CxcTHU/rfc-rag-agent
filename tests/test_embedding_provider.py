import math
import json

import pytest

from app.services.retrieval.embedding import (
    DeterministicEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    create_embedding_provider,
    parse_openai_compatible_embeddings,
    tokenize,
)


def test_deterministic_embedding_provider_returns_expected_dimension() -> None:
    provider = DeterministicEmbeddingProvider(dimension=16)

    embedding = provider.embed_query("堆石混凝土 temperature control")

    assert len(embedding) == 16
    assert math.isclose(vector_norm(embedding), 1.0)


def test_deterministic_embedding_provider_is_stable() -> None:
    provider = DeterministicEmbeddingProvider(dimension=32)

    first = provider.embed_query("filling capacity of rock-filled concrete")
    second = provider.embed_query("filling capacity of rock-filled concrete")

    assert first == second


def test_deterministic_embedding_provider_handles_empty_text() -> None:
    provider = DeterministicEmbeddingProvider(dimension=8)

    embedding = provider.embed_query("   ")

    assert embedding == [0.0] * 8


def test_embed_texts_preserves_input_order() -> None:
    provider = DeterministicEmbeddingProvider(dimension=16)

    embeddings = provider.embed_texts(["elastic modulus", "seismic behavior"])

    assert embeddings == [
        provider.embed_query("elastic modulus"),
        provider.embed_query("seismic behavior"),
    ]


def test_tokenize_supports_english_words_and_chinese_characters() -> None:
    assert tokenize("RFC 堆石混凝土") == ["rfc", "堆", "石", "混", "凝", "土"]


def test_create_embedding_provider_defaults_to_deterministic() -> None:
    provider = create_embedding_provider()

    assert provider.provider_name == "deterministic"


def test_create_embedding_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        create_embedding_provider("unknown")


def test_create_embedding_provider_builds_openai_compatible_embedding_provider() -> None:
    provider = create_embedding_provider(
        "openai-compatible",
        model_name="text-embedding-test",
        api_key="test-key",
        base_url="https://models.example/v1",
        dimension=3,
    )

    assert provider.provider_name == "openai-compatible"
    assert provider.model_name == "text-embedding-test"
    assert provider.dimension == 3


def test_create_embedding_provider_builds_jina_alias_provider() -> None:
    provider = create_embedding_provider(
        "jina",
        model_name="jina-embeddings-v3",
        api_key="test-key",
        base_url="https://api.jina.ai/v1",
        dimension=1024,
    )

    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider.provider_name == "jina"
    assert provider.model_name == "jina-embeddings-v3"
    assert provider.dimension == 1024


def test_openai_compatible_embedding_provider_requires_configuration() -> None:
    with pytest.raises(ValueError, match="model_name"):
        OpenAICompatibleEmbeddingProvider(
            model_name="",
            api_key="test-key",
            base_url="https://models.example/v1",
            dimension=3,
        )

    with pytest.raises(ValueError, match="api_key"):
        OpenAICompatibleEmbeddingProvider(
            model_name="text-embedding-test",
            api_key="",
            base_url="https://models.example/v1",
            dimension=3,
        )

    with pytest.raises(ValueError, match="dimension"):
        create_embedding_provider(
            "openai-compatible",
            model_name="text-embedding-test",
            api_key="test-key",
            base_url="https://models.example/v1",
        )


def test_openai_compatible_embedding_provider_posts_embeddings_request(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(
                {
                    "data": [
                        {"index": 0, "embedding": [1, 0, 0]},
                        {"index": 1, "embedding": [0, 1, 0]},
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("app.services.retrieval.embedding.urlopen_without_proxy", fake_urlopen)
    provider = OpenAICompatibleEmbeddingProvider(
        model_name="text-embedding-test",
        api_key="test-key",
        base_url="https://models.example/v1",
        dimension=3,
        timeout_seconds=7,
    )

    embeddings = provider.embed_texts(["thermal control", "filling capacity"])

    assert embeddings == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert captured["url"] == "https://models.example/v1/embeddings"
    assert captured["timeout"] == 7
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["headers"]["Api-key"] == "test-key"
    assert captured["headers"]["Accept"] == "application/json"
    assert captured["headers"]["User-agent"] == "rfc-rag-agent/embedding-provider"
    assert captured["payload"] == {
        "model": "text-embedding-test",
        "input": ["thermal control", "filling capacity"],
    }


def test_openai_compatible_embedding_provider_rejects_dimension_mismatch(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps({"data": [{"index": 0, "embedding": [1, 0]}]}).encode("utf-8")

    monkeypatch.setattr(
        "app.services.retrieval.embedding.urlopen_without_proxy",
        lambda request, timeout: FakeResponse(),
    )
    provider = OpenAICompatibleEmbeddingProvider(
        model_name="text-embedding-test",
        api_key="test-key",
        base_url="https://models.example/v1/embeddings",
        dimension=3,
    )

    with pytest.raises(RuntimeError, match="dimension"):
        provider.embed_query("thermal control")


def test_parse_openai_compatible_embeddings_orders_by_index() -> None:
    embeddings = parse_openai_compatible_embeddings(
        {
            "data": [
                {"index": 1, "embedding": [0, 1]},
                {"index": 0, "embedding": [1, 0]},
            ]
        }
    )

    assert embeddings == [[1.0, 0.0], [0.0, 1.0]]


def vector_norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))
