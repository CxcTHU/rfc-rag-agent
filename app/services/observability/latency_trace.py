from __future__ import annotations

import hashlib
import time
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
    "planner_latency_ms",
    "answer_latency_ms",
    "tool_latency_ms",
    "graph_search_latency_ms",
)


@dataclass
class LatencyTrace:
    started_at: float = field(default_factory=time.perf_counter)
    values: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in LATENCY_FIELDS:
            self.values.setdefault(field_name, 0.0)
        self.values.setdefault("time_to_first_token_ms", None)
        self.values.setdefault("time_to_final_ms", 0.0)
        self.values.setdefault("iteration_count", 0)
        self.values.setdefault("tool_call_count", 0)
        self.values.setdefault("query_embedding_cache_hits", 0)
        self.values.setdefault("query_embedding_cache_misses", 0)
        self.values.setdefault("query_embedding_cache_backend", "memory")
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
        self.values.setdefault("vector_search_backend", "not_run")
        self.values.setdefault("planner_model", "deterministic")
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

    def add_duration(self, field_name: str, duration_ms: float) -> None:
        current = self.values.get(field_name, 0.0)
        if not isinstance(current, (int, float)):
            current = 0.0
        self.values[field_name] = round(float(current) + duration_ms, 3)

    def set_value(self, field_name: str, value: object) -> None:
        self.values[field_name] = value

    def mark_first_token(self, started_at: float | None = None) -> None:
        if self.values.get("time_to_first_token_ms") is not None:
            return
        start = self.started_at if started_at is None else started_at
        self.values["time_to_first_token_ms"] = round((time.perf_counter() - start) * 1000.0, 3)

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
