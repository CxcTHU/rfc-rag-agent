from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from threading import RLock

from app.services.observability.latency_trace import get_current_latency_trace
from app.services.retrieval.embedding import EmbeddingProvider


@dataclass(frozen=True)
class QueryEmbeddingCacheKey:
    provider: str
    model_name: str
    dimension: int
    normalized_query: str


@dataclass(frozen=True)
class QueryEmbeddingCacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0


@dataclass
class _CacheEntry:
    embedding: tuple[float, ...]
    expires_at: float


class QueryEmbeddingCache:
    """Small TTL + LRU cache for query embeddings only."""

    def __init__(self, max_size: int = 256, ttl_seconds: float = 900.0) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be greater than 0")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._lock = RLock()
        self._entries: OrderedDict[QueryEmbeddingCacheKey, _CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get_or_embed(self, provider: EmbeddingProvider, query: str) -> list[float]:
        normalized_query = cache_identity_query_text(query)
        key = QueryEmbeddingCacheKey(
            provider=provider.provider_name,
            model_name=provider.model_name,
            dimension=provider.dimension,
            normalized_query=normalized_query,
        )
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > now:
                self._hits += 1
                self._entries.move_to_end(key)
                record_query_embedding_cache_event(hit=True, backend="memory")
                return list(entry.embedding)
            if entry is not None:
                self._entries.pop(key, None)

        embedding = provider.embed_query(normalized_query)
        if len(embedding) != provider.dimension:
            raise ValueError("embedding provider returned a vector with unexpected dimension")

        with self._lock:
            self._misses += 1
            record_query_embedding_cache_event(hit=False, backend="memory")
            self._entries[key] = _CacheEntry(
                embedding=tuple(float(value) for value in embedding),
                expires_at=now + self.ttl_seconds,
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_size:
                self._entries.popitem(last=False)
                self._evictions += 1
        return list(embedding)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def stats(self) -> QueryEmbeddingCacheStats:
        with self._lock:
            return QueryEmbeddingCacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
            )

    def keys(self) -> list[QueryEmbeddingCacheKey]:
        with self._lock:
            return list(self._entries.keys())


def normalize_query_text(query: str) -> str:
    return " ".join((query or "").strip().split())


def cache_identity_query_text(query: str) -> str:
    trace = get_current_latency_trace()
    if trace is not None and trace.values.get("evidence_cache_reuse_allowed") is True:
        entity_key = trace.values.get("evidence_entity_key")
        intent_key = trace.values.get("evidence_intent_key")
        if isinstance(entity_key, str) and isinstance(intent_key, str):
            entity = normalize_query_text(entity_key)
            intent = normalize_query_text(intent_key)
            if entity and intent:
                return f"entity={entity}|intent={intent}"
        canonical = trace.values.get("evidence_canonical_query")
        if isinstance(canonical, str) and canonical.strip():
            return normalize_query_text(canonical)
    return normalize_query_text(query)


def record_query_embedding_cache_event(*, hit: bool, backend: str) -> None:
    trace = get_current_latency_trace()
    if trace is None:
        return
    field_name = "query_embedding_cache_hits" if hit else "query_embedding_cache_misses"
    current = trace.values.get(field_name, 0)
    if not isinstance(current, int):
        current = 0
    trace.set_value(field_name, current + 1)
    trace.set_value("query_embedding_cache_backend", backend)


_GLOBAL_QUERY_EMBEDDING_CACHE = QueryEmbeddingCache()


def get_query_embedding_cache() -> QueryEmbeddingCache:
    from app.services.cache.embedding_cache import get_configured_query_embedding_cache

    return get_configured_query_embedding_cache(_GLOBAL_QUERY_EMBEDDING_CACHE)


def clear_query_embedding_cache() -> None:
    from app.services.cache.embedding_cache import reset_configured_query_embedding_cache

    reset_configured_query_embedding_cache()
    _GLOBAL_QUERY_EMBEDDING_CACHE.clear()
