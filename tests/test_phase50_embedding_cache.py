from __future__ import annotations

import json
from collections.abc import Sequence

from app.services.cache.embedding_cache import (
    RedisQueryEmbeddingCache,
    decode_embedding,
    redis_embedding_cache_key,
)
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.query_embedding_cache import (
    QueryEmbeddingCache,
    QueryEmbeddingCacheKey,
)


class CountingEmbeddingProvider:
    def __init__(
        self,
        *,
        dimension: int = 8,
        provider_name: str = "counting",
        model_name: str = "counting-model",
    ) -> None:
        self.dimension = dimension
        self.provider_name = provider_name
        self.model_name = model_name
        self.delegate = DeterministicEmbeddingProvider(
            dimension=dimension,
            provider_name=provider_name,
            model_name=model_name,
        )
        self.query_calls = 0

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return self.delegate.embed_texts(texts)

    def embed_query(self, query: str) -> list[float]:
        self.query_calls += 1
        return self.delegate.embed_query(query)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.get_calls = 0
        self.setex_calls = 0
        self.fail_get = False
        self.fail_setex = False

    def get(self, key: str):
        self.get_calls += 1
        if self.fail_get:
            raise TimeoutError("redis get unavailable")
        return self.values.get(key)

    def setex(self, key: str, ttl_seconds: int, value: str) -> bool:
        self.setex_calls += 1
        if self.fail_setex:
            raise TimeoutError("redis set unavailable")
        assert ttl_seconds == 900
        self.values[key] = value
        return True


def test_redis_embedding_cache_key_hashes_normalized_query() -> None:
    first = QueryEmbeddingCacheKey(
        provider="p",
        model_name="m",
        dimension=8,
        normalized_query="same query",
    )
    second = QueryEmbeddingCacheKey(
        provider="p",
        model_name="m",
        dimension=8,
        normalized_query="same   query",
    )

    assert redis_embedding_cache_key(first).startswith("emb:p:m:8:")
    assert redis_embedding_cache_key(first) != redis_embedding_cache_key(second)


def test_decode_embedding_accepts_bytes_and_rejects_non_numeric_values() -> None:
    assert decode_embedding(b"[1,2.5]") == [1.0, 2.5]

    try:
        decode_embedding(json.dumps([1, "bad"]))
    except TypeError as exc:
        assert "non-numeric" in str(exc)
    else:
        raise AssertionError("decode_embedding should reject non-numeric values")


def test_redis_query_embedding_cache_writes_miss_and_reuses_hit() -> None:
    redis_client = FakeRedis()
    provider = CountingEmbeddingProvider()
    cache = RedisQueryEmbeddingCache(redis_client, fallback_cache=QueryEmbeddingCache())

    first = cache.get_or_embed(provider, "  filling   capacity ")
    second = cache.get_or_embed(provider, "filling capacity")

    assert first == second
    assert provider.query_calls == 1
    assert redis_client.get_calls == 2
    assert redis_client.setex_calls == 1
    assert cache.stats().hits == 1
    assert cache.stats().misses == 1


def test_query_embedding_cache_records_safe_latency_trace_metrics() -> None:
    redis_client = FakeRedis()
    provider = CountingEmbeddingProvider()
    cache = RedisQueryEmbeddingCache(redis_client, fallback_cache=QueryEmbeddingCache())
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        cache.get_or_embed(provider, "cache metrics")
        cache.get_or_embed(provider, "cache metrics")
    finally:
        reset_current_latency_trace(token)

    assert trace.values["query_embedding_cache_hits"] == 1
    assert trace.values["query_embedding_cache_misses"] == 1
    assert trace.values["query_embedding_cache_backend"] == "redis"


def test_redis_query_embedding_cache_falls_back_when_get_fails() -> None:
    redis_client = FakeRedis()
    redis_client.fail_get = True
    provider = CountingEmbeddingProvider()
    cache = RedisQueryEmbeddingCache(redis_client, fallback_cache=QueryEmbeddingCache())

    first = cache.get_or_embed(provider, "thermal control")
    second = cache.get_or_embed(provider, "thermal   control")

    assert first == second
    assert provider.query_calls == 1
    assert cache.redis_errors == 2


def test_redis_query_embedding_cache_falls_back_when_set_fails() -> None:
    redis_client = FakeRedis()
    redis_client.fail_setex = True
    provider = CountingEmbeddingProvider()
    cache = RedisQueryEmbeddingCache(redis_client, fallback_cache=QueryEmbeddingCache())

    first = cache.get_or_embed(provider, "table retrieval")
    second = cache.get_or_embed(provider, "table retrieval")

    assert first == second
    assert provider.query_calls == 1
    assert redis_client.setex_calls == 2
    assert cache.redis_errors == 2


def test_redis_query_embedding_cache_ignores_corrupt_cached_value() -> None:
    redis_client = FakeRedis()
    provider = CountingEmbeddingProvider()
    key = QueryEmbeddingCacheKey(
        provider=provider.provider_name,
        model_name=provider.model_name,
        dimension=provider.dimension,
        normalized_query="bad cache",
    )
    redis_client.values[redis_embedding_cache_key(key)] = json.dumps(["bad"])
    cache = RedisQueryEmbeddingCache(redis_client, fallback_cache=QueryEmbeddingCache())

    embedding = cache.get_or_embed(provider, "bad cache")

    assert len(embedding) == provider.dimension
    assert provider.query_calls == 1
    assert cache.redis_errors == 1
