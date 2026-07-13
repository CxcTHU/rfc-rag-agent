from __future__ import annotations

import hashlib
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Iterator


LATENCY_FIELDS = (
    "query_embedding_latency_ms",
    "vector_search_latency_ms",
    "faiss_search_latency_ms",
    "numpy_search_latency_ms",
    "rerank_latency_ms",
    "rerank_fallback_latency_ms",
    "planner_latency_ms",
    "hyde_latency_ms",
    "answer_latency_ms",
    "citation_repair_latency_ms",
    "tool_latency_ms",
    "graph_search_latency_ms",
    "keyword_search_latency_ms",
    "bm25_search_latency_ms",
    "table_channel_latency_ms",
    "figure_channel_latency_ms",
    "provider_http_latency_ms",
    "reranking_primary_health_latency_ms",
    "retrieval_cache_lookup_latency_ms",
    "retrieval_cache_hydrate_latency_ms",
    "rerank_cache_lookup_latency_ms",
    "request_preflight_latency_ms",
    "context_assembly_latency_ms",
    "retrieval_total_latency_ms",
    "glm_rerank_latency_ms",
    "final_generation_latency_ms",
    "citation_validation_latency_ms",
)


@dataclass
class LatencyTrace:
    started_at: float = field(default_factory=time.perf_counter)
    values: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in LATENCY_FIELDS:
            self.values.setdefault(field_name, 0.0)
        self.values.setdefault("time_to_first_progress_ms", None)
        self.values.setdefault("time_to_first_answer_token_ms", None)
        self.values.setdefault("time_to_first_token_ms", None)
        self.values.setdefault("planner_ttft_ms", None)
        self.values.setdefault("final_model_ttft_ms", None)
        self.values.setdefault("time_to_final_ms", 0.0)
        self.values.setdefault("streaming_degraded", False)
        self.values.setdefault("streamed_token_count", 0)
        self.values.setdefault("iteration_count", 0)
        self.values.setdefault("tool_call_count", 0)
        self.values.setdefault("query_embedding_cache_hits", 0)
        self.values.setdefault("query_embedding_cache_misses", 0)
        self.values.setdefault("query_embedding_cache_backend", "memory")
        self.values.setdefault("provider_http_request_count", 0)
        self.values.setdefault("provider_http_attempt_count", 0)
        self.values.setdefault("provider_http_reused_connection_count", 0)
        self.values.setdefault("provider_http_retry_backoff_ms", 0.0)
        self.values.setdefault("provider_http_last_status", None)
        self.values.setdefault("provider_http_last_connection_reused", False)
        self.values.setdefault("provider_http_last_pool_key_hash", "")
        self.values.setdefault("provider_http_last_provider", "")
        self.values.setdefault("provider_http_last_model", "")
        self.values.setdefault("provider_prompt_tokens", 0)
        self.values.setdefault("provider_prompt_cache_hit_tokens", 0)
        self.values.setdefault("provider_prompt_cache_miss_tokens", 0)
        self.values.setdefault("reranking_primary_health_status", "not_checked")
        self.values.setdefault("reranking_primary_health_error", "")
        self.values.setdefault("reranking_primary_health_cache_hit", False)
        self.values.setdefault("retrieval_cache_hit", False)
        self.values.setdefault("retrieval_cache_backend", "disabled")
        self.values.setdefault("retrieval_cache_reason", "not_checked")
        self.values.setdefault("retrieval_cache_saved_ms", 0.0)
        self.values.setdefault("rerank_cache_hit", False)
        self.values.setdefault("rerank_cache_backend", "disabled")
        self.values.setdefault("rerank_cache_reason", "not_checked")
        self.values.setdefault("rerank_cache_saved_ms", 0.0)
        self.values.setdefault("tool_result_cache_hit", False)
        self.values.setdefault("tool_result_cache_backend", "disabled")
        self.values.setdefault("tool_result_cache_reason", "not_checked")
        self.values.setdefault("tool_result_cache_saved_ms", 0.0)
        self.values.setdefault("semantic_cache_hit", False)
        self.values.setdefault("semantic_cache_reason", "not_checked")
        self.values.setdefault("agent_cache_scope", "")
        self.values.setdefault("canonical_task", "")
        self.values.setdefault("hyde_generated", False)
        self.values.setdefault("hyde_used_for_vector", False)
        self.values.setdefault("hyde_reason", "not_checked")
        self.values.setdefault("hyde_model", "")
        self.values.setdefault("vector_search_backend", "not_run")
        self.values.setdefault("lexical_search_backend", "not_run")
        self.values.setdefault("vector_search_degraded", False)
        self.values.setdefault("vector_search_fallback_reason", "")
        self.values.setdefault("vector_backend_policy", "prefer_pgvector")
        self.values.setdefault("reranking_degraded", False)
        self.values.setdefault("reranking_degradation_level", "")
        self.values.setdefault("reranking_error_type", "")
        self.values.setdefault("planner_model", "deterministic")
        self.values.setdefault("planner_call_count", 0)
        self.values.setdefault("final_generation_call_count", 0)
        self.values.setdefault("total_model_call_count", 0)
        self.values.setdefault("retrieval_strategy", "none")
        self.values.setdefault("graph_search_available", False)
        self.values.setdefault("graph_search_fallback", False)
        self.values.setdefault("graph_search_error", "")
        self.values.setdefault("graph_entity_count", 0)
        self.values.setdefault("graph_candidate_chunk_count", 0)
        self.values.setdefault("graph_hop_count", 0)
        self.values.setdefault("retrieval_enabled_channels", [])
        self.values.setdefault("retrieval_eligible_channels", [])
        self.values.setdefault("retrieval_channel_candidate_counts", {})
        self.values.setdefault("retrieval_selected_channels", [])
        self.values.setdefault("retrieval_runtime_mode", "legacy")
        self.values.setdefault("retrieval_plan_schema", "legacy")
        self.values.setdefault("retrieval_plan_digest", "legacy")
        self.values.setdefault("retrieval_plan_fallback", False)
        self.values.setdefault("retrieval_plan_fallback_reason", "")
        self.values.setdefault("retrieval_intent_source", "deterministic")
        self.values.setdefault("retrieval_graph_requirement", "disabled")
        self.values.setdefault("retrieval_graph_budget_profile", "disabled")
        self.values.setdefault("retrieval_graph_max_hops", 0)
        self.values.setdefault("retrieval_graph_max_matches", 0)
        self.values.setdefault("retrieval_table_text_requirement", "disabled")
        self.values.setdefault("retrieval_figure_caption_requirement", "disabled")
        self.values.setdefault("retrieval_required_channels", [])
        self.values.setdefault("retrieval_required_channel_insertions", [])
        self.values.setdefault("retrieval_required_channels_satisfied", True)
        self.values.setdefault("graph_fingerprint", "disabled")
        self.values.setdefault("graph_selected_count", 0)
        self.values.setdefault("graph_selected_chunk_ids", [])
        self.values.setdefault("graph_relation_type_preview", [])
        self.values.setdefault("runtime_context_assembled", False)
        self.values.setdefault("runtime_followup_type", "standalone")
        self.values.setdefault("runtime_recent_topic", "")
        self.values.setdefault("runtime_inherited_topic", "")
        self.values.setdefault("runtime_standalone_task", "")
        self.values.setdefault("runtime_contextualized", False)
        self.values.setdefault("runtime_contextualization_source", "none")
        self.values.setdefault("runtime_tool_arg_rewrite_count", 0)
        self.values.setdefault("runtime_tool_arg_rewrites", [])
        self.values.setdefault("runtime_evidence_attempts", [])
        self.values.setdefault("runtime_evidence_counts", {})
        self.values.setdefault("runtime_stop_reason", "not_stopped")
        self.values.setdefault("runtime_final_decision", "pending")

    def add_duration(self, field_name: str, duration_ms: float) -> None:
        current = self.values.get(field_name, 0.0)
        if not isinstance(current, (int, float)):
            current = 0.0
        self.values[field_name] = round(float(current) + duration_ms, 3)

    def set_value(self, field_name: str, value: object) -> None:
        self.values[field_name] = value

    @contextmanager
    def span(self, field_name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            self.add_duration(field_name, (time.perf_counter() - started) * 1000.0)

    def mark_progress(self) -> None:
        if self.values.get("time_to_first_progress_ms") is not None:
            return
        self.values["time_to_first_progress_ms"] = round(
            (time.perf_counter() - self.started_at) * 1000.0,
            3,
        )

    def mark_answer_token(self, started_at: float | None = None) -> None:
        if self.values.get("time_to_first_answer_token_ms") is not None:
            return
        start = self.started_at if started_at is None else started_at
        value = round((time.perf_counter() - start) * 1000.0, 3)
        self.values["time_to_first_answer_token_ms"] = value
        self.values["time_to_first_token_ms"] = value

    def mark_first_token(self, started_at: float | None = None) -> None:
        """Compatibility alias for callers that still use the old name."""
        self.mark_answer_token(started_at=started_at)

    def finalize(self, *, iteration_count: int, tool_call_count: int) -> dict[str, object]:
        self.values["iteration_count"] = iteration_count
        self.values["tool_call_count"] = tool_call_count
        self.values["time_to_final_ms"] = round((time.perf_counter() - self.started_at) * 1000.0, 3)
        return dict(self.values)


def stable_text_cache_key(text: str) -> str:
    normalized = " ".join((text or "").strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def bind_user_question_cache_key(trace: LatencyTrace, question: str) -> None:
    trace.set_value("user_question_cache_key", stable_text_cache_key(question))


def bind_agent_conversation_cache_scope(trace: LatencyTrace, conversation_id: int | None) -> None:
    """Scope short-lived retrieval/evidence caches to one chat session.

    A missing conversation id means the request is not tied to a durable session;
    use a per-request scope so it cannot reuse another request/session's evidence.
    """
    scope = f"conversation:{conversation_id}" if conversation_id is not None else f"request:{uuid.uuid4().hex}"
    trace.set_value("agent_cache_scope", scope)


def active_agent_cache_scope() -> str:
    trace = get_current_latency_trace()
    if trace is None:
        return ""
    value = trace.values.get("agent_cache_scope", "")
    return value if isinstance(value, str) else ""


_CURRENT_LATENCY_TRACE: ContextVar[LatencyTrace | None] = ContextVar(
    "current_latency_trace",
    default=None,
)


def get_current_latency_trace() -> LatencyTrace | None:
    return _CURRENT_LATENCY_TRACE.get()


def set_current_latency_trace(trace: LatencyTrace | None) -> Token[LatencyTrace | None]:
    return _CURRENT_LATENCY_TRACE.set(trace)


def reset_current_latency_trace(token: Token[LatencyTrace | None]) -> None:
    _CURRENT_LATENCY_TRACE.reset(token)


@contextmanager
def latency_timer(field_name: str) -> Iterator[None]:
    trace = get_current_latency_trace()
    started = time.perf_counter()
    try:
        yield
    finally:
        if trace is not None:
            trace.add_duration(field_name, (time.perf_counter() - started) * 1000.0)
