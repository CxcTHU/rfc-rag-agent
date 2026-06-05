import math

import pytest

from app.services.retrieval.embedding import (
    DeterministicEmbeddingProvider,
    create_embedding_provider,
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


def vector_norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))
