from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "data" / "evaluation" / "phase58i_continuous_runtime_cases.yaml"
DEFAULT_OUT = ROOT / "data" / "evaluation" / "phase58i_continuous_runtime_eval.csv"


FIELDNAMES = [
    "sequence_id",
    "category",
    "turn_index",
    "question_hash",
    "expected_cache_hit",
    "actual_semantic_cache_hit",
    "actual_tool_result_cache_hit",
    "cache_expectation_met",
    "expected_contextualized",
    "actual_contextualized",
    "contextualization_met",
    "status",
    "elapsed_ms",
    "trace_total_latency_ms",
    "time_to_first_token_ms",
    "semantic_cache_reason",
    "semantic_cache_tool_name",
    "evidence_entity_key",
    "evidence_intent_key",
    "evidence_modifiers",
    "evidence_cache_reuse_allowed",
    "evidence_cache_reuse_block_reason",
    "evidence_canonical_query",
    "tool_result_cache_reason",
    "query_embedding_cache_hits",
    "query_embedding_cache_misses",
    "retrieval_cache_hit",
    "rerank_cache_hit",
    "hyde_generated",
    "hyde_used_for_vector",
    "reranking_provider",
    "source_count",
    "citation_count",
    "workflow_names",
    "workflow_summaries",
    "runtime_stop_reason",
    "runtime_final_decision",
    "error_summary",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Phase 58I continuous similar-question runtime behavior."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--max-tool-calls", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--limit-turns", type=int, default=0)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--no-clear-cache", action="store_true")
    args = parser.parse_args()

    sequences = load_sequences(args.cases)
    if args.execute and not args.no_clear_cache:
        clear_layered_cache_namespace()
    rows = run_sequences(
        sequences=sequences,
        execute=args.execute,
        base_url=args.base_url,
        top_k=args.top_k,
        max_tool_calls=args.max_tool_calls,
        timeout_seconds=args.timeout_seconds,
        limit_turns=args.limit_turns,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    completed = [row for row in rows if row["status"] == "completed"]
    cache_rows = [row for row in completed if row["expected_cache_hit"] != ""]
    cache_passed = sum(1 for row in cache_rows if row["cache_expectation_met"] == "true")
    contextual_rows = [row for row in completed if row["expected_contextualized"] != ""]
    contextual_passed = sum(1 for row in contextual_rows if row["contextualization_met"] == "true")
    hit_rows = [row for row in completed if row["actual_semantic_cache_hit"] == "true"]
    miss_rows = [row for row in completed if row["actual_semantic_cache_hit"] == "false"]

    print(
        "turns={turns} completed={completed} cache_expectations={cache_total} "
        "cache_passed={cache_passed} contextual_expectations={ctx_total} "
        "contextual_passed={ctx_passed} semantic_hits={semantic_hits} out={out}".format(
            turns=len(rows),
            completed=len(completed),
            cache_total=len(cache_rows),
            cache_passed=cache_passed,
            ctx_total=len(contextual_rows),
            ctx_passed=contextual_passed,
            semantic_hits=len(hit_rows),
            out=args.out,
        )
    )
    if hit_rows and miss_rows:
        hit_latencies = [float(row["elapsed_ms"]) for row in hit_rows]
        miss_latencies = [float(row["elapsed_ms"]) for row in miss_rows]
        print(
            "median_elapsed_ms miss={miss:.1f} hit={hit:.1f}".format(
                miss=statistics.median(miss_latencies),
                hit=statistics.median(hit_latencies),
            )
        )


def load_sequences(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    sequences = payload.get("sequences", []) if isinstance(payload, dict) else []
    return [sequence for sequence in sequences if isinstance(sequence, dict)]


def clear_layered_cache_namespace() -> None:
    from app.core.config import get_settings
    from app.services.cache.redis_client import get_redis_client

    settings = get_settings()
    client = get_redis_client(settings)
    if client is None:
        print("cache_clear=skipped redis_unavailable")
        return
    namespace = settings.layered_cache_namespace.strip(":") or "phase56-v1"
    patterns = [
        f"{namespace}:tool:*",
        f"{namespace}:retrieval:*",
        f"{namespace}:rerank:*",
    ]
    deleted = 0
    try:
        for pattern in patterns:
            keys = list(client.scan_iter(match=pattern, count=500))
            if keys:
                deleted += int(client.delete(*keys))
    except Exception as exc:  # noqa: BLE001 - evaluation can continue without clearing.
        print(f"cache_clear=failed reason={type(exc).__name__}")
        return
    print(f"cache_clear=ok deleted={deleted}")


def run_sequences(
    *,
    sequences: list[dict[str, Any]],
    execute: bool,
    base_url: str,
    top_k: int,
    max_tool_calls: int,
    timeout_seconds: float,
    limit_turns: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    remaining = limit_turns if limit_turns > 0 else None
    for sequence in sequences:
        conversation_id = None
        if execute:
            conversation_id = create_conversation(
                base_url=base_url,
                title=f"phase58i-eval-{sequence.get('id', '')}"[:120],
                timeout_seconds=timeout_seconds,
            )
        turns = sequence.get("turns", [])
        if not isinstance(turns, list):
            continue
        for index, turn in enumerate(turns, start=1):
            if remaining is not None and remaining <= 0:
                return rows
            if remaining is not None:
                remaining -= 1
            if not isinstance(turn, dict):
                continue
            rows.append(
                run_turn(
                    sequence=sequence,
                    turn=turn,
                    turn_index=index,
                    execute=execute,
                    base_url=base_url,
                    conversation_id=conversation_id,
                    top_k=top_k,
                    max_tool_calls=max_tool_calls,
                    timeout_seconds=timeout_seconds,
                )
            )
    return rows


def create_conversation(*, base_url: str, title: str, timeout_seconds: float) -> int:
    payload = {"title": title}
    response = post_json(
        f"{base_url.rstrip('/')}/conversations",
        payload,
        timeout_seconds=timeout_seconds,
        user_agent="phase58i-continuous-runtime-eval",
    )
    conversation_id = response.get("id")
    if not isinstance(conversation_id, int):
        raise RuntimeError("conversation response did not include an integer id")
    return conversation_id


def run_turn(
    *,
    sequence: dict[str, Any],
    turn: dict[str, Any],
    turn_index: int,
    execute: bool,
    base_url: str,
    conversation_id: int | None,
    top_k: int,
    max_tool_calls: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    question = str(turn.get("q", "")).strip()
    base_row = {
        "sequence_id": str(sequence.get("id", "")),
        "category": str(sequence.get("category", "")),
        "turn_index": turn_index,
        "question_hash": stable_short_hash(question),
        "expected_cache_hit": bool_to_cell(turn.get("expected_cache_hit")),
        "expected_contextualized": bool_to_cell(turn.get("expected_contextualized")),
    }
    if not execute:
        return row_from_response(
            base_row=base_row,
            response=None,
            elapsed_ms=0.0,
            status="dry_run",
            error_summary="",
        )

    payload = {
        "question": question,
        "conversation_id": conversation_id,
        "mode": "tool_calling_agent",
        "top_k": top_k,
        "max_tool_calls": max_tool_calls,
    }
    try:
        started = time.perf_counter()
        response = post_json(
            f"{base_url.rstrip('/')}/agent/query",
            payload,
            timeout_seconds=timeout_seconds,
            user_agent="phase58i-continuous-runtime-eval",
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        return row_from_response(
            base_row=base_row,
            response=response,
            elapsed_ms=elapsed_ms,
            status="completed",
            error_summary="",
        )
    except Exception as exc:  # noqa: BLE001 - evaluation should continue.
        return row_from_response(
            base_row=base_row,
            response=None,
            elapsed_ms=0.0,
            status="failed",
            error_summary=str(exc)[:160],
        )


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    user_agent: str,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": user_agent,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def row_from_response(
    *,
    base_row: dict[str, Any],
    response: dict[str, Any] | None,
    elapsed_ms: float,
    status: str,
    error_summary: str,
) -> dict[str, Any]:
    response = response or {}
    trace = response.get("latency_trace") if isinstance(response.get("latency_trace"), dict) else {}
    workflow_steps = response.get("workflow_steps") if isinstance(response.get("workflow_steps"), list) else []
    sources = response.get("sources") if isinstance(response.get("sources"), list) else []
    citations = response.get("citations") if isinstance(response.get("citations"), list) else []
    expected_cache = cell_to_bool(base_row.get("expected_cache_hit"))
    expected_contextualized = cell_to_bool(base_row.get("expected_contextualized"))
    actual_semantic_hit = bool(trace.get("semantic_cache_hit"))
    actual_tool_hit = bool(trace.get("tool_result_cache_hit"))
    actual_contextualized = bool(trace.get("runtime_contextualized"))
    cache_met = ""
    if expected_cache is not None:
        cache_met = bool_to_cell(actual_semantic_hit == expected_cache)
    contextual_met = ""
    if expected_contextualized is not None:
        contextual_met = bool_to_cell(actual_contextualized == expected_contextualized)
    row = {
        **base_row,
        "actual_semantic_cache_hit": bool_to_cell(actual_semantic_hit) if status == "completed" else "",
        "actual_tool_result_cache_hit": bool_to_cell(actual_tool_hit) if status == "completed" else "",
        "cache_expectation_met": cache_met,
        "actual_contextualized": bool_to_cell(actual_contextualized) if status == "completed" else "",
        "contextualization_met": contextual_met,
        "status": status,
        "elapsed_ms": elapsed_ms,
        "trace_total_latency_ms": trace.get("total_latency_ms", ""),
        "time_to_first_token_ms": trace.get("time_to_first_token_ms", ""),
        "semantic_cache_reason": trace.get("semantic_cache_reason", ""),
        "semantic_cache_tool_name": trace.get("semantic_cache_tool_name", ""),
        "evidence_entity_key": trace.get("evidence_entity_key", ""),
        "evidence_intent_key": trace.get("evidence_intent_key", ""),
        "evidence_modifiers": compact_json_cell(trace.get("evidence_modifiers", "")),
        "evidence_cache_reuse_allowed": trace.get("evidence_cache_reuse_allowed", ""),
        "evidence_cache_reuse_block_reason": trace.get("evidence_cache_reuse_block_reason", ""),
        "evidence_canonical_query": trace.get("evidence_canonical_query", ""),
        "tool_result_cache_reason": trace.get("tool_result_cache_reason", ""),
        "query_embedding_cache_hits": trace.get("query_embedding_cache_hits", ""),
        "query_embedding_cache_misses": trace.get("query_embedding_cache_misses", ""),
        "retrieval_cache_hit": trace.get("retrieval_cache_hit", ""),
        "rerank_cache_hit": trace.get("rerank_cache_hit", ""),
        "hyde_generated": trace.get("hyde_generated", ""),
        "hyde_used_for_vector": trace.get("hyde_used_for_vector", ""),
        "reranking_provider": trace.get("reranking_provider", ""),
        "source_count": len(sources),
        "citation_count": len(citations),
        "workflow_names": safe_join(
            [step.get("name", "") for step in workflow_steps if isinstance(step, dict)]
        ),
        "workflow_summaries": safe_workflow_summaries(workflow_steps),
        "runtime_stop_reason": trace.get("runtime_stop_reason", ""),
        "runtime_final_decision": trace.get("runtime_final_decision", ""),
        "error_summary": error_summary,
    }
    return {field: row.get(field, "") for field in FIELDNAMES}


def safe_join(values: list[Any], limit: int = 8) -> str:
    return "|".join(str(value).replace("\n", " ")[:120] for value in values[:limit])


def compact_json_cell(value: Any) -> str:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value) if value is not None else ""


def safe_workflow_summaries(workflow_steps: list[Any], limit: int = 4) -> str:
    summaries: list[str] = []
    for step in workflow_steps:
        if not isinstance(step, dict):
            continue
        name = str(step.get("name", ""))
        if name == "final_answer":
            continue
        summary = str(step.get("output_summary", "")).replace("\n", " ")
        summaries.append(summary[:120])
    return safe_join(summaries, limit=limit)


def stable_short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def bool_to_cell(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return ""


def cell_to_bool(value: object) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    return None


if __name__ == "__main__":
    main()
