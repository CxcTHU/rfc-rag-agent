from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.config import Settings, get_settings
from app.services.cache.redis_client import RedisClientFactory
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.query_embedding_cache import (
    QueryEmbeddingCache,
    QueryEmbeddingCacheKey,
    QueryEmbeddingCacheStats,
    normalize_query_text,
    record_query_embedding_cache_event,
)


class RedisQueryEmbeddingCache:
    """Redis-backed query embedding cache with an in-process fallback."""

    def __init__(
        self,
        redis_client: Any,
        *,
        fallback_cache: QueryEmbeddingCache | None = None,
        ttl_seconds: float = 900.0,
        key_prefix: str = "emb",
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
        self.redis_client = redis_client
        self.fallback_cache = fallback_cache or QueryEmbeddingCache(ttl_seconds=ttl_seconds)
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix.strip(":") or "emb"
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._redis_errors = 0

    @property
    def redis_errors(self) -> int:
        return self._redis_errors

    def get_or_embed(self, provider: EmbeddingProvider, query: str) -> list[float]:
        normalized_query = normalize_query_text(query)
        key = QueryEmbeddingCacheKey(
            provider=provider.provider_name,
            model_name=provider.model_name,
            dimension=provider.dimension,
            normalized_query=normalized_query,
        )
        redis_key = redis_embedding_cache_key(key, prefix=self.key_prefix)

        try:
            cached = self.redis_client.get(redis_key)
        except Exception:
            self._redis_errors += 1
            return self.fallback_cache.get_or_embed(provider, normalized_query)

        if cached is not None:
            try:
                embedding = decode_embedding(cached)
                if len(embedding) != provider.dimension:
                    raise ValueError("cached embedding dimension mismatch")
            except (TypeError, ValueError, json.JSONDecodeError):
                self._redis_errors += 1
            else:
                self._hits += 1
                record_query_embedding_cache_event(hit=True, backend="redis")
                return embedding

        self._misses += 1
        embedding = self.fallback_cache.get_or_embed(provider, normalized_query)
        try:
            self.redis_client.setex(
                redis_key,
                int(self.ttl_seconds),
                json.dumps(embedding, separators=(",", ":")),
            )
        except Exception:
            self._redis_errors += 1
        return embedding

    def clear(self) -> None:
        self.fallback_cache.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._redis_errors = 0

    def stats(self) -> QueryEmbeddingCacheStats:
        return QueryEmbeddingCacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
        )

    def keys(self) -> list[QueryEmbeddingCacheKey]:
        return self.fallback_cache.keys()


def redis_embedding_cache_key(
    key: QueryEmbeddingCacheKey,
    *,
    prefix: str = "emb",
) -> str:
    query_hash = hashlib.sha256(key.normalized_query.encode("utf-8")).hexdigest()
    return f"{prefix}:{key.provider}:{key.model_name}:{key.dimension}:{query_hash}"


def decode_embedding(raw_value: bytes | str) -> list[float]:
    if isinstance(raw_value, bytes):
        raw_text = raw_value.decode("utf-8")
    else:
        raw_text = raw_value
    raw_embedding = json.loads(raw_text)
    if not isinstance(raw_embedding, list):
        raise TypeError("cached embedding is not a list")
    embedding: list[float] = []
    for value in raw_embedding:
        if not isinstance(value, (int, float)):
            raise TypeError("cached embedding contains a non-numeric value")
        embedding.append(float(value))
    return embedding


_GLOBAL_CONFIGURED_CACHE: QueryEmbeddingCache | RedisQueryEmbeddingCache | None = None
_GLOBAL_CONFIGURED_SIGNATURE: tuple[str, float] | None = None


def get_configured_query_embedding_cache(
    fallback_cache: QueryEmbeddingCache,
    *,
    settings: Settings | None = None,
) -> QueryEmbeddingCache | RedisQueryEmbeddingCache:
    global _GLOBAL_CONFIGURED_CACHE, _GLOBAL_CONFIGURED_SIGNATURE

    active_settings = settings or get_settings()
    signature = (
        active_settings.redis_url.strip(),
        active_settings.redis_socket_timeout_seconds,
    )
    if not signature[0]:
        return fallback_cache

    if _GLOBAL_CONFIGURED_CACHE is not None and _GLOBAL_CONFIGURED_SIGNATURE == signature:
        return _GLOBAL_CONFIGURED_CACHE

    redis_client = RedisClientFactory(
        active_settings.redis_url,
        socket_timeout_seconds=active_settings.redis_socket_timeout_seconds,
    ).create_client()
    if redis_client is None:
        _GLOBAL_CONFIGURED_CACHE = fallback_cache
        _GLOBAL_CONFIGURED_SIGNATURE = signature
        return fallback_cache

    _GLOBAL_CONFIGURED_CACHE = RedisQueryEmbeddingCache(
        redis_client,
        fallback_cache=fallback_cache,
    )
    _GLOBAL_CONFIGURED_SIGNATURE = signature
    return _GLOBAL_CONFIGURED_CACHE


def reset_configured_query_embedding_cache() -> None:
    global _GLOBAL_CONFIGURED_CACHE, _GLOBAL_CONFIGURED_SIGNATURE
    _GLOBAL_CONFIGURED_CACHE = None
    _GLOBAL_CONFIGURED_SIGNATURE = None
