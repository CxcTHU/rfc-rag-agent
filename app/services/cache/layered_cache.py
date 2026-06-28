from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Chunk, ChunkEmbedding, Document
from app.services.cache.redis_client import get_redis_client
from app.services.observability.latency_trace import get_current_latency_trace
from app.services.retrieval.query_embedding_cache import normalize_query_text


CacheLayer = Literal["retrieval", "rerank", "tool"]


@dataclass(frozen=True)
class LayeredCacheLookup:
    payload: dict[str, Any] | None
    hit: bool
    reason: str
    backend: str = "redis"


class RedisLayeredCache:
    """Small Redis JSON cache for Phase 56 retrieval/rerank/tool layers."""

    def __init__(
        self,
        redis_client: Any,
        *,
        namespace: str,
        ttl_seconds: int,
        layer: CacheLayer,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
        self.redis_client = redis_client
        self.namespace = namespace.strip(":") or "phase56-v1"
        self.ttl_seconds = ttl_seconds
        self.layer = layer

    def lookup(self, identity: dict[str, Any]) -> LayeredCacheLookup:
        key = layered_cache_key(identity, namespace=self.namespace, layer=self.layer)
        started = time.perf_counter()
        try:
            raw_value = self.redis_client.get(key)
        except Exception:
            _record_layer_event(self.layer, hit=False, backend="redis", reason="redis_error")
            return LayeredCacheLookup(None, False, "redis_error")
        if raw_value is None:
            _record_layer_event(self.layer, hit=False, backend="redis", reason="miss")
            return LayeredCacheLookup(None, False, "miss")
        try:
            if isinstance(raw_value, bytes):
                raw_value = raw_value.decode("utf-8")
            payload = json.loads(raw_value)
        except Exception:
            _record_layer_event(self.layer, hit=False, backend="redis", reason="decode_error")
            return LayeredCacheLookup(None, False, "decode_error")
        _record_layer_event(
            self.layer,
            hit=True,
            backend="redis",
            reason="hit",
            saved_ms=(time.perf_counter() - started) * 1000.0,
        )
        return LayeredCacheLookup(payload, True, "hit")

    def store(self, identity: dict[str, Any], payload: dict[str, Any]) -> bool:
        key = layered_cache_key(identity, namespace=self.namespace, layer=self.layer)
        safe_payload = {
            "schema": identity.get("schema", "phase56-v1"),
            "layer": self.layer,
            "created_at": int(time.time()),
            "payload": payload,
        }
        try:
            self.redis_client.setex(
                key,
                int(self.ttl_seconds),
                json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":")),
            )
        except Exception:
            return False
        return True


def get_configured_layered_cache(
    layer: CacheLayer,
    *,
    settings: Settings | None = None,
) -> RedisLayeredCache | None:
    active_settings = settings or get_settings()
    enabled = {
        "retrieval": active_settings.retrieval_candidate_cache_enabled,
        "rerank": active_settings.rerank_order_cache_enabled,
        "tool": active_settings.tool_result_cache_enabled,
    }[layer]
    if not enabled:
        _record_layer_event(layer, hit=False, backend="disabled", reason="disabled")
        return None
    redis_client = get_redis_client(active_settings)
    if redis_client is None:
        _record_layer_event(layer, hit=False, backend="none", reason="redis_unavailable")
        return None
    ttl_seconds = {
        "retrieval": active_settings.retrieval_candidate_cache_ttl_seconds,
        "rerank": active_settings.rerank_order_cache_ttl_seconds,
        "tool": active_settings.tool_result_cache_ttl_seconds,
    }[layer]
    return RedisLayeredCache(
        redis_client,
        namespace=active_settings.layered_cache_namespace,
        ttl_seconds=ttl_seconds,
        layer=layer,
    )


def layered_cache_key(
    identity: dict[str, Any],
    *,
    namespace: str,
    layer: CacheLayer,
) -> str:
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{namespace.strip(':')}:{layer}:{digest}"


def base_cache_identity(
    db: Session,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    active_settings = settings or get_settings()
    return {
        "schema": "phase56-v1",
        "namespace": active_settings.layered_cache_namespace,
        "app_version": active_settings.app_version,
        "corpus": corpus_fingerprint(db),
    }


def corpus_fingerprint(db: Session) -> str:
    """Return a compact DB waterline fingerprint without reading chunk bodies."""
    document_count, document_max = db.execute(
        select(func.count(Document.id), func.coalesce(func.max(Document.id), 0))
    ).one()
    chunk_count, chunk_max = db.execute(
        select(func.count(Chunk.id), func.coalesce(func.max(Chunk.id), 0))
    ).one()
    embedding_count, embedding_max = db.execute(
        select(func.count(ChunkEmbedding.id), func.coalesce(func.max(ChunkEmbedding.id), 0))
    ).one()
    raw = "|".join(
        [
            f"documents={document_count}:{document_max}",
            f"chunks={chunk_count}:{chunk_max}",
            f"embeddings={embedding_count}:{embedding_max}",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def normalized_query_identity(query: str) -> str:
    return normalize_query_text(query)


def candidate_chunk_hash(chunk_ids: list[int]) -> str:
    raw = ",".join(str(chunk_id) for chunk_id in chunk_ids)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hydrate_chunk_rows(db: Session, chunk_ids: list[int]) -> list[tuple[Chunk, Document]]:
    if not chunk_ids:
        return []
    rows = db.execute(
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(chunk_ids))
    ).all()
    by_id = {chunk.id: (chunk, document) for chunk, document in rows}
    return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]


def _record_layer_event(
    layer: CacheLayer,
    *,
    hit: bool,
    backend: str,
    reason: str,
    saved_ms: float = 0.0,
) -> None:
    trace = get_current_latency_trace()
    if trace is None:
        return
    prefix = {
        "retrieval": "retrieval_cache",
        "rerank": "rerank_cache",
        "tool": "tool_result_cache",
    }[layer]
    if hit:
        trace.set_value(f"{prefix}_hit", True)
    elif trace.values.get(f"{prefix}_hit") is not True:
        trace.set_value(f"{prefix}_hit", False)
    trace.set_value(f"{prefix}_backend", backend)
    trace.set_value(f"{prefix}_reason", reason)
    if saved_ms:
        trace.set_value(f"{prefix}_saved_ms", round(saved_ms, 3))
