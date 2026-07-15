from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.evaluate_phase63_e2e import (
    OUTPUT_FIELDS,
    case_history,
    collect_streamed_answer,
    evaluate_events,
    parse_sse_text,
    select_cases,
    set_stream_read_timeout,
)


def test_phase63_e2e_output_keeps_safe_connection_reuse_diagnostics() -> None:
    assert "provider_http_request_count" in OUTPUT_FIELDS
    assert "provider_http_reused_connection_count" in OUTPUT_FIELDS
    assert "provider_http_last_connection_reused" in OUTPUT_FIELDS


def test_phase63_e2e_output_keeps_safe_selected_model_diagnostics() -> None:
    assert "requested_chat_model" in OUTPUT_FIELDS
    assert "observed_chat_model" in OUTPUT_FIELDS


def test_phase63_e2e_requires_metadata_done_and_no_error() -> None:
    success_events = parse_sse_text(
        "event: token\ndata: {\"text\":\"ok\"}\n\n"
        "event: tool_call_result\ndata: {\"tool_name\":\"hybrid_search_knowledge\","
        "\"succeeded\":true,\"skipped\":false}\n\n"
        "event: metadata\ndata: {\"refused\":false,\"citations\":[1],"
        "\"tool_calls\":[{\"tool_name\":\"hybrid_search_knowledge\",\"succeeded\":true}],"
        "\"latency_trace\":{\"retrieval_graph_requirement\":\"disabled\"}}\n\n"
        "event: done\ndata: {}\n\n"
    )
    failed_events = parse_sse_text(
        "event: tool_call_result\ndata: {\"tool_name\":\"hybrid_search_knowledge\"}\n\n"
        "event: error\ndata: {\"detail\":\"agent stream failed\"}\n\n"
    )

    success = evaluate_events(success_events, expected_tool="hybrid_search_knowledge", expected_graph_requirement="disabled", minimum_citations=1, enforce_runtime_contract=False)
    failure = evaluate_events(failed_events, expected_tool="hybrid_search_knowledge", expected_graph_requirement="disabled", minimum_citations=1, enforce_runtime_contract=False)

    assert success["ok"] is True
    assert failure["ok"] is False
    assert failure["error_category"] == "stream_error"


def test_phase63_e2e_requires_expected_tool_to_succeed() -> None:
    events = parse_sse_text(
        "event: tool_call_result\ndata: {\"tool_name\":\"search_figures\",\"succeeded\":false,\"skipped\":true}\n\n"
        "event: tool_call_result\ndata: {\"tool_name\":\"hybrid_search_knowledge\",\"succeeded\":true,\"skipped\":false}\n\n"
        "event: metadata\ndata: {\"refused\":false,\"citations\":[1],\"tool_calls\":[{\"tool_name\":\"search_figures\",\"succeeded\":false}],\"latency_trace\":{\"retrieval_graph_requirement\":\"disabled\"}}\n\n"
        "event: done\ndata: {}\n\n"
    )
    result = evaluate_events(events, expected_tool="search_figures", expected_graph_requirement="disabled", minimum_citations=1, enforce_runtime_contract=False)
    assert result["ok"] is False
    assert result["error_category"] == "expected_tool_failed"


def test_phase63_e2e_accepts_expected_gate_from_workflow_steps() -> None:
    events = parse_sse_text(
        "event: metadata\n"
        "data: {\"refused\":true,\"workflow_steps\":[{\"name\":\"off_topic_gate\",\"succeeded\":true}],"
        "\"latency_trace\":{\"retrieval_graph_requirement\":\"disabled\"}}\n\n"
        "event: done\ndata: {}\n\n"
    )

    result = evaluate_events(
        events,
        expected_tool="off_topic_gate",
        expected_graph_requirement="disabled",
        minimum_citations=0,
    )

    assert result["ok"] is True
    assert result["observed_tool_names"] == "off_topic_gate"


def test_phase63_e2e_parses_case_history_for_followup_requests() -> None:
    assert case_history({"history": "[\"user: first\", \"assistant: second\"]"}) == [
        "user: first",
        "assistant: second",
    ]
    assert case_history({"history_json": "[\"user: first\"]"}) == ["user: first"]
    assert case_history({"history": "[]"}) == []
    assert case_history({"history": "not-json"}) == []


def test_phase63_e2e_accepts_preferred_or_required_for_active_graph_gate() -> None:
    events = parse_sse_text(
        "event: tool_call_result\ndata: {\"tool_name\":\"hybrid_search_knowledge\",\"succeeded\":true}\n\n"
        "event: metadata\ndata: {\"citations\":[1],\"latency_trace\":{\"retrieval_graph_requirement\":\"preferred\"}}\n\n"
        "event: done\ndata: {}\n\n"
    )
    result = evaluate_events(events, expected_tool="hybrid_search_knowledge", expected_graph_requirement="active", minimum_citations=1, enforce_runtime_contract=False)
    assert result["ok"] is True


def test_phase63_e2e_requires_bm25_pgvector_true_streaming_and_count_equality() -> None:
    healthy = parse_sse_text('event: token\ndata: {"text":"ok"}\n\n' 'event: tool_call_result\ndata: {"tool_name":"hybrid_search_knowledge","succeeded":true,"selected_count":11}\n\n' 'event: metadata\ndata: {"citations":[1],"latency_trace":{"lexical_search_backend":"bm25","vector_search_backend":"pgvector_hnsw","vector_search_degraded":false,"streaming_degraded":false,"streamed_token_count":2,"time_to_first_token_ms":100,"time_to_final_ms":500,"retrieval_selected_count":11}}\n\n' 'event: done\ndata: {}\n\n')
    fallback = parse_sse_text('event: token\ndata: {"text":"ok"}\n\n' 'event: tool_call_result\ndata: {"tool_name":"hybrid_search_knowledge","succeeded":true,"selected_count":11}\n\n' 'event: metadata\ndata: {"citations":[1],"latency_trace":{"lexical_search_backend":"bm25","vector_search_backend":"faiss_fail_open","vector_search_degraded":true,"streaming_degraded":false,"streamed_token_count":2,"time_to_first_token_ms":100,"time_to_final_ms":500,"retrieval_selected_count":11}}\n\n' 'event: done\ndata: {}\n\n')
    inconsistent = parse_sse_text('event: token\ndata: {"text":"ok"}\n\n' 'event: tool_call_result\ndata: {"tool_name":"hybrid_search_knowledge","succeeded":true,"selected_count":6}\n\n' 'event: metadata\ndata: {"citations":[1],"latency_trace":{"lexical_search_backend":"bm25","vector_search_backend":"pgvector_hnsw","vector_search_degraded":false,"streaming_degraded":false,"streamed_token_count":2,"time_to_first_token_ms":100,"time_to_final_ms":500,"retrieval_selected_count":11}}\n\n' 'event: done\ndata: {}\n\n')
    healthy_result = evaluate_events(healthy, expected_tool="hybrid_search_knowledge", expected_graph_requirement="any", minimum_citations=1)
    fallback_result = evaluate_events(fallback, expected_tool="hybrid_search_knowledge", expected_graph_requirement="any", minimum_citations=1)
    fault_result = evaluate_events(fallback, expected_tool="hybrid_search_knowledge", expected_graph_requirement="any", minimum_citations=1, allow_vector_fallback=True)
    inconsistent_result = evaluate_events(inconsistent, expected_tool="hybrid_search_knowledge", expected_graph_requirement="any", minimum_citations=1)
    assert healthy_result["ok"] is True
    assert fallback_result["error_category"] == "vector_backend_degraded"
    assert fault_result["ok"] is True
    assert inconsistent_result["error_category"] == "retrieval_count_mismatch"


def test_phase63_e2e_accepts_specialized_route_without_hybrid_lexical_lane() -> None:
    events = parse_sse_text('event: token\ndata: {"text":"ok"}\n\n' 'event: tool_call_result\ndata: {"tool_name":"search_figures","succeeded":true,"selected_count":4}\n\n' 'event: metadata\ndata: {"citations":[1],"latency_trace":{"retrieval_graph_requirement":"disabled","lexical_search_backend":"not_run","vector_search_backend":"pgvector_hnsw","vector_search_degraded":false,"streaming_degraded":false,"streamed_token_count":2,"time_to_first_token_ms":100,"time_to_final_ms":500,"retrieval_selected_count":4}}\n\n' 'event: done\ndata: {}\n\n')
    result = evaluate_events(events, expected_tool="search_figures", expected_graph_requirement="disabled", minimum_citations=1)
    assert result["ok"] is True
    assert result["counts_match"] is True


def test_phase63_e2e_accepts_specialized_route_with_hybrid_supplemental_trace() -> None:
    events = parse_sse_text(
        'event: token\ndata: {"text":"ok"}\n\n'
        'event: tool_call_result\ndata: {"tool_name":"search_figures","succeeded":true,"selected_count":11}\n\n'
        'event: tool_call_result\ndata: {"tool_name":"hybrid_search_knowledge","succeeded":true,"selected_count":12}\n\n'
        'event: metadata\ndata: {"citations":[1],"latency_trace":{"retrieval_graph_requirement":"disabled","lexical_search_backend":"bm25","vector_search_backend":"pgvector_hnsw","vector_search_degraded":false,"streaming_degraded":false,"streamed_token_count":2,"time_to_first_token_ms":100,"time_to_final_ms":500,"retrieval_selected_count":12}}\n\n'
        'event: done\ndata: {}\n\n'
    )

    result = evaluate_events(events, expected_tool="search_figures", expected_graph_requirement="disabled", minimum_citations=1)

    assert result["ok"] is True
    assert result["selected_count"] == 11
    assert result["live_selected_count"] == 11


def test_phase63_e2e_specialized_route_zero_results_reports_citation_failure_not_trace_mismatch() -> None:
    events = parse_sse_text(
        'event: token\ndata: {"text":"ok"}\n\n'
        'event: tool_call_result\ndata: {"tool_name":"search_figures","succeeded":true,"selected_count":0}\n\n'
        'event: tool_call_result\ndata: {"tool_name":"hybrid_search_knowledge","succeeded":true,"selected_count":12}\n\n'
        'event: metadata\ndata: {"citations":[],"latency_trace":{"retrieval_graph_requirement":"disabled","lexical_search_backend":"bm25","vector_search_backend":"pgvector_hnsw","vector_search_degraded":false,"streaming_degraded":false,"streamed_token_count":2,"time_to_first_token_ms":100,"time_to_final_ms":500,"retrieval_selected_count":12}}\n\n'
        'event: done\ndata: {}\n\n'
    )

    result = evaluate_events(events, expected_tool="search_figures", expected_graph_requirement="disabled", minimum_citations=1)

    assert result["error_category"] == "insufficient_citations"
    assert result["selected_count"] == 0
    assert result["live_selected_count"] == 0


def test_phase63_e2e_output_schema_excludes_response_content() -> None:
    forbidden = {"answer", "content", "raw_response", "reasoning", "source_content", "evidence_content"}
    assert forbidden.isdisjoint(OUTPUT_FIELDS)


def test_collect_streamed_answer_stays_out_of_the_persisted_schema() -> None:
    events = parse_sse_text('event: token\ndata: {"text":"first "}\n\n' 'event: metadata\ndata: {}\n\n' 'event: token\ndata: {"text":"second"}\n\n')
    assert collect_streamed_answer(events) == "first second"
    assert "answer" not in OUTPUT_FIELDS


def test_phase63_e2e_case_set_covers_real_routes_and_regression() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "evaluation" / "phase63_e2e_cases.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    categories = {row["category"] for row in rows}
    assert {"regression_text", "relationship", "figure", "table", "negative_visual", "negative_table", "negative_relationship"} <= categories
    assert any(row["query"] == "堆石混凝土的优势？" for row in rows)


def test_phase63_e2e_can_select_one_case_for_targeted_retest() -> None:
    rows = [{"case_id": "text", "category": "text"}, {"case_id": "figure", "category": "figure"}]
    assert select_cases(rows, case_id="figure", limit=0) == [rows[1]]


class _FakeSocket:
    def __init__(self) -> None:
        self.timeout: float | None = None

    def settimeout(self, value: float) -> None:
        self.timeout = value


class _FakeResponse:
    def __init__(self) -> None:
        self.fp = type("Fp", (), {"raw": type("Raw", (), {"_sock": _FakeSocket()})()})()


def test_stream_read_timeout_uses_remaining_total_deadline() -> None:
    response = _FakeResponse()
    remaining = set_stream_read_timeout(response, deadline_monotonic=110.0, now=100.0)
    assert remaining == pytest.approx(10.0)
    assert response.fp.raw._sock.timeout == pytest.approx(10.0)


def test_stream_read_timeout_rejects_an_expired_total_deadline() -> None:
    with pytest.raises(TimeoutError, match="agent_stream_total_deadline_exhausted"):
        set_stream_read_timeout(_FakeResponse(), deadline_monotonic=100.0, now=100.0)
