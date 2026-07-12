from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.agent import get_agent_chat_model_provider, get_agent_embedding_provider
from app.db.session import SessionLocal
from app.main import init_db
from app.services.agent.tool_calling_service import ToolCallingAgentService


DEFAULT_OUTPUT = Path("data/evaluation/full_chain_latency_eval.csv")


@dataclass(frozen=True)
class Case:
    case_id: str
    category: str
    question: str
    top_k: int = 8
    max_tool_calls: int = 5


CASES = [
    Case("ordinary_advantages", "ordinary", "堆石混凝土有哪些主要技术优势？"),
    Case("dynamic_k_causes", "dynamic_k", "堆石混凝土裂缝的主要成因有哪些？"),
    Case("graph_standard", "graph_intent", "哪些标准或文献关系定义了堆石混凝土的适用范围？"),
    Case("table_mix_ratio", "table_intent", "请根据表格证据说明堆石混凝土配合比相关参数。"),
    Case("figure_failure", "figure_intent", "有没有堆石混凝土破坏形态或裂缝相关的图片证据？"),
    Case("fallback_rerank", "rerank_fallback", "堆石混凝土与自密实混凝土界面薄弱会带来什么影响？"),
    Case("citation_repair", "citation_repair", "堆石混凝土施工过程中的质量控制要点是什么？"),
    Case("boundary_refusal", "boundary", "请直接替我判断工程配合比是否合规并签字。"),
]


FIELDS = [
    "case_id",
    "category",
    "status",
    "total_ms",
    "planner_ms",
    "hyde_ms",
    "tool_ms",
    "answer_ms",
    "citation_repair_ms",
    "keyword_ms",
    "embedding_ms",
    "vector_ms",
    "graph_ms",
    "table_channel_ms",
    "figure_channel_ms",
    "rerank_ms",
    "rerank_fallback_ms",
    "rerank_primary_health_ms",
    "rerank_primary_health_status",
    "rerank_primary_health_cache_hit",
    "provider_http_ms",
    "provider_http_attempts",
    "provider_http_requests",
    "provider_http_reused",
    "retrieval_cache_hit",
    "retrieval_cache_reason",
    "rerank_cache_primary_hit",
    "rerank_cache_fallback_hit",
    "tool_result_cache_hit",
    "semantic_cache_hit",
    "hyde_generated",
    "reranking_fallback_used",
    "source_count",
    "citation_count",
    "refused",
    "error_summary",
]


def main() -> None:
    args = parse_args()
    rows = run_cases(limit=args.limit, execute=args.execute)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    completed = [float(row["total_ms"]) for row in rows if row["status"] == "completed"]
    over_50 = sum(value > 50000.0 for value in completed)
    print(
        "full_chain_latency "
        f"completed={len(completed)}/{len(rows)} "
        f"max_ms={max(completed) if completed else 0:.1f} "
        f"slow_over_50={over_50} "
        f"output={args.out}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate sanitized full-chain Agent latency. Dry-run by default; "
            "--execute uses configured local providers."
        )
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=len(CASES))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def run_cases(*, limit: int, execute: bool) -> list[dict[str, Any]]:
    selected = CASES[: max(0, min(limit, len(CASES)))]
    if not execute:
        return [empty_row(case, status="dry_run") for case in selected]
    init_db()
    chat_provider = get_agent_chat_model_provider()
    embedding_provider = get_agent_embedding_provider()
    rows: list[dict[str, Any]] = []
    with SessionLocal() as db:
        service = ToolCallingAgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_provider,
            log_answers=False,
        )
        for case in selected:
            started = time.perf_counter()
            try:
                result = service.query(
                    question=case.question,
                    max_tool_calls=case.max_tool_calls,
                )
                rows.append(row_from_result(case, result))
            except Exception as exc:  # noqa: BLE001 - keep evaluating later cases.
                row = empty_row(case, status="error")
                row["total_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
                row["error_summary"] = sanitize_error(exc)
                rows.append(row)
    return rows


def row_from_result(case: Case, result: Any) -> dict[str, Any]:
    trace = result.latency_trace or {}
    return {
        "case_id": case.case_id,
        "category": case.category,
        "status": "completed",
        "total_ms": number(trace.get("time_to_final_ms")),
        "planner_ms": number(trace.get("planner_latency_ms")),
        "hyde_ms": number(trace.get("hyde_latency_ms")),
        "tool_ms": number(trace.get("tool_latency_ms")),
        "answer_ms": number(trace.get("answer_latency_ms")),
        "citation_repair_ms": number(trace.get("citation_repair_latency_ms")),
        "keyword_ms": number(trace.get("keyword_search_latency_ms")),
        "embedding_ms": number(trace.get("query_embedding_latency_ms")),
        "vector_ms": number(trace.get("vector_search_latency_ms")),
        "graph_ms": number(trace.get("graph_search_latency_ms")),
        "table_channel_ms": number(trace.get("table_channel_latency_ms")),
        "figure_channel_ms": number(trace.get("figure_channel_latency_ms")),
        "rerank_ms": number(trace.get("rerank_latency_ms")),
        "rerank_fallback_ms": number(trace.get("rerank_fallback_latency_ms")),
        "rerank_primary_health_ms": number(trace.get("reranking_primary_health_latency_ms")),
        "rerank_primary_health_status": trace.get("reranking_primary_health_status", ""),
        "rerank_primary_health_cache_hit": trace.get("reranking_primary_health_cache_hit", ""),
        "provider_http_ms": number(trace.get("provider_http_latency_ms")),
        "provider_http_attempts": trace.get("provider_http_attempt_count", ""),
        "provider_http_requests": trace.get("provider_http_request_count", ""),
        "provider_http_reused": trace.get("provider_http_reused_connection_count", ""),
        "retrieval_cache_hit": trace.get("retrieval_cache_hit", ""),
        "retrieval_cache_reason": trace.get("retrieval_cache_reason", ""),
        "rerank_cache_primary_hit": trace.get("rerank_cache_primary_hit", ""),
        "rerank_cache_fallback_hit": trace.get("rerank_cache_fallback_hit", ""),
        "tool_result_cache_hit": trace.get("tool_result_cache_hit", ""),
        "semantic_cache_hit": trace.get("semantic_cache_hit", ""),
        "hyde_generated": trace.get("hyde_generated", ""),
        "reranking_fallback_used": trace.get("reranking_fallback_used", ""),
        "source_count": len(result.sources or []),
        "citation_count": len(result.citations or []),
        "refused": result.refused,
        "error_summary": "",
    }


def empty_row(case: Case, *, status: str) -> dict[str, Any]:
    return {
        field: "" for field in FIELDS
    } | {
        "case_id": case.case_id,
        "category": case.category,
        "status": status,
    }


def number(value: object) -> float:
    try:
        return round(float(value or 0.0), 3)
    except (TypeError, ValueError):
        return 0.0


def sanitize_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc).replace(chr(10), ' ')[:220]}"


if __name__ == "__main__":
    main()
