from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.agent.react_service import ReActAgentService  # noqa: E402
from app.services.agent.service import AgentService  # noqa: E402
from app.services.generation.answer_service import CitationAnswerService  # noqa: E402
from app.services.generation.chat_model import (  # noqa: E402
    DeterministicChatModelProvider,
    create_chat_model_provider,
)
from app.services.retrieval.embedding import (  # noqa: E402
    DeterministicEmbeddingProvider,
    create_embedding_provider,
)
from scripts.evaluate_stage29_real_quality import sanitize_error  # noqa: E402


OUTPUT_PATH = ROOT / "data" / "evaluation" / "stage34_latency_traces.csv"

TRACE_FIELDS = [
    "query_embedding_latency_ms",
    "vector_search_latency_ms",
    "faiss_search_latency_ms",
    "numpy_search_latency_ms",
    "rerank_latency_ms",
    "planner_latency_ms",
    "tool_latency_ms",
    "answer_latency_ms",
    "time_to_first_token_ms",
    "time_to_final_ms",
    "iteration_count",
    "tool_call_count",
]

FIELDS = [
    "run_mode",
    "query_id",
    "category",
    "endpoint",
    "mode",
    "provider",
    "model_name",
    "embedding_provider",
    "embedding_model_name",
    "top_k",
    "max_tool_calls",
    "status",
    "error",
    "refused",
    "source_count",
    "citation_count",
    "load_mode",
    "primary_bottleneck",
    *TRACE_FIELDS,
]


@dataclass(frozen=True)
class LatencyCase:
    query_id: str
    category: str
    endpoint: str
    mode: str
    question: str
    top_k: int = 5
    max_tool_calls: int = 3


CASES = [
    LatencyCase(
        query_id="stage34_simple_filling_default",
        category="simple_fact",
        endpoint="agent_query",
        mode="default",
        question="What affects filling capacity in rock-filled concrete?",
    ),
    LatencyCase(
        query_id="stage34_simple_filling_react",
        category="simple_fact",
        endpoint="agent_query",
        mode="react_agent",
        question="What affects filling capacity in rock-filled concrete?",
    ),
    LatencyCase(
        query_id="stage34_thermal_default",
        category="long_answer",
        endpoint="agent_query",
        mode="default",
        question="How does thermal control affect rock-filled concrete dam construction?",
    ),
    LatencyCase(
        query_id="stage34_thermal_react",
        category="long_answer",
        endpoint="agent_query",
        mode="react_agent",
        question="How does thermal control affect rock-filled concrete dam construction?",
    ),
    LatencyCase(
        query_id="stage34_refusal_boundary_default",
        category="refusal_boundary",
        endpoint="agent_query",
        mode="default",
        question="请判定本工程的堆石混凝土配合比设计是否符合规范要求？",
    ),
    LatencyCase(
        query_id="stage34_refusal_boundary_react",
        category="refusal_boundary",
        endpoint="agent_query",
        mode="react_agent",
        question="请判定本工程的堆石混凝土配合比设计是否符合规范要求？",
    ),
    LatencyCase(
        query_id="stage34_mixed_language_default",
        category="mixed_language",
        endpoint="agent_query",
        mode="default",
        question="堆石混凝土 filling capacity 和 self-compacting concrete flowability 有什么关系？",
    ),
    LatencyCase(
        query_id="stage34_mixed_language_react",
        category="mixed_language",
        endpoint="agent_query",
        mode="react_agent",
        question="堆石混凝土 filling capacity 和 self-compacting concrete flowability 有什么关系？",
    ),
    LatencyCase(
        query_id="stage34_search_default",
        category="tool_search",
        endpoint="agent_query",
        mode="default",
        question="检索 thermal control rock-filled concrete 相关资料",
    ),
    LatencyCase(
        query_id="stage34_chat_filling",
        category="chat_baseline",
        endpoint="chat",
        mode="chat",
        question="What affects filling capacity in rock-filled concrete?",
    ),
]


def main() -> None:
    args = parse_args()
    rows = collect_traces(args)
    write_csv(Path(args.output), rows)
    completed = sum(1 for row in rows if row["status"] == "completed")
    print(f"stage34 latency traces: completed={completed}/{len(rows)} output={args.output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect sanitized stage 34 RAG/ReAct latency traces.",
    )
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--limit", type=int, default=len(CASES))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--execute-real", action="store_true")
    return parser.parse_args()


def collect_traces(args: argparse.Namespace) -> list[dict[str, object]]:
    init_db()
    chat_provider, embedding_provider, planner_chat_provider = build_providers(
        execute_real=args.execute_real
    )
    run_mode = "real" if args.execute_real else "dry_run"
    rows: list[dict[str, object]] = []

    with SessionLocal() as db:
        for case in CASES[: args.limit]:
            top_k = args.top_k or case.top_k
            started = time.perf_counter()
            try:
                if case.endpoint == "chat":
                    result = CitationAnswerService(
                        db=db,
                        chat_model_provider=chat_provider,
                        embedding_provider=embedding_provider,
                    ).answer(question=case.question, top_k=top_k, retrieval_mode="hybrid")
                    trace = {
                        "time_to_final_ms": elapsed_ms(started),
                        "tool_call_count": 0,
                        "iteration_count": 0,
                    }
                    rows.append(
                        row_from_trace(
                            case=case,
                            run_mode=run_mode,
                            provider=chat_provider.provider_name,
                            model_name=chat_provider.model_name,
                            embedding_provider_name=embedding_provider.provider_name,
                            embedding_model_name=embedding_provider.model_name,
                            top_k=top_k,
                            max_tool_calls=case.max_tool_calls,
                            trace=trace,
                            refused=result.refused,
                            source_count=len(result.sources),
                            citation_count=len(result.citations),
                        )
                    )
                    continue

                service_factory: Callable[[], object]
                if case.mode == "react_agent":
                    service_factory = lambda: ReActAgentService(
                        db=db,
                        chat_model_provider=chat_provider,
                        embedding_provider=embedding_provider,
                        planner_chat_provider=planner_chat_provider,
                    )
                else:
                    service_factory = lambda: AgentService(
                        db=db,
                        chat_model_provider=chat_provider,
                        embedding_provider=embedding_provider,
                    )
                result = service_factory().query(
                    question=case.question,
                    top_k=top_k,
                    max_tool_calls=case.max_tool_calls,
                )
                rows.append(
                    row_from_trace(
                        case=case,
                        run_mode=run_mode,
                        provider=chat_provider.provider_name,
                        model_name=chat_provider.model_name,
                        embedding_provider_name=embedding_provider.provider_name,
                        embedding_model_name=embedding_provider.model_name,
                        top_k=top_k,
                        max_tool_calls=case.max_tool_calls,
                        trace=result.latency_trace,
                        refused=result.refused,
                        source_count=len(result.sources),
                        citation_count=len(result.citations),
                    )
                )
            except Exception as exc:  # noqa: BLE001 - persisted as sanitized status.
                rows.append(error_row(case, run_mode=run_mode, error=sanitize_error(exc)))
    return rows


def build_providers(*, execute_real: bool):
    if not execute_real:
        return (
            DeterministicChatModelProvider(),
            DeterministicEmbeddingProvider(dimension=64),
            None,
        )

    settings = get_settings()
    planner_provider = None
    if settings.planner_chat_model_provider.strip():
        planner_provider = create_chat_model_provider(
            provider_name=settings.planner_chat_model_provider,
            model_name=settings.planner_chat_model_name,
            api_key=settings.planner_chat_model_api_key,
            base_url=settings.planner_chat_model_base_url,
            temperature=settings.planner_chat_model_temperature,
            timeout_seconds=settings.planner_chat_model_timeout_seconds,
        )
    return (
        create_chat_model_provider(
            provider_name=settings.chat_model_provider,
            model_name=settings.chat_model_name,
            api_key=settings.chat_model_api_key,
            base_url=settings.chat_model_base_url,
            temperature=settings.chat_model_temperature,
            timeout_seconds=settings.chat_model_timeout_seconds,
        ),
        create_embedding_provider(
            provider_name=settings.embedding_provider,
            model_name=settings.embedding_model_name,
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            dimension=settings.embedding_dimension or None,
            timeout_seconds=settings.embedding_timeout_seconds,
        ),
        planner_provider,
    )


def row_from_trace(
    *,
    case: LatencyCase,
    run_mode: str,
    provider: str,
    model_name: str,
    embedding_provider_name: str,
    embedding_model_name: str,
    top_k: int,
    max_tool_calls: int,
    trace: dict[str, object],
    refused: bool,
    source_count: int,
    citation_count: int,
) -> dict[str, object]:
    row: dict[str, object] = {
        "run_mode": run_mode,
        "query_id": case.query_id,
        "category": case.category,
        "endpoint": case.endpoint,
        "mode": case.mode,
        "provider": provider,
        "model_name": model_name,
        "embedding_provider": embedding_provider_name,
        "embedding_model_name": embedding_model_name,
        "top_k": top_k,
        "max_tool_calls": max_tool_calls,
        "status": "completed",
        "error": "",
        "refused": str(refused).lower(),
        "source_count": source_count,
        "citation_count": citation_count,
        "load_mode": safe_value(trace.get("load_mode", "")),
        "primary_bottleneck": primary_bottleneck(trace),
    }
    for field in TRACE_FIELDS:
        row[field] = safe_value(trace.get(field, 0.0))
    return row


def error_row(case: LatencyCase, *, run_mode: str, error: str) -> dict[str, object]:
    row = {
        "run_mode": run_mode,
        "query_id": case.query_id,
        "category": case.category,
        "endpoint": case.endpoint,
        "mode": case.mode,
        "provider": "",
        "model_name": "",
        "embedding_provider": "",
        "embedding_model_name": "",
        "top_k": case.top_k,
        "max_tool_calls": case.max_tool_calls,
        "status": "error",
        "error": error,
        "refused": "",
        "source_count": 0,
        "citation_count": 0,
        "load_mode": "",
        "primary_bottleneck": "",
    }
    for field in TRACE_FIELDS:
        row[field] = 0.0
    return row


def safe_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return value


def primary_bottleneck(trace: dict[str, object]) -> str:
    if (
        numeric(trace.get("time_to_final_ms")) > 0
        and all(numeric(trace.get(field)) == 0 for field in TRACE_FIELDS if field != "time_to_final_ms")
    ):
        return "endpoint_total_latency"
    candidates = {
        "embedding_provider_latency": numeric(trace.get("query_embedding_latency_ms")),
        "faiss_or_vector_search_latency": max(
            numeric(trace.get("faiss_search_latency_ms")),
            numeric(trace.get("vector_search_latency_ms")),
            numeric(trace.get("numpy_search_latency_ms")),
        ),
        "rerank_latency": numeric(trace.get("rerank_latency_ms")),
        "planner_latency": numeric(trace.get("planner_latency_ms")),
        "tool_iteration_overhead": numeric(trace.get("tool_latency_ms")),
        "answer_generation_latency": numeric(trace.get("answer_latency_ms")),
        "time_to_first_token_latency": numeric(trace.get("time_to_first_token_ms")),
    }
    return max(candidates.items(), key=lambda item: item[1])[0]


def numeric(value: object) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
