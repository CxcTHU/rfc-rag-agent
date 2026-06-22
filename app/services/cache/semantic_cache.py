from __future__ import annotations

import hashlib
import json
import struct
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.agent import AgentQueryResponse
from app.services.cache.redis_client import get_redis_client
from app.services.observability.latency_trace import get_current_latency_trace
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.query_embedding_cache import (
    get_query_embedding_cache,
    normalize_query_text,
)


SEMANTIC_CACHE_INDEX = "idx:semcache"
SEMANTIC_CACHE_PREFIX = "semcache"


@dataclass(frozen=True)
class SemanticCacheLookup:
    response: AgentQueryResponse | None
    hit: bool
    similarity: float | None = None
    reason: str = "miss"


class RedisSemanticCache:
    """Redis Stack semantic cache for complete agent answers."""

    def __init__(
        self,
        redis_client: Any,
        *,
        similarity_threshold: float = 0.92,
        ttl_seconds: int = 3600,
        index_name: str = SEMANTIC_CACHE_INDEX,
        key_prefix: str = SEMANTIC_CACHE_PREFIX,
    ) -> None:
        if not 0.0 < similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be in (0, 1]")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
        self.redis_client = redis_client
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.index_name = index_name
        self.key_prefix = key_prefix.strip(":") or SEMANTIC_CACHE_PREFIX
        self._index_dimensions: set[int] = set()

    def lookup(
        self,
        *,
        query: str,
        mode: str,
        embedding_provider: EmbeddingProvider,
        cache_context: str = "default",
    ) -> SemanticCacheLookup:
        normalized_query = normalize_query_text(query)
        if not normalized_query:
            return _record_lookup(SemanticCacheLookup(None, False, reason="empty_query"))

        try:
            embedding = get_query_embedding_cache().get_or_embed(
                embedding_provider,
                normalized_query,
            )
            dimension = len(embedding)
            self._ensure_index(dimension)
            raw_result = self.redis_client.execute_command(
                "FT.SEARCH",
                self._index_name_for_dimension(dimension),
                "*=>[KNN 5 @embedding $vector AS distance]",
                "PARAMS",
                "2",
                "vector",
                encode_float32_vector(embedding),
                "SORTBY",
                "distance",
                "RETURN",
                "2",
                "payload",
                "distance",
                "DIALECT",
                "2",
            )
        except Exception as exc:
            return _record_lookup(
                SemanticCacheLookup(None, False, reason=f"redis_skip:{exc.__class__.__name__}")
            )

        candidates = parse_ft_search_payloads(raw_result)
        if not candidates:
            return _record_lookup(SemanticCacheLookup(None, False, reason="miss"))

        last_similarity: float | None = None
        saw_identity_mismatch = False
        for payload, distance in candidates:
            similarity = max(0.0, min(1.0, 1.0 - distance))
            last_similarity = similarity
            if similarity < self.similarity_threshold:
                continue
            try:
                decoded = json.loads(payload)
            except Exception:
                continue
            if decoded.get("mode") != mode:
                saw_identity_mismatch = True
                continue
            if (
                decoded.get("embedding_provider") != embedding_provider.provider_name
                or decoded.get("embedding_model") != embedding_provider.model_name
                or decoded.get("embedding_dimension") != embedding_provider.dimension
                or decoded.get("cache_context") != cache_context
            ):
                saw_identity_mismatch = True
                continue
            response = AgentQueryResponse.model_validate(
                {
                    "question": decoded["query"],
                    "answer": decoded["answer"],
                    "tool_calls": [],
                    "search_results": [],
                    "sources": decoded.get("sources", []),
                    "citations": decoded.get("citations", []),
                    "refused": False,
                    "refusal_reason": None,
                    "reasoning_summary": "semantic_cache_hit: reused cached agent answer",
                    "mode": mode,
                    "workflow_steps": [],
                    "iteration_count": 0,
                    "invalid_citations": [],
                    "refusal_category": None,
                    "latency_trace": {
                        "semantic_cache_hit": True,
                        "semantic_cache_similarity": round(similarity, 6),
                    },
                }
            )
            return _record_lookup(
                SemanticCacheLookup(response, True, similarity=similarity, reason="hit")
            )

        reason = "embedding_identity_mismatch" if saw_identity_mismatch else "below_threshold"
        return _record_lookup(
            SemanticCacheLookup(None, False, similarity=last_similarity, reason=reason)
        )

    def store(
        self,
        *,
        query: str,
        mode: str,
        embedding_provider: EmbeddingProvider,
        response: AgentQueryResponse,
        cache_context: str = "default",
    ) -> bool:
        if response.refused:
            return False
        normalized_query = normalize_query_text(query)
        if not normalized_query:
            return False

        payload = {
            "query": normalized_query,
            "answer": response.answer,
            "sources": [source.model_dump(mode="json") for source in response.sources],
            "citations": list(response.citations),
            "mode": mode,
            "embedding_provider": embedding_provider.provider_name,
            "embedding_model": embedding_provider.model_name,
            "embedding_dimension": embedding_provider.dimension,
            "cache_context": cache_context,
            "created_at": int(time.time()),
        }
        try:
            embedding = get_query_embedding_cache().get_or_embed(
                embedding_provider,
                normalized_query,
            )
            dimension = len(embedding)
            self._ensure_index(dimension)
            redis_key = semantic_cache_key(
                semantic_cache_identity(
                    query=normalized_query,
                    mode=mode,
                    embedding_provider=embedding_provider,
                    cache_context=cache_context,
                ),
                prefix=self._key_prefix_for_dimension(dimension),
            )
            self.redis_client.hset(
                redis_key,
                mapping={
                    "query": normalized_query,
                    "mode": mode,
                    "created_at": payload["created_at"],
                    "embedding": encode_float32_vector(embedding),
                    "payload": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                },
            )
            self.redis_client.expire(redis_key, int(self.ttl_seconds))
        except Exception:
            return False
        return True

    def _ensure_index(self, dimension: int) -> None:
        if dimension in self._index_dimensions:
            return
        index_name = self._index_name_for_dimension(dimension)
        key_prefix = self._key_prefix_for_dimension(dimension)
        try:
            self.redis_client.execute_command("FT.INFO", index_name)
        except Exception:
            self.redis_client.execute_command(
                "FT.CREATE",
                index_name,
                "ON",
                "HASH",
                "PREFIX",
                "1",
                f"{key_prefix}:",
                "SCHEMA",
                "query",
                "TEXT",
                "mode",
                "TAG",
                "created_at",
                "NUMERIC",
                "embedding",
                "VECTOR",
                "FLAT",
                "6",
                "TYPE",
                "FLOAT32",
                "DIM",
                str(dimension),
                "DISTANCE_METRIC",
                "COSINE",
            )
        self._index_dimensions.add(dimension)

    def _index_name_for_dimension(self, dimension: int) -> str:
        return f"{self.index_name}:d{dimension}"

    def _key_prefix_for_dimension(self, dimension: int) -> str:
        return f"{self.key_prefix}:d{dimension}"


def semantic_cache_key(query: str, *, prefix: str = SEMANTIC_CACHE_PREFIX) -> str:
    digest = hashlib.sha256(normalize_query_text(query).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def semantic_cache_identity(
    *,
    query: str,
    mode: str,
    embedding_provider: EmbeddingProvider,
    cache_context: str = "default",
) -> str:
    return "|".join(
        [
            cache_context,
            mode,
            embedding_provider.provider_name,
            embedding_provider.model_name,
            str(embedding_provider.dimension),
            normalize_query_text(query),
        ]
    )


def encode_float32_vector(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *(float(value) for value in values))


def parse_ft_search_payload(raw_result: Any) -> tuple[str | None, float | None]:
    candidates = parse_ft_search_payloads(raw_result)
    if not candidates:
        return None, None
    return candidates[0]


def parse_ft_search_payloads(raw_result: Any) -> list[tuple[str, float]]:
    if not isinstance(raw_result, list) or len(raw_result) < 3:
        return []
    candidates: list[tuple[str, float]] = []
    for fields in raw_result[2::2]:
        if not isinstance(fields, list):
            continue
        decoded: dict[str, Any] = {}
        for key, value in zip(fields[::2], fields[1::2], strict=False):
            if isinstance(key, bytes):
                key = key.decode("utf-8")
            if isinstance(value, bytes) and key != "payload":
                value = value.decode("utf-8")
            decoded[str(key)] = value
        payload = decoded.get("payload")
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        try:
            distance = float(decoded.get("distance"))
        except (TypeError, ValueError):
            continue
        if isinstance(payload, str):
            candidates.append((payload, distance))
    return candidates


def get_configured_semantic_cache(
    *,
    settings: Settings | None = None,
) -> RedisSemanticCache | None:
    active_settings = settings or get_settings()
    if not active_settings.semantic_cache_enabled:
        return None
    redis_client = get_redis_client(active_settings)
    if redis_client is None:
        return None
    return RedisSemanticCache(
        redis_client,
        similarity_threshold=active_settings.semantic_cache_similarity_threshold,
        ttl_seconds=active_settings.semantic_cache_ttl_seconds,
    )


def semantic_cache_request_is_eligible(
    *,
    conversation_id: int | None,
    history: list[str],
    source_id: str | None,
    image_path: str | None,
    query: str = "",
    conversation_messages: list[Any] | None = None,
) -> bool:
    if source_id is not None or image_path is not None:
        return False
    if conversation_id is None:
        return not history
    if last_user_message_matches_query(query, conversation_messages or []):
        return True
    return query_looks_standalone_for_semantic_cache(query)


def last_user_message_matches_query(query: str, conversation_messages: list[Any]) -> bool:
    normalized_query = normalize_query_text(query)
    if not normalized_query:
        return False
    for message in reversed(conversation_messages):
        if getattr(message, "role", None) != "user":
            continue
        return normalize_query_text(str(getattr(message, "content", ""))) == normalized_query
    return False


def query_looks_standalone_for_semantic_cache(query: str) -> bool:
    normalized_query = normalize_query_text(query)
    if not normalized_query:
        return False
    followup_markers = (
        "它",
        "这个",
        "这些",
        "那些",
        "上述",
        "上面",
        "前面",
        "刚才",
        "继续",
        "再说",
        "展开",
        "详细",
        "that",
        "it",
        "them",
        "those",
        "above",
        "previous",
    )
    if any(marker in normalized_query.casefold() for marker in followup_markers):
        return False
    standalone_anchors = (
        "堆石",
        "混凝土",
        "自密实",
        "rfc",
        "rock-filled",
        "rock filled",
        "concrete",
        "self-compacting",
    )
    return any(anchor in normalized_query.casefold() for anchor in standalone_anchors)


def _record_lookup(result: SemanticCacheLookup) -> SemanticCacheLookup:
    trace = get_current_latency_trace()
    if trace is not None:
        trace.set_value("semantic_cache_hit", result.hit)
        trace.set_value("semantic_cache_similarity", result.similarity)
    return result
