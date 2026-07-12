from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "data" / "evaluation" / "phase63_retrieval_runtime_cases.csv"

OUTPUT_FIELDS = (
    "case_id",
    "category",
    "runtime_mode",
    "executed",
    "ok",
    "error_category",
    "elapsed_ms",
    "judge_elapsed_ms",
    "expected_tool",
    "observed_tool_names",
    "expected_graph_requirement",
    "observed_graph_requirement",
    "plan_schema",
    "plan_digest",
    "selected_chunk_ids",
    "selected_count",
    "citation_count",
    "answer_accuracy_score",
    "citation_validity_score",
    "planner_fallback",
    "graph_fallback",
    "required_channels_satisfied",
    "reranking_degraded",
    "lexical_backend",
    "vector_backend",
    "vector_degraded",
    "streaming_degraded",
    "counts_match",
    "refused",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Phase 63 retrieval routing safely.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--legacy-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--phase63-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--planner-failure-base-url", default="")
    parser.add_argument("--graph-unavailable-base-url", default="")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--enforce-gates", action="store_true")
    return parser.parse_args()


def load_cases(path: Path, limit: int) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return rows[:limit] if limit > 0 else rows


def dry_run_row(case: dict[str, str], mode: str) -> dict[str, object]:
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "runtime_mode": mode,
        "executed": False,
        "ok": True,
        "error_category": "",
        "elapsed_ms": 0.0,
        "judge_elapsed_ms": 0.0,
        "expected_tool": case["expected_tool"],
        "observed_tool_names": "",
        "expected_graph_requirement": case["expected_graph_requirement"],
        "observed_graph_requirement": "",
        "plan_schema": "",
        "plan_digest": "",
        "selected_chunk_ids": "",
        "selected_count": 0,
        "citation_count": 0,
        "answer_accuracy_score": "",
        "citation_validity_score": "",
        "planner_fallback": "",
        "graph_fallback": "",
        "required_channels_satisfied": "",
        "reranking_degraded": "",
        "refused": False,
    }


def execute_row(
    case: dict[str, str],
    mode: str,
    base_url: str,
    timeout_seconds: float,
) -> dict[str, object]:
    started = time.perf_counter()
    payload: dict[str, Any] = {}
    error_category = ""
    ok = False
    judge_scores: dict[str, object] = {}
    agent_elapsed_ms: float | None = None
    judge_elapsed_ms = 0.0
    try:
        body = json.dumps(
            {"question": case["query"], "top_k": 8},
            ensure_ascii=False,
        ).encode("utf-8")
        call = request.Request(
            f"{base_url.rstrip('/')}/agent/query",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Retrieval-Runtime-Mode": mode,
            },
            method="POST",
        )
        with request.urlopen(call, timeout=timeout_seconds) as response:
            decoded = json.loads(response.read().decode("utf-8"))
        agent_elapsed_ms = (time.perf_counter() - started) * 1000.0
        payload = decoded if isinstance(decoded, dict) else {}
        ok = bool(payload)
        if ok and payload.get("answer"):
            judge_sources = payload.get("sources")
            judge_sources = judge_sources if isinstance(judge_sources, list) else []
            judge_citations = payload.get("citations")
            judge_citations = judge_citations if isinstance(judge_citations, list) else []
            judge_body = json.dumps(
                {
                    "question": case["query"],
                    "answer": str(payload.get("answer")),
                    "sources": judge_sources[:12],
                    "citations": judge_citations[:50],
                    "refused": bool(payload.get("refused", False)),
                    "refusal_reason": payload.get("refusal_reason"),
                },
                ensure_ascii=False,
            ).encode("utf-8")
            judge_call = request.Request(
                f"{base_url.rstrip('/')}/agent/judge",
                data=judge_body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            judge_started = time.perf_counter()
            with request.urlopen(judge_call, timeout=timeout_seconds) as judge_response:
                judge_payload = json.loads(judge_response.read().decode("utf-8"))
            judge_elapsed_ms = (time.perf_counter() - judge_started) * 1000.0
            if isinstance(judge_payload, dict) and isinstance(judge_payload.get("judge_scores"), dict):
                judge_scores = judge_payload["judge_scores"]
    except error.HTTPError as exc:
        error_category = f"http_{exc.code}"
    except error.URLError:
        error_category = "connection_error"
    except (TimeoutError, json.JSONDecodeError):
        error_category = "invalid_or_timeout_response"

    trace = payload.get("latency_trace")
    trace = trace if isinstance(trace, dict) else {}
    tool_calls = payload.get("tool_calls")
    tool_calls = tool_calls if isinstance(tool_calls, list) else []
    tool_names = [
        str(item.get("tool_name"))
        for item in tool_calls
        if isinstance(item, dict) and item.get("tool_name")
    ]
    selected_ids = trace.get("retrieval_selected_chunk_ids", [])
    if not isinstance(selected_ids, list):
        selected_ids = []
    citations = payload.get("citations")
    citation_count = len(citations) if isinstance(citations, list) else 0
    answer_accuracy_score = average_numeric_scores(
        judge_scores,
        ("faithfulness", "answer_coverage"),
    )
    citation_validity_score = average_numeric_scores(
        judge_scores,
        ("citation_support",),
    )
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "runtime_mode": mode,
        "executed": True,
        "ok": ok,
        "error_category": error_category,
        "elapsed_ms": round(
            agent_elapsed_ms
            if agent_elapsed_ms is not None
            else (time.perf_counter() - started) * 1000.0,
            3,
        ),
        "judge_elapsed_ms": round(judge_elapsed_ms, 3),
        "expected_tool": case["expected_tool"],
        "observed_tool_names": "|".join(tool_names),
        "expected_graph_requirement": case["expected_graph_requirement"],
        "observed_graph_requirement": trace.get("retrieval_graph_requirement", ""),
        "plan_schema": trace.get("retrieval_plan_schema", ""),
        "plan_digest": trace.get("retrieval_plan_digest", ""),
        "selected_chunk_ids": "|".join(str(value) for value in selected_ids[:20]),
        "selected_count": trace.get("retrieval_selected_count", len(selected_ids)),
        "citation_count": citation_count,
        "answer_accuracy_score": answer_accuracy_score,
        "citation_validity_score": citation_validity_score,
        "planner_fallback": bool(trace.get("retrieval_plan_fallback", False)),
        "graph_fallback": bool(trace.get("graph_search_fallback", False)),
        "required_channels_satisfied": bool(
            trace.get("retrieval_required_channels_satisfied", True)
        ),
        "reranking_degraded": bool(
            trace.get("reranking_error")
            or trace.get("reranking_fallback_error")
        ),
        "lexical_backend": trace.get("lexical_search_backend", ""),
        "vector_backend": trace.get("vector_search_backend", ""),
        "vector_degraded": bool(trace.get("vector_search_degraded", False)),
        "streaming_degraded": bool(trace.get("streaming_degraded", False)),
        "counts_match": int(trace.get("retrieval_selected_count", len(selected_ids)) or 0)
        == len(selected_ids),
        "refused": bool(payload.get("refused", False)),
    }


def average_numeric_scores(values: dict[str, object], keys: tuple[str, ...]) -> float | str:
    scores: list[float] = []
    for key in keys:
        try:
            score = float(values.get(key, ""))
        except (TypeError, ValueError):
            continue
        if math.isfinite(score):
            scores.append(score)
    return round(statistics.fmean(scores), 4) if scores else ""


def numeric_values(rows: list[dict[str, object]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        try:
            value = float(row.get(field, ""))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(value)
    return values


def rate(rows: list[dict[str, object]], predicate) -> float | None:
    if not rows:
        return None
    return round(sum(1 for row in rows if predicate(row)) / len(rows), 4)


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return round(ordered[index], 3)


def relative_delta(current: float | None, legacy: float | None) -> float | None:
    if current is None or legacy is None or legacy <= 0:
        return None
    return round((current - legacy) / legacy, 4)


def mean_delta(
    current: list[dict[str, object]],
    legacy: list[dict[str, object]],
    field: str,
) -> float | None:
    current_values = numeric_values(current, field)
    legacy_values = numeric_values(legacy, field)
    if not current_values or not legacy_values:
        return None
    return round(statistics.fmean(current_values) - statistics.fmean(legacy_values), 4)


def gate_summary(rows: list[dict[str, object]], *, executed: bool) -> dict[str, object]:
    if not executed:
        return {
            "validation_mode": "case_schema_only",
            "case_count": len(rows) // 2,
            "routing_metrics": "not_executed",
            "gates_passed": False,
            "safe_output_columns": list(OUTPUT_FIELDS),
        }

    current = [row for row in rows if row["runtime_mode"] == "phase63"]
    legacy = [row for row in rows if row["runtime_mode"] == "legacy"]
    relationship_current = [
        row for row in current if row["expected_graph_requirement"] in {"required", "preferred"}
    ]
    predicted_current = [
        row for row in current if row["observed_graph_requirement"] in {"required", "preferred"}
    ]
    true_positive_ids = {
        str(row["case_id"])
        for row in predicted_current
        if row["expected_graph_requirement"] in {"required", "preferred"}
    }
    relationship_ids = {str(row["case_id"]) for row in relationship_current}
    relationship_precision = (
        round(len(true_positive_ids) / len(predicted_current), 4)
        if predicted_current
        else 0.0
    )
    relationship_recall = (
        round(len(true_positive_ids) / len(relationship_ids), 4)
        if relationship_ids
        else 0.0
    )
    graph_negative = [
        row for row in current if row["expected_graph_requirement"] == "disabled"
    ]
    graph_negative_false_positives = sum(
        1
        for row in graph_negative
        if row["observed_graph_requirement"] in {"required", "preferred"}
    )
    figure_current = [row for row in current if row["expected_tool"] == "search_figures"]
    figure_legacy = [row for row in legacy if row["expected_tool"] == "search_figures"]
    table_current = [row for row in current if row["expected_tool"] == "search_tables"]
    table_legacy = [row for row in legacy if row["expected_tool"] == "search_tables"]
    tool_fulfilled = lambda expected: lambda row: expected in str(row["observed_tool_names"]).split("|")
    fallback_rows = [row for row in current if row["category"] == "planner_failure"]
    graph_unavailable_rows = [
        row for row in current if row["category"] == "graph_unavailable"
    ]
    ordinary_current = [row for row in current if row["category"] in {"ordinary", "text"}]
    ordinary_legacy = [row for row in legacy if row["category"] in {"ordinary", "text"}]
    ordinary_current_p95 = percentile(numeric_values(ordinary_current, "elapsed_ms"), 0.95)
    ordinary_legacy_p95 = percentile(numeric_values(ordinary_legacy, "elapsed_ms"), 0.95)
    relationship_legacy = [
        row for row in legacy if row["expected_graph_requirement"] in {"required", "preferred"}
    ]
    relationship_current_p95 = percentile(numeric_values(relationship_current, "elapsed_ms"), 0.95)
    relationship_legacy_p95 = percentile(numeric_values(relationship_legacy, "elapsed_ms"), 0.95)
    figure_delta = (
        (rate(figure_current, tool_fulfilled("search_figures")) or 0.0)
        - (rate(figure_legacy, tool_fulfilled("search_figures")) or 0.0)
    )
    table_delta = (
        (rate(table_current, tool_fulfilled("search_tables")) or 0.0)
        - (rate(table_legacy, tool_fulfilled("search_tables")) or 0.0)
    )
    metrics = {
        "ordinary_answer_accuracy_delta": mean_delta(
            ordinary_current, ordinary_legacy, "answer_accuracy_score"
        ),
        "relationship_route_precision": relationship_precision,
        "relationship_route_recall": relationship_recall,
        "graph_negative_false_positives": graph_negative_false_positives,
        "explicit_figure_fulfillment_delta": round(figure_delta, 4),
        "explicit_table_fulfillment_delta": round(table_delta, 4),
        "citation_validity_delta": mean_delta(
            current, legacy, "citation_validity_score"
        ),
        "planner_failure_fallback_completion": rate(
            fallback_rows,
            lambda row: bool(row["ok"]) and bool(row["planner_fallback"]),
        ),
        "graph_unavailable_fallback_completion": rate(
            graph_unavailable_rows,
            lambda row: bool(row["ok"]) and bool(row["graph_fallback"]),
        ),
        "ordinary_p95_latency_increase": relative_delta(
            ordinary_current_p95, ordinary_legacy_p95
        ),
        "relationship_p95_latency_increase": relative_delta(
            relationship_current_p95, relationship_legacy_p95
        ),
        "silent_reranker_degradation": sum(
            1 for row in current if bool(row["reranking_degraded"])
        ),
        "production_retrieval_contract_violations": sum(
            1
            for row in current
            if row.get("lexical_backend") != "bm25"
            or row.get("vector_backend") != "pgvector_hnsw"
            or bool(row.get("vector_degraded"))
            or bool(row.get("streaming_degraded"))
            or not bool(row.get("counts_match"))
        ),
    }
    gates = {
        "ordinary_answer_accuracy_delta": metrics["ordinary_answer_accuracy_delta"] is not None
        and float(metrics["ordinary_answer_accuracy_delta"]) >= 0.0,
        "relationship_route_precision": relationship_precision >= 0.90,
        "relationship_route_recall": relationship_recall >= 0.90,
        "graph_negative_false_positives": graph_negative_false_positives == 0,
        "explicit_figure_fulfillment_delta": figure_delta >= 0.0,
        "explicit_table_fulfillment_delta": table_delta >= 0.0,
        "citation_validity_delta": metrics["citation_validity_delta"] is not None
        and float(metrics["citation_validity_delta"]) >= 0.0,
        "planner_failure_fallback_completion": metrics["planner_failure_fallback_completion"] == 1.0,
        "graph_unavailable_fallback_completion": metrics["graph_unavailable_fallback_completion"] == 1.0,
        "ordinary_p95_latency_increase": metrics["ordinary_p95_latency_increase"] is not None
        and float(metrics["ordinary_p95_latency_increase"]) <= 0.15,
        "relationship_p95_latency_increase": metrics["relationship_p95_latency_increase"] is not None
        and float(metrics["relationship_p95_latency_increase"]) <= 0.30,
        "silent_reranker_degradation": metrics["silent_reranker_degradation"] == 0,
        "production_retrieval_contract": metrics[
            "production_retrieval_contract_violations"
        ] == 0,
    }
    return {
        "validation_mode": "dual_runtime_execution",
        "case_count": len(current),
        "metrics": metrics,
        "gates": gates,
        "gates_passed": all(gates.values()),
        "safe_output_columns": list(OUTPUT_FIELDS),
    }


def main() -> int:
    args = parse_args()
    if (
        args.execute
        and args.legacy_base_url.rstrip("/")
        == args.phase63_base_url.rstrip("/")
    ):
        print(
            json.dumps(
                {
                    "error": "execute_requires_distinct_runtime_endpoints",
                    "hint": "start separately configured legacy and Phase 63 app processes",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    if args.execute and (
        not args.planner_failure_base_url.strip()
        or not args.graph_unavailable_base_url.strip()
    ):
        print(
            json.dumps(
                {
                    "error": "execute_requires_fault_profile_endpoints",
                    "hint": (
                        "provide Phase 63 endpoints configured with an unavailable "
                        "identity provider and an unavailable graph"
                    ),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    cases = load_cases(args.cases, max(args.limit, 0))
    rows: list[dict[str, object]] = []
    for case in cases:
        for mode, base_url in (
            ("legacy", args.legacy_base_url),
            ("phase63", args.phase63_base_url),
        ):
            if mode == "phase63" and case["category"] == "planner_failure":
                base_url = args.planner_failure_base_url
            elif mode == "phase63" and case["category"] == "graph_unavailable":
                base_url = args.graph_unavailable_base_url
            rows.append(
                execute_row(case, mode, base_url, args.timeout_seconds)
                if args.execute
                else dry_run_row(case, mode)
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    summary = gate_summary(rows, executed=args.execute)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if args.enforce_gates and not bool(summary["gates_passed"]):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
