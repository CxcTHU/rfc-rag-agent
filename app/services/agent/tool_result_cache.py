"""Shared tool-result cache boundary for Phase 66 extraction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.services.cache.layered_cache import (
    CacheLayer,
    RedisLayeredCache,
    base_cache_identity,
    get_configured_layered_cache,
    hydrate_chunk_rows,
    normalized_query_identity,
)
from app.services.agent.tool_models import AgentToolResult
from app.services.observability.latency_trace import (
    active_agent_cache_scope,
    get_current_latency_trace,
)
from app.services.retrieval.runtime import current_retrieval_plan, retrieval_plan_digest

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.services.retrieval.embedding import EmbeddingProvider


_WHITESPACE_RE = re.compile(r"\s+")
_CACHEABLE_TOOL_NAMES = frozenset(
    {"search_knowledge", "hybrid_search_knowledge", "search_tables", "search_figures"}
)
SAFE_RETRIEVAL_DIAGNOSTIC_FIELDS = (
    "graph_fingerprint",
    "graph_selected_count",
    "graph_selected_chunk_ids",
    "graph_relation_type_preview",
    "retrieval_required_channels",
    "retrieval_required_channel_insertions",
    "retrieval_required_channels_satisfied",
)


def stable_cache_identity_part(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "").strip())


def stable_cache_modifier_suffix(value: object) -> str:
    if not isinstance(value, (list, tuple)):
        return ""
    modifiers = [
        stable_cache_identity_part(str(item))
        for item in value
        if stable_cache_identity_part(str(item))
    ]
    if not modifiers:
        return ""
    return "|modifiers=" + ",".join(sorted(dict.fromkeys(modifiers)))


def tool_graph_fingerprint(tool_name: str, runtime_plan: object | None) -> str:
    if tool_name != "hybrid_search_knowledge" or runtime_plan is None:
        return "disabled"
    if getattr(runtime_plan, "graph_requirement", "disabled") == "disabled":
        return "disabled"
    from app.services.graphrag.retriever import graph_content_fingerprint

    return graph_content_fingerprint(Path(get_settings().graphrag_graph_path))


def current_safe_retrieval_diagnostics() -> dict[str, object]:
    trace = get_current_latency_trace()
    if trace is None:
        return {}
    return {
        key: trace.values[key]
        for key in SAFE_RETRIEVAL_DIAGNOSTIC_FIELDS
        if key in trace.values
    }


def restore_tool_cache_retrieval_diagnostics(payload: dict[str, object]) -> None:
    trace = get_current_latency_trace()
    diagnostics = payload.get("retrieval_diagnostics")
    if trace is None or not isinstance(diagnostics, dict):
        return
    for key in SAFE_RETRIEVAL_DIAGNOSTIC_FIELDS:
        if key in diagnostics:
            trace.set_value(key, diagnostics[key])


class ToolResultCache:
    def __init__(
        self,
        *,
        db: Session | None,
        embedding_provider: EmbeddingProvider | None,
        cache_factory: Callable[[CacheLayer], RedisLayeredCache | None] = get_configured_layered_cache,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self._cache_factory = cache_factory
        self._local_results: dict[str, AgentToolResult] = {}

    def identity(self, tool_name: str, query: str, top_k: int) -> dict[str, object]:
        if self.db is None or self.embedding_provider is None:
            return {
                "schema": "phase66-tool-result-cache-v1",
                "tool_name": stable_cache_identity_part(tool_name),
                "query": stable_cache_identity_part(query),
                "top_k": int(top_k),
            }
        trace = get_current_latency_trace()
        stable_question_key = ""
        if trace is not None and isinstance(trace.values.get("user_question_cache_key"), str):
            stable_question_key = str(trace.values["user_question_cache_key"])
        evidence_query = normalized_query_identity(query)
        if trace is not None and trace.values.get("evidence_cache_reuse_allowed") is True:
            canonical = trace.values.get("evidence_canonical_query")
            entity_key = trace.values.get("evidence_entity_key")
            intent_key = trace.values.get("evidence_intent_key")
            if isinstance(entity_key, str) and isinstance(intent_key, str):
                normalized_entity = stable_cache_identity_part(entity_key)
                normalized_intent = stable_cache_identity_part(intent_key)
                if normalized_entity and normalized_intent:
                    modifier_suffix = stable_cache_modifier_suffix(
                        trace.values.get("evidence_modifiers")
                    )
                    evidence_query = (
                        f"entity={normalized_entity}|intent={normalized_intent}"
                        f"{modifier_suffix}"
                    )
                    stable_question_key = ""
            elif isinstance(canonical, str) and canonical.strip():
                evidence_query = normalized_query_identity(canonical)
                stable_question_key = ""
        settings = get_settings()
        runtime_plan = (
            current_retrieval_plan()
            if settings.retrieval_runtime_enabled
            else None
        )
        identity = base_cache_identity(self.db)
        query_mode = "user_question" if stable_question_key else "evidence_identity"
        identity.update(
            {
                "layer": "tool",
                "agent_cache_scope": active_agent_cache_scope(),
                "tool_name": tool_name,
                "query_mode": query_mode,
                "query": stable_question_key or evidence_query,
                "top_k": "dynamic" if stable_question_key else top_k,
                "dynamic_top_k_quality_gate": (
                    "hybrid-dynamic-top-k-v2"
                    if tool_name == "hybrid_search_knowledge"
                    and getattr(settings, "reranking_dynamic_top_k_enabled", False)
                    else "static"
                ),
                "dynamic_top_k_enabled": bool(
                    tool_name == "hybrid_search_knowledge"
                    and getattr(settings, "reranking_dynamic_top_k_enabled", False)
                ),
                "dynamic_min_results": (
                    settings.reranking_dynamic_min_results
                    if tool_name == "hybrid_search_knowledge"
                    else 0
                ),
                "dynamic_max_results": (
                    settings.reranking_dynamic_max_results
                    if tool_name == "hybrid_search_knowledge"
                    else 0
                ),
                "dynamic_relative_score_threshold": (
                    round(float(settings.reranking_dynamic_relative_score_threshold), 6)
                    if tool_name == "hybrid_search_knowledge"
                    else 0.0
                ),
                "embedding_provider": self.embedding_provider.provider_name,
                "embedding_model": self.embedding_provider.model_name,
                "embedding_dimension": self.embedding_provider.dimension,
                "reranking_provider": settings.reranking_provider,
                "reranking_model": settings.reranking_model_name,
                "reranking_recall_k": settings.reranking_recall_k,
                "graph_path": settings.graphrag_graph_path if tool_name == "search_graph_knowledge" else "",
                "table_rag_enabled": bool(settings.table_rag_enabled)
                if tool_name == "search_tables"
                else False,
                "retrieval_plan_digest": retrieval_plan_digest(runtime_plan),
                "retrieval_runtime_schema": (
                    runtime_plan.schema if runtime_plan is not None else "legacy"
                ),
                "graph_fingerprint": tool_graph_fingerprint(tool_name, runtime_plan),
            }
        )
        return identity

    def simple_identity(self, tool_name: str, query: str, top_k: int) -> dict[str, object]:
        return {
            "schema": "phase66-tool-result-cache-v1",
            "tool_name": stable_cache_identity_part(tool_name),
            "query": stable_cache_identity_part(query),
            "top_k": int(top_k),
        }

    def lookup(self, tool_name: str, query: str, top_k: int) -> AgentToolResult | None:
        if self.db is None:
            return self._local_results.get(self._identity_key(tool_name, query, top_k))
        trace = get_current_latency_trace()
        if tool_name not in _CACHEABLE_TOOL_NAMES:
            return None
        if tool_name == "search_tables" and get_settings().table_rag_enabled:
            return None
        cache = self._cache_factory("tool")
        if cache is None:
            if trace is not None:
                trace.set_value("tool_result_cache_hit", False)
                trace.set_value("tool_result_cache_backend", "disabled")
                trace.set_value("tool_result_cache_reason", "disabled")
            return None
        lookup = cache.lookup(self.identity(tool_name, query, top_k))
        if not lookup.hit or lookup.payload is None:
            if trace is not None:
                trace.set_value("tool_result_cache_hit", False)
                trace.set_value("tool_result_cache_backend", lookup.backend)
                trace.set_value("tool_result_cache_reason", lookup.reason)
            return None
        payload = lookup.payload.get("payload", {})
        chunk_ids = payload.get("chunk_ids")
        if not isinstance(chunk_ids, list) or not all(isinstance(chunk_id, int) for chunk_id in chunk_ids):
            return None
        if len(chunk_ids) < top_k:
            stored_top_k = payload.get("stored_top_k")
            try:
                stored_top_k_value = int(stored_top_k)
            except (TypeError, ValueError):
                stored_top_k_value = 0
            if stored_top_k_value < top_k:
                return None
        preserve_dynamic_count = (
            tool_name == "hybrid_search_knowledge"
            and bool(getattr(get_settings(), "reranking_dynamic_top_k_enabled", False))
        )
        if not preserve_dynamic_count:
            chunk_ids = chunk_ids[:top_k]
        scores = payload.get("scores")
        score_by_chunk_id: dict[int, float] = {}
        if isinstance(scores, dict):
            for raw_chunk_id, raw_score in scores.items():
                try:
                    score_by_chunk_id[int(raw_chunk_id)] = float(raw_score)
                except (TypeError, ValueError):
                    continue
        hydrated = hydrate_chunk_rows(self.db, chunk_ids)
        if len(hydrated) != len(chunk_ids):
            return None
        from app.services.agent.tools import (
            _enrich_results_with_citation_location,
            _enrich_sources_with_citation_location,
            _trace_tool_cache_selected_results,
            figure_result_from_search_item,
            search_item_from_chunk,
            sources_from_search_results,
            summarize_input,
        )
        from app.services.agent.tool_models import AgentToolCallRecord

        search_results = _enrich_results_with_citation_location(
            [
                search_item_from_chunk(
                    chunk=chunk,
                    document=document,
                    score=score_by_chunk_id.get(chunk.id, 0.0),
                )
                for chunk, document in hydrated
            ],
            self.db,
        )
        sources = _enrich_sources_with_citation_location(
            sources_from_search_results(search_results),
            self.db,
        )
        figure_results = [
            figure_result_from_search_item(item)
            for item in search_results
            if item.chunk_type == "image_description" and item.image_url and item.source_image_path
        ]
        refused = bool(payload.get("refused")) and not search_results
        refusal_reason = payload.get("refusal_reason") if isinstance(payload.get("refusal_reason"), str) else None
        restore_tool_cache_retrieval_diagnostics(payload)
        _trace_tool_cache_selected_results(tool_name, search_results)
        if trace is not None:
            trace.set_value("tool_result_cache_hit", True)
            trace.set_value("tool_result_cache_backend", lookup.backend)
            trace.set_value("tool_result_cache_reason", lookup.reason)
        return AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=summarize_input(query, top_k),
                output_summary=f"cache hit; returned {len(search_results)} {tool_name} results",
                succeeded=True,
            ),
            search_results=search_results,
            figure_results=figure_results,
            sources=sources,
            refused=refused,
            refusal_reason=refusal_reason if refused else None,
        )

    def store(
        self,
        tool_name: str,
        query: str,
        top_k: int,
        result: AgentToolResult,
    ) -> None:
        if self.db is None:
            self._local_results[self._identity_key(tool_name, query, top_k)] = result
            return
        if tool_name not in _CACHEABLE_TOOL_NAMES:
            return
        if tool_name == "search_tables" and get_settings().table_rag_enabled:
            return
        cache = self._cache_factory("tool")
        if cache is None:
            return
        chunk_ids = [item.chunk_id for item in result.search_results]
        cache.store(
            self.identity(tool_name, query, top_k),
            {
                "chunk_ids": chunk_ids,
                "stored_top_k": top_k,
                "stored_result_count": len(chunk_ids),
                "dynamic_top_k_enabled": bool(
                    tool_name == "hybrid_search_knowledge"
                    and getattr(get_settings(), "reranking_dynamic_top_k_enabled", False)
                ),
                "scores": {
                    str(item.chunk_id): round(float(item.score), 8)
                    for item in result.search_results
                },
                "refused": result.refused,
                "refusal_reason": result.refusal_reason,
                "retrieval_diagnostics": current_safe_retrieval_diagnostics(),
            },
        )

    def _identity_key(self, tool_name: str, query: str, top_k: int) -> str:
        payload = self.identity(tool_name, query, top_k)
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
