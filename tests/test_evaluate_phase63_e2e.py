from __future__ import annotations

import csv
from pathlib import Path

from scripts.evaluate_phase63_e2e import (
    OUTPUT_FIELDS,
    evaluate_events,
    parse_sse_text,
    select_cases,
)


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

    success = evaluate_events(
        success_events,
        expected_tool="hybrid_search_knowledge",
        expected_graph_requirement="disabled",
        minimum_citations=1,
        enforce_runtime_contract=False,
    )
    failure = evaluate_events(
        failed_events,
        expected_tool="hybrid_search_knowledge",
        expected_graph_requirement="disabled",
        minimum_citations=1,
        enforce_runtime_contract=False,
    )

    assert success["ok"] is True
    assert failure["ok"] is False
    assert failure["error_category"] == "stream_error"


def test_phase63_e2e_requires_expected_tool_to_succeed() -> None:
    events = parse_sse_text(
        "event: tool_call_result\ndata: {\"tool_name\":\"search_figures\","
        "\"succeeded\":false,\"skipped\":true}\n\n"
        "event: tool_call_result\ndata: {\"tool_name\":\"hybrid_search_knowledge\","
        "\"succeeded\":true,\"skipped\":false}\n\n"
        "event: metadata\ndata: {\"refused\":false,\"citations\":[1],"
        "\"tool_calls\":[{\"tool_name\":\"search_figures\",\"succeeded\":false}],"
        "\"latency_trace\":{\"retrieval_graph_requirement\":\"disabled\"}}\n\n"
        "event: done\ndata: {}\n\n"
    )

    result = evaluate_events(
        events,
        expected_tool="search_figures",
        expected_graph_requirement="disabled",
        minimum_citations=1,
        enforce_runtime_contract=False,
    )

    assert result["ok"] is False
    assert result["error_category"] == "expected_tool_failed"


def test_phase63_e2e_accepts_preferred_or_required_for_active_graph_gate() -> None:
    events = parse_sse_text(
        "event: tool_call_result\ndata: {\"tool_name\":\"hybrid_search_knowledge\","
        "\"succeeded\":true}\n\n"
        "event: metadata\ndata: {\"citations\":[1],"
        "\"latency_trace\":{\"retrieval_graph_requirement\":\"preferred\"}}\n\n"
        "event: done\ndata: {}\n\n"
    )

    result = evaluate_events(
        events,
        expected_tool="hybrid_search_knowledge",
        expected_graph_requirement="active",
        minimum_citations=1,
        enforce_runtime_contract=False,
    )

    assert result["ok"] is True


def test_phase63_e2e_requires_bm25_pgvector_true_streaming_and_count_equality() -> None:
    healthy = parse_sse_text(
        'event: token\ndata: {"text":"ok"}\n\n'
        'event: tool_call_result\ndata: {"tool_name":"hybrid_search_knowledge",'
        '"succeeded":true,"selected_count":11}\n\n'
        'event: metadata\ndata: {"citations":[1],'
        '"latency_trace":{"lexical_search_backend":"bm25",'
        '"vector_search_backend":"pgvector_hnsw","vector_search_degraded":false,'
        '"streaming_degraded":false,"streamed_token_count":2,'
        '"time_to_first_token_ms":100,"time_to_final_ms":500,'
        '"retrieval_selected_count":11}}\n\n'
        'event: done\ndata: {}\n\n'
    )
    fallback = parse_sse_text(
        'event: token\ndata: {"text":"ok"}\n\n'
        'event: tool_call_result\ndata: {"tool_name":"hybrid_search_knowledge",'
        '"succeeded":true,"selected_count":11}\n\n'
        'event: metadata\ndata: {"citations":[1],'
        '"latency_trace":{"lexical_search_backend":"bm25",'
        '"vector_search_backend":"faiss_fail_open","vector_search_degraded":true,'
        '"streaming_degraded":false,"streamed_token_count":2,'
        '"time_to_first_token_ms":100,"time_to_final_ms":500,'
        '"retrieval_selected_count":11}}\n\n'
        'event: done\ndata: {}\n\n'
    )
    inconsistent = parse_sse_text(
        'event: token\ndata: {"text":"ok"}\n\n'
        'event: tool_call_result\ndata: {"tool_name":"hybrid_search_knowledge",'
        '"succeeded":true,"selected_count":6}\n\n'
        'event: metadata\ndata: {"citations":[1],'
        '"latency_trace":{"lexical_search_backend":"bm25",'
        '"vector_search_backend":"pgvector_hnsw","vector_search_degraded":false,'
        '"streaming_degraded":false,"streamed_token_count":2,'
        '"time_to_first_token_ms":100,"time_to_final_ms":500,'
        '"retrieval_selected_count":11}}\n\n'
        'event: done\ndata: {}\n\n'
    )

    healthy_result = evaluate_events(
        healthy,
        expected_tool="hybrid_search_knowledge",
        expected_graph_requirement="any",
        minimum_citations=1,
    )
    fallback_result = evaluate_events(
        fallback,
        expected_tool="hybrid_search_knowledge",
        expected_graph_requirement="any",
        minimum_citations=1,
    )
    fault_result = evaluate_events(
        fallback,
        expected_tool="hybrid_search_knowledge",
        expected_graph_requirement="any",
        minimum_citations=1,
        allow_vector_fallback=True,
    )
    inconsistent_result = evaluate_events(
        inconsistent,
        expected_tool="hybrid_search_knowledge",
        expected_graph_requirement="any",
        minimum_citations=1,
    )

    assert healthy_result["ok"] is True
    assert fallback_result["error_category"] == "vector_backend_degraded"
    assert fault_result["ok"] is True
    assert inconsistent_result["error_category"] == "retrieval_count_mismatch"


def test_phase63_e2e_accepts_specialized_route_without_hybrid_lexical_lane() -> None:
    events = parse_sse_text(
        'event: token\ndata: {"text":"ok"}\n\n'
        'event: tool_call_result\ndata: {"tool_name":"search_figures",'
        '"succeeded":true,"selected_count":4}\n\n'
        'event: metadata\ndata: {"citations":[1],'
        '"latency_trace":{"retrieval_graph_requirement":"disabled",'
        '"lexical_search_backend":"not_run",'
        '"vector_search_backend":"pgvector_hnsw","vector_search_degraded":false,'
        '"streaming_degraded":false,"streamed_token_count":2,'
        '"time_to_first_token_ms":100,"time_to_final_ms":500,'
        '"retrieval_selected_count":4}}\n\n'
        'event: done\ndata: {}\n\n'
    )

    result = evaluate_events(
        events,
        expected_tool="search_figures",
        expected_graph_requirement="disabled",
        minimum_citations=1,
    )

    assert result["ok"] is True
    assert result["counts_match"] is True


def test_phase63_e2e_output_schema_excludes_response_content() -> None:
    forbidden = {
        "answer",
        "content",
        "raw_response",
        "reasoning",
        "source_content",
        "evidence_content",
    }

    assert forbidden.isdisjoint(OUTPUT_FIELDS)


def test_phase63_e2e_case_set_covers_real_routes_and_regression() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "evaluation"
        / "phase63_e2e_cases.csv"
    )
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    categories = {row["category"] for row in rows}
    assert {
        "regression_text",
        "relationship",
        "figure",
        "table",
        "negative_visual",
        "negative_table",
        "negative_relationship",
    } <= categories
    assert any(row["query"] == "堆石混凝土的优势？" for row in rows)


def test_phase63_e2e_can_select_one_case_for_targeted_retest() -> None:
    rows = [
        {"case_id": "text", "category": "text"},
        {"case_id": "figure", "category": "figure"},
    ]

    assert select_cases(rows, case_id="figure", limit=0) == [rows[1]]
