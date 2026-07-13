from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "data" / "evaluation" / "phase63_e2e_cases.csv"
OUTPUT_FIELDS = (
    "case_id",
    "category",
    "ok",
    "error_category",
    "requested_chat_model",
    "observed_chat_model",
    "http_status",
    "event_names",
    "observed_tool_names",
    "expected_tool",
    "observed_graph_requirement",
    "expected_graph_requirement",
    "citation_count",
    "selected_count",
    "live_selected_count",
    "lexical_backend",
    "vector_backend",
    "vector_degraded",
    "streaming_degraded",
    "streamed_token_count",
    "counts_match",
    "query_embedding_latency_ms",
    "bm25_search_latency_ms",
    "vector_search_latency_ms",
    "graph_search_latency_ms",
    "rerank_latency_ms",
    "tool_latency_ms",
    "answer_latency_ms",
    "provider_http_latency_ms",
    "provider_http_request_count",
    "provider_http_reused_connection_count",
    "provider_http_last_connection_reused",
    "refused",
    "first_token_ms",
    "elapsed_ms",
    "conversation_persisted",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run safe real-provider Phase 63 SSE end-to-end evaluation."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--case-id", default="")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--token", default="")
    parser.add_argument("--keep-conversations", action="store_true")
    return parser.parse_args()


def select_cases(
    rows: list[dict[str, str]],
    *,
    case_id: str,
    limit: int,
) -> list[dict[str, str]]:
    selected = (
        [row for row in rows if row.get("case_id") == case_id]
        if case_id
        else list(rows)
    )
    return selected[:limit] if limit > 0 else selected


def parse_sse_text(text: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    normalized = text.replace("\r\n", "\n")
    for block in normalized.split("\n\n"):
        parsed = parse_sse_block(block.splitlines())
        if parsed is not None:
            events.append(parsed)
    return events


def collect_streamed_answer(events: list[tuple[str, dict[str, Any]]]) -> str:
    return "".join(
        str(payload.get("text", ""))
        for event_name, payload in events
        if event_name == "token" and isinstance(payload.get("text"), str)
    )


def parse_sse_block(lines: list[str]) -> tuple[str, dict[str, Any]] | None:
    event_name = "message"
    data_lines: list[str] = []
    for line in lines:
        if line.startswith("event:"):
            event_name = line[6:].strip() or "message"
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not data_lines:
        return None
    try:
        payload = json.loads("\n".join(data_lines))
    except json.JSONDecodeError:
        payload = {}
    return event_name, payload if isinstance(payload, dict) else {}


def evaluate_events(
    events: list[tuple[str, dict[str, Any]]],
    *,
    expected_tool: str,
    expected_graph_requirement: str,
    minimum_citations: int,
    enforce_runtime_contract: bool = True,
    allow_vector_fallback: bool = False,
) -> dict[str, object]:
    event_names = [name for name, _payload in events]
    metadata = next(
        (payload for name, payload in events if name == "metadata"),
        {},
    )
    tool_names: list[str] = []
    succeeded_tool_names: list[str] = []
    for name, payload in events:
        if name in {"tool_call_start", "tool_call_result"}:
            value = payload.get("tool_name") or payload.get("name")
            if isinstance(value, str) and value:
                tool_names.append(value)
                if name == "tool_call_result" and payload.get("succeeded") is True:
                    succeeded_tool_names.append(value)
    metadata_calls = metadata.get("tool_calls")
    if isinstance(metadata_calls, list):
        for item in metadata_calls:
            if not isinstance(item, dict):
                continue
            value = item.get("tool_name") or item.get("name")
            if isinstance(value, str) and value:
                tool_names.append(value)
                if item.get("succeeded") is True:
                    succeeded_tool_names.append(value)
    tool_names = list(dict.fromkeys(tool_names))
    succeeded_tool_names = list(dict.fromkeys(succeeded_tool_names))
    trace = metadata.get("latency_trace")
    trace = trace if isinstance(trace, dict) else {}
    citations = metadata.get("citations")
    citation_count = len(citations) if isinstance(citations, list) else 0
    observed_graph = str(trace.get("retrieval_graph_requirement", ""))
    selected_ids = trace.get("retrieval_selected_chunk_ids")
    selected_count = (
        len(selected_ids)
        if isinstance(selected_ids, list)
        else int(trace.get("retrieval_selected_count", 0) or 0)
    )
    live_selected_values = [
        int(payload.get("selected_count", 0) or 0)
        for name, payload in events
        if name == "tool_call_result"
        and payload.get("tool_name") == expected_tool
        and payload.get("succeeded") is True
    ]
    live_selected_count = live_selected_values[-1] if live_selected_values else 0
    lexical_backend = str(trace.get("lexical_search_backend", ""))
    vector_backend = str(trace.get("vector_search_backend", ""))
    vector_degraded = bool(trace.get("vector_search_degraded", False))
    streaming_degraded = bool(trace.get("streaming_degraded", False))
    streamed_token_count = int(trace.get("streamed_token_count", 0) or 0)
    first_token = trace.get("time_to_first_token_ms")
    final_time = trace.get("time_to_final_ms")
    true_streaming = (
        "token" in event_names
        and streamed_token_count > 0
        and not streaming_degraded
        and isinstance(first_token, (int, float))
        and isinstance(final_time, (int, float))
        and float(first_token) < float(final_time)
    )
    counts_match = live_selected_count == selected_count and live_selected_count > 0
    has_error = "error" in event_names
    has_metadata = "metadata" in event_names
    has_done = "done" in event_names
    tool_ok = expected_tool in succeeded_tool_names
    graph_ok = (
        expected_graph_requirement in {"", "any"}
        or (
            expected_graph_requirement == "active"
            and observed_graph in {"preferred", "required"}
        )
        or observed_graph == expected_graph_requirement
    )
    citations_ok = citation_count >= minimum_citations
    error_category = ""
    if has_error:
        error_category = "stream_error"
    elif not has_metadata:
        error_category = "missing_metadata"
    elif not has_done:
        error_category = "missing_done"
    elif not tool_ok:
        error_category = (
            "expected_tool_failed"
            if expected_tool in tool_names
            else "unexpected_tool_route"
        )
    elif not graph_ok:
        error_category = "unexpected_graph_route"
    elif (
        enforce_runtime_contract
        and expected_tool == "hybrid_search_knowledge"
        and lexical_backend != "bm25"
    ):
        error_category = "unexpected_lexical_backend"
    elif enforce_runtime_contract and not (
        vector_backend == "pgvector_hnsw" and not vector_degraded
    ) and not (
        allow_vector_fallback
        and vector_backend == "faiss_fail_open"
        and vector_degraded
    ):
        error_category = "vector_backend_degraded"
    elif enforce_runtime_contract and not true_streaming:
        error_category = "streaming_degraded"
    elif enforce_runtime_contract and not counts_match:
        error_category = "retrieval_count_mismatch"
    elif not citations_ok:
        error_category = "insufficient_citations"
    return {
        "ok": not error_category,
        "error_category": error_category,
        "observed_chat_model": str(metadata.get("chat_model", "")),
        "event_names": "|".join(event_names),
        "observed_tool_names": "|".join(tool_names),
        "observed_graph_requirement": observed_graph,
        "citation_count": citation_count,
        "selected_count": selected_count,
        "live_selected_count": live_selected_count,
        "lexical_backend": lexical_backend,
        "vector_backend": vector_backend,
        "vector_degraded": vector_degraded,
        "streaming_degraded": streaming_degraded,
        "streamed_token_count": streamed_token_count,
        "counts_match": counts_match,
        "query_embedding_latency_ms": trace.get("query_embedding_latency_ms", 0.0),
        "bm25_search_latency_ms": trace.get("bm25_search_latency_ms", 0.0),
        "vector_search_latency_ms": trace.get("vector_search_latency_ms", 0.0),
        "graph_search_latency_ms": trace.get("graph_search_latency_ms", 0.0),
        "rerank_latency_ms": trace.get("rerank_latency_ms", 0.0),
        "retrieval_total_latency_ms": trace.get("retrieval_total_latency_ms", 0.0),
        "glm_rerank_latency_ms": trace.get("glm_rerank_latency_ms", 0.0),
        "phase64_execution_graph": str(trace.get("phase64_execution_graph", "")),
        "phase64_route_kind": str(trace.get("phase64_route_kind", "")),
        "phase64_route_reason": str(trace.get("phase64_route_reason", "")),
        "tool_latency_ms": trace.get("tool_latency_ms", 0.0),
        "answer_latency_ms": trace.get("answer_latency_ms", 0.0),
        "provider_http_latency_ms": trace.get("provider_http_latency_ms", 0.0),
        "provider_http_request_count": trace.get("provider_http_request_count", 0),
        "provider_http_reused_connection_count": trace.get(
            "provider_http_reused_connection_count", 0
        ),
        "provider_http_last_connection_reused": bool(
            trace.get("provider_http_last_connection_reused", False)
        ),
        "planner_call_count": trace.get("planner_call_count", 0),
        "final_generation_call_count": trace.get("final_generation_call_count", 0),
        "final_model_ttft_ms": trace.get("final_model_ttft_ms", 0.0),
        "citation_repair_count": trace.get("citation_repair_count", 0),
        "citation_repair_latency_ms": trace.get("citation_repair_latency_ms", 0.0),
        "refused": bool(metadata.get("refused", False)),
    }


def request_headers(token: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def post_json(
    url: str,
    payload: dict[str, object],
    *,
    token: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    call = request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=request_headers(token),
        method="POST",
    )
    with request.urlopen(call, timeout=timeout_seconds) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    return decoded if isinstance(decoded, dict) else {}


def execute_case(
    case: dict[str, str],
    *,
    base_url: str,
    token: str,
    timeout_seconds: float,
    keep_conversation: bool,
    capture_answer: bool = False,
    chat_model: str | None = None,
) -> dict[str, object]:
    started = time.perf_counter()
    conversation_id: int | None = None
    http_status = 0
    first_token_ms = 0.0
    events: list[tuple[str, dict[str, Any]]] = []
    transport_error = ""
    try:
        conversation = post_json(
            f"{base_url.rstrip('/')}/conversations",
            {"title": f"phase63-e2e-{case['case_id']}"},
            token=token,
            timeout_seconds=timeout_seconds,
        )
        conversation_id = int(conversation["id"])
        payload: dict[str, object] = {
            "question": case["query"],
            "conversation_id": conversation_id,
        }
        if chat_model:
            payload["chat_model"] = chat_model
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        call = request.Request(
            f"{base_url.rstrip('/')}/agent/query/stream",
            data=body,
            headers=request_headers(token),
            method="POST",
        )
        with request.urlopen(call, timeout=timeout_seconds) as response:
            http_status = int(response.status)
            block: list[str] = []
            for raw_line in response:
                line = raw_line.decode("utf-8").rstrip("\r\n")
                if line:
                    block.append(line)
                    continue
                parsed = parse_sse_block(block)
                block = []
                if parsed is None:
                    continue
                events.append(parsed)
                if parsed[0] == "token" and first_token_ms == 0.0:
                    first_token_ms = (time.perf_counter() - started) * 1000.0
            parsed = parse_sse_block(block)
            if parsed is not None:
                events.append(parsed)
    except error.HTTPError as exc:
        http_status = int(exc.code)
        transport_error = f"http_{exc.code}"
    except error.URLError:
        transport_error = "connection_error"
    except (TimeoutError, ValueError, KeyError, json.JSONDecodeError):
        transport_error = "invalid_or_timeout_response"

    minimum_citations = int(case.get("minimum_citations", "0") or 0)
    evaluated = evaluate_events(
        events,
        expected_tool=case["expected_tool"],
        expected_graph_requirement=case["expected_graph_requirement"],
        minimum_citations=minimum_citations,
    )
    if transport_error:
        evaluated["ok"] = False
        evaluated["error_category"] = transport_error

    conversation_persisted = False
    if conversation_id is not None:
        try:
            messages_call = request.Request(
                f"{base_url.rstrip('/')}/conversations/{conversation_id}/messages",
                headers=request_headers(token),
                method="GET",
            )
            with request.urlopen(messages_call, timeout=timeout_seconds) as response:
                messages_payload = json.loads(response.read().decode("utf-8"))
            messages = messages_payload.get("messages", [])
            conversation_persisted = isinstance(messages, list) and len(messages) >= 2
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):
            conversation_persisted = False
        if not keep_conversation:
            try:
                delete_call = request.Request(
                    f"{base_url.rstrip('/')}/conversations/{conversation_id}",
                    headers=request_headers(token),
                    method="DELETE",
                )
                with request.urlopen(delete_call, timeout=timeout_seconds):
                    pass
            except (error.HTTPError, error.URLError, TimeoutError):
                pass
    if not conversation_persisted and bool(evaluated["ok"]):
        evaluated["ok"] = False
        evaluated["error_category"] = "conversation_not_persisted"
    observed_chat_model = str(evaluated.get("observed_chat_model", ""))
    if chat_model and observed_chat_model != chat_model:
        evaluated["ok"] = False
        evaluated["error_category"] = "selected_chat_model_mismatch"

    result = {
        "case_id": case["case_id"],
        "category": case["category"],
        **evaluated,
        "requested_chat_model": chat_model or "",
        "http_status": http_status,
        "expected_tool": case["expected_tool"],
        "expected_graph_requirement": case["expected_graph_requirement"],
        "first_token_ms": round(first_token_ms, 3),
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "conversation_persisted": conversation_persisted,
    }
    if capture_answer:
        result["_ephemeral_answer"] = collect_streamed_answer(events)
    return result


def main() -> int:
    args = parse_args()
    with args.cases.open(encoding="utf-8-sig", newline="") as stream:
        cases = list(csv.DictReader(stream))
    cases = select_cases(cases, case_id=args.case_id, limit=args.limit)
    rows = [
        execute_case(
            case,
            base_url=args.base_url,
            token=args.token,
            timeout_seconds=args.timeout_seconds,
            keep_conversation=args.keep_conversations,
        )
        for case in cases
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(
            {field: row.get(field, "") for field in OUTPUT_FIELDS} for row in rows
        )
    passed = sum(1 for row in rows if row["ok"])
    print(
        json.dumps(
            {
                "case_count": len(rows),
                "passed": passed,
                "failed": len(rows) - passed,
                "all_passed": passed == len(rows),
                "output": str(args.out),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
