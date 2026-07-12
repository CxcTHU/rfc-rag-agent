"""Stage 37 Tool Calling Loop vs ReAct comparison.

The default evaluation runs both agent modes against the same local fixture
with deterministic providers, so full local pytest and CI never require real
chat, embedding, rerank, or provider tool-calling APIs.

Run with ``--execute`` to use the configured real database and providers. In
that mode ReAct uses the tiered setup (planner provider + answer provider),
while tool_calling_agent uses the planner provider as its single tools-capable
model. This intentionally exposes the Phase 37 tradeoff: tool-calling merges
planning and answering into one model path.
"""

from __future__ import annotations

import csv
import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["RERANKING_ENABLED"] = "false"

from app.core.config import get_settings  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository  # noqa: E402
from app.db.session import create_sqlite_engine  # noqa: E402
from app.services.agent.react_service import ReActAgentService  # noqa: E402
from app.services.agent.service import AgentQueryResult  # noqa: E402
from app.services.agent.tool_calling_service import ToolCallingAgentService  # noqa: E402
from app.services.generation.chat_model import (  # noqa: E402
    ChatToolCall,
    ChatModelProvider,
    DeterministicChatModelProvider,
    create_chat_model_provider,
)
from app.services.retrieval.embedding import (  # noqa: E402
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    create_embedding_provider,
)


DEFAULT_OUTPUT_DIR = ROOT / "data" / "evaluation"
RESULTS_PATH = DEFAULT_OUTPUT_DIR / "stage37_tool_calling_vs_react_results.csv"
SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "stage37_tool_calling_vs_react_summary.csv"
REAL_RESULTS_PATH = (
    DEFAULT_OUTPUT_DIR / "stage37_tool_calling_vs_react_real_results.csv"
)
REAL_SUMMARY_PATH = (
    DEFAULT_OUTPUT_DIR / "stage37_tool_calling_vs_react_real_summary.csv"
)

RESULT_FIELDS = [
    "run_type",
    "query_id",
    "category",
    "mode",
    "status",
    "refused",
    "refusal_reason_summary",
    "llm_call_count",
    "tool_call_count",
    "iteration_count",
    "time_to_first_token_ms",
    "time_to_final_ms",
    "citation_count",
    "source_count",
    "same_refusal_as_react",
    "same_top_source_as_react",
    "repeated_query_count",
    "near_duplicate_query_count",
    "executed_tool_call_count",
    "skipped_tool_call_count",
    "citation_repair_count",
    "error_summary",
    "decision_candidate",
]

SUMMARY_FIELDS = [
    "mode",
    "total",
    "errors",
    "refused",
    "avg_llm_call_count",
    "avg_tool_call_count",
    "avg_iteration_count",
    "avg_time_to_final_ms",
    "avg_citation_count",
    "avg_source_count",
    "avg_executed_tool_call_count",
    "avg_skipped_tool_call_count",
    "avg_citation_repair_count",
    "same_refusal_as_react",
    "same_top_source_as_react",
    "decision",
]


@dataclass(frozen=True)
class EvalCase:
    query_id: str
    question: str
    category: str
    history: tuple[str, ...] = ()
    tool_call_rounds: tuple[tuple[ChatToolCall, ...], ...] = ()


@dataclass(frozen=True)
class ModeOutcome:
    case: EvalCase
    mode: str
    result: AgentQueryResult | None
    time_to_final_ms: float
    run_type: str
    error: str = ""


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        query_id="stage37_single_hop_definition",
        question="What controls filling capacity in rock-filled concrete?",
        category="single_hop_definition",
    ),
    EvalCase(
        query_id="stage37_comparison",
        question=(
            "Compare filling capacity and thermal control mechanisms in "
            "rock-filled concrete."
        ),
        category="comparison",
    ),
    EvalCase(
        query_id="stage37_multi_dimensional",
        question=(
            "Summarize RFC filling quality, durability, and construction risk "
            "control evidence."
        ),
        category="multi_dimensional",
    ),
    EvalCase(
        query_id="stage37_bilingual_terms",
        question="What do 自密实混凝土 and SCC mean for rock-filled concrete filling?",
        category="bilingual_terminology",
    ),
    EvalCase(
        query_id="stage37_followup",
        question="What about its flowability evidence?",
        category="followup",
        history=("User previously asked about rock-filled concrete filling capacity.",),
    ),
    EvalCase(
        query_id="stage37_evidence_insufficient",
        question=(
            "What does rock-filled concrete evidence say about quantum curing "
            "telemetry?"
        ),
        category="evidence_insufficient",
    ),
    EvalCase(
        query_id="stage37_off_topic_refusal",
        question="Give me a tomato soup recipe.",
        category="off_topic_refusal",
    ),
    EvalCase(
        query_id="stage37_multi_hop_retrieval",
        question=(
            "Use multiple searches to connect thermal control and durability "
            "evidence for rock-filled concrete."
        ),
        category="multi_hop_retrieval",
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="stage37_call_thermal",
                    name="hybrid_search_knowledge",
                    arguments={"query": "rock-filled concrete thermal control", "top_k": 3},
                ),
            ),
            (
                ChatToolCall(
                    id="stage37_call_durability",
                    name="search_knowledge",
                    arguments={"query": "rock-filled concrete durability", "top_k": 3},
                ),
            ),
        ),
    ),
)


def make_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_fixture(db: Session) -> None:
    repository = DocumentRepository(db)
    repository.create_with_chunks(
        DocumentCreate(
            title="RFC filling quality",
            source_type="open_access_pdf",
            source_path="stage37/filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="stage37-filling",
            raw_path="data/raw/stage37/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Rock-filled concrete filling capacity is controlled by "
                    "self-compacting concrete flowability, aggregate grading, "
                    "void filling, and compactness monitoring."
                ),
                char_count=151,
                heading_path="Filling quality",
                start_char=0,
                end_char=151,
            )
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="RFC thermal control",
            source_type="open_access_pdf",
            source_path="stage37/thermal.md",
            file_name="thermal.md",
            file_extension=".md",
            content_hash="stage37-thermal",
            raw_path="data/raw/stage37/thermal.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Rock-filled concrete thermal control manages hydration heat, "
                    "adiabatic temperature rise, cooling pipes, and low-heat "
                    "cement to reduce cracking risk."
                ),
                char_count=150,
                heading_path="Thermal control",
                start_char=0,
                end_char=150,
            )
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="RFC durability evidence",
            source_type="open_access_pdf",
            source_path="stage37/durability.md",
            file_name="durability.md",
            file_extension=".md",
            content_hash="stage37-durability",
            raw_path="data/raw/stage37/durability.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Durability evidence for rock-filled concrete includes "
                    "impermeability, aggregate interlock, construction quality "
                    "control, and long-term monitoring."
                ),
                char_count=143,
                heading_path="Durability",
                start_char=0,
                end_char=143,
            )
        ],
    )


def evaluate_react(
    db: Session,
    embedding_provider: EmbeddingProvider,
    case: EvalCase,
    *,
    chat_provider: ChatModelProvider | None = None,
    planner_provider: ChatModelProvider | None = None,
    run_type: str = "deterministic",
) -> ModeOutcome:
    started = time.perf_counter()
    answer_provider = chat_provider or DeterministicChatModelProvider()
    try:
        result = ReActAgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=answer_provider,
            planner_chat_provider=planner_provider,
            log_answers=False,
        ).query(case.question, top_k=3, max_tool_calls=3, history=list(case.history))
    except Exception as exc:  # noqa: BLE001 - evaluation records safe summaries.
        return ModeOutcome(
            case=case,
            mode="react_agent",
            result=None,
            time_to_final_ms=elapsed_ms(started),
            run_type=run_type,
            error=safe_error_summary(exc),
        )
    return ModeOutcome(
        case=case,
        mode="react_agent",
        result=result,
        time_to_final_ms=elapsed_ms(started),
        run_type=run_type,
    )


def evaluate_tool_calling(
    db: Session,
    embedding_provider: EmbeddingProvider,
    case: EvalCase,
    *,
    chat_provider: ChatModelProvider | None = None,
    run_type: str = "deterministic",
) -> ModeOutcome:
    started = time.perf_counter()
    provider = chat_provider or DeterministicChatModelProvider(
        tool_call_rounds=case.tool_call_rounds
    )
    try:
        result = ToolCallingAgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=provider,
            log_answers=False,
        ).query(case.question, max_tool_calls=3, history=list(case.history))
    except Exception as exc:  # noqa: BLE001 - evaluation records safe summaries.
        return ModeOutcome(
            case=case,
            mode="tool_calling_agent",
            result=None,
            time_to_final_ms=elapsed_ms(started),
            run_type=run_type,
            error=safe_error_summary(exc),
        )
    return ModeOutcome(
        case=case,
        mode="tool_calling_agent",
        result=result,
        time_to_final_ms=elapsed_ms(started),
        run_type=run_type,
    )


def make_result_rows(outcomes: list[ModeOutcome]) -> list[dict[str, str]]:
    react_by_query = {
        outcome.case.query_id: outcome
        for outcome in outcomes
        if outcome.mode == "react_agent"
    }
    rows: list[dict[str, str]] = []
    for outcome in outcomes:
        react = react_by_query[outcome.case.query_id]
        rows.append(outcome_to_row(outcome, react))
    return rows


def outcome_to_row(outcome: ModeOutcome, react: ModeOutcome) -> dict[str, str]:
    result = outcome.result
    react_result = react.result
    status = "error" if outcome.error else "ok"
    refused = result_refused(result)
    same_refusal = (
        result_refused(result) == result_refused(react_result)
        if result is not None and react_result is not None
        else False
    )
    same_source = (
        top_source_id(result) == top_source_id(react_result)
        if result is not None and react_result is not None
        else False
    )
    return {
        "run_type": outcome.run_type,
        "query_id": outcome.case.query_id,
        "category": outcome.case.category,
        "mode": outcome.mode,
        "status": status,
        "refused": bool_text(refused) if result is not None else "",
        "refusal_reason_summary": refusal_reason_summary(result),
        "llm_call_count": str(metric_int(result, "llm_call_count")),
        "tool_call_count": str(result_tool_count(result)),
        "iteration_count": str(result_iterations(result)),
        "time_to_first_token_ms": metric_text(result, "time_to_first_token_ms"),
        "time_to_final_ms": f"{outcome.time_to_final_ms:.3f}",
        "citation_count": str(len(getattr(result, "citations", []) or [])) if result else "0",
        "source_count": str(len(getattr(result, "sources", []) or [])) if result else "0",
        "same_refusal_as_react": bool_text(same_refusal),
        "same_top_source_as_react": bool_text(same_source),
        "repeated_query_count": str(metric_int(result, "repeated_query_count")),
        "near_duplicate_query_count": str(metric_int(result, "near_duplicate_query_count")),
        "executed_tool_call_count": str(metric_int(result, "executed_tool_call_count")),
        "skipped_tool_call_count": str(metric_int(result, "skipped_tool_call_count")),
        "citation_repair_count": str(metric_int(result, "citation_repair_count")),
        "error_summary": outcome.error,
        "decision_candidate": decision_candidate(outcome, react, same_refusal, same_source),
    }


def summarize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    summary: list[dict[str, str]] = []
    for mode in sorted({row["mode"] for row in rows}):
        mode_rows = [row for row in rows if row["mode"] == mode]
        total = len(mode_rows)
        errors = sum(1 for row in mode_rows if row["status"] == "error")
        same_refusal = sum(
            1 for row in mode_rows if row["same_refusal_as_react"] == "true"
        )
        same_source = sum(
            1 for row in mode_rows if row["same_top_source_as_react"] == "true"
        )
        decision = "review"
        if errors == 0 and same_refusal == total and same_source >= total - 1:
            decision = "keep_parallel_candidate"
        summary.append(
            {
                "mode": mode,
                "total": str(total),
                "errors": str(errors),
                "refused": str(sum(1 for row in mode_rows if row["refused"] == "true")),
                "avg_llm_call_count": avg_field(mode_rows, "llm_call_count"),
                "avg_tool_call_count": avg_field(mode_rows, "tool_call_count"),
                "avg_iteration_count": avg_field(mode_rows, "iteration_count"),
                "avg_time_to_final_ms": avg_field(mode_rows, "time_to_final_ms"),
                "avg_citation_count": avg_field(mode_rows, "citation_count"),
                "avg_source_count": avg_field(mode_rows, "source_count"),
                "avg_executed_tool_call_count": avg_field(
                    mode_rows,
                    "executed_tool_call_count",
                ),
                "avg_skipped_tool_call_count": avg_field(
                    mode_rows,
                    "skipped_tool_call_count",
                ),
                "avg_citation_repair_count": avg_field(
                    mode_rows,
                    "citation_repair_count",
                ),
                "same_refusal_as_react": f"{same_refusal}/{total}",
                "same_top_source_as_react": f"{same_source}/{total}",
                "decision": decision,
            }
        )
    return summary


def run_evaluation(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    os.environ["RERANKING_ENABLED"] = "false"
    # The deterministic comparison owns an in-memory SQLite fixture.  It must
    # not consult a process-local Redis cache, otherwise CI results depend on
    # an external service rather than on the fixture seeded above.
    os.environ["REDIS_ENABLED"] = "false"
    get_settings.cache_clear()
    session_factory = make_session_factory()
    embedding_provider = DeterministicEmbeddingProvider(dimension=32)

    with session_factory() as db:
        seed_fixture(db)
        outcomes: list[ModeOutcome] = []
        for case in EVAL_CASES:
            outcomes.append(
                evaluate_react(
                    db,
                    embedding_provider,
                    case,
                    run_type="deterministic",
                )
            )
            outcomes.append(
                evaluate_tool_calling(
                    db,
                    embedding_provider,
                    case,
                    run_type="deterministic",
                )
            )

    rows = make_result_rows(outcomes)
    summary = summarize_rows(rows)
    write_outputs(output_dir, rows, summary, RESULTS_PATH.name, SUMMARY_PATH.name)
    return rows, summary


def run_real_evaluation(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    limit: int | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    settings = get_settings()
    session_factory = make_real_session_factory(settings.database_url)
    embedding_provider = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension or None,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    answer_provider = create_chat_model_provider(
        provider_name=settings.chat_model_provider,
        model_name=settings.chat_model_name,
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=settings.chat_model_timeout_seconds,
    )
    planner_provider = build_planner_provider(settings)
    cases = list(EVAL_CASES[:limit] if limit else EVAL_CASES)

    with session_factory() as db:
        outcomes: list[ModeOutcome] = []
        for case in cases:
            outcomes.append(
                evaluate_react(
                    db,
                    embedding_provider,
                    case,
                    chat_provider=answer_provider,
                    planner_provider=planner_provider,
                    run_type="real_provider",
                )
            )
            outcomes.append(
                evaluate_tool_calling(
                    db,
                    embedding_provider,
                    case,
                    chat_provider=planner_provider,
                    run_type="real_provider",
                )
            )

    rows = make_result_rows(outcomes)
    summary = summarize_rows(rows)
    write_outputs(output_dir, rows, summary, REAL_RESULTS_PATH.name, REAL_SUMMARY_PATH.name)
    return rows, summary


def build_planner_provider(settings) -> ChatModelProvider:
    if not settings.planner_chat_model_provider.strip():
        raise ValueError(
            "planner chat provider is required for --execute real-provider comparison"
        )
    return create_chat_model_provider(
        provider_name=settings.planner_chat_model_provider,
        model_name=settings.planner_chat_model_name,
        api_key=settings.planner_chat_model_api_key,
        base_url=settings.planner_chat_model_base_url,
        temperature=settings.planner_chat_model_temperature,
        timeout_seconds=settings.planner_chat_model_timeout_seconds,
    )


def make_real_session_factory(database_url: str):
    engine = create_sqlite_engine(database_url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def write_outputs(
    output_dir: Path,
    rows: list[dict[str, str]],
    summary: list[dict[str, str]],
    results_name: str,
    summary_name: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / results_name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / summary_name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary)


def result_refused(result: AgentQueryResult | None) -> bool:
    return bool(getattr(result, "refused", False)) if result is not None else False


def refusal_reason_summary(result: AgentQueryResult | None) -> str:
    if result is None or not getattr(result, "refused", False):
        return ""
    reason = (getattr(result, "refusal_reason", "") or "").casefold()
    if "valid tool-backed citations" in reason:
        return "missing_tool_backed_citations"
    if "off-topic" in reason or "domain anchor" in reason:
        return "off_topic"
    if "responsibility_gate" in reason:
        return "responsibility_gate"
    if "iteration limit" in reason:
        return "iteration_limit"
    if "tool execution failed" in reason or "request failed" in reason:
        return "tool_error"
    return "refused"


def result_tool_count(result: AgentQueryResult | None) -> int:
    if result is None:
        return 0
    return len(getattr(result, "tool_calls", []) or [])


def result_iterations(result: AgentQueryResult | None) -> int:
    if result is None:
        return 0
    return int(getattr(result, "iteration_count", 0) or 0)


def metric_int(result: AgentQueryResult | None, key: str) -> int:
    if result is None:
        return 0
    value = (getattr(result, "latency_trace", {}) or {}).get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def metric_text(result: AgentQueryResult | None, key: str) -> str:
    if result is None:
        return ""
    value = (getattr(result, "latency_trace", {}) or {}).get(key)
    return "" if value is None else str(value)


def top_source_id(result: AgentQueryResult | None) -> str:
    if result is None or not result.sources:
        return ""
    return result.sources[0].source_id


def decision_candidate(
    outcome: ModeOutcome,
    react: ModeOutcome,
    same_refusal: bool,
    same_source: bool,
) -> str:
    if outcome.error:
        return "review_error"
    if outcome.mode == "react_agent":
        return "baseline"
    if same_refusal and (same_source or result_refused(outcome.result)):
        return "parallel_candidate"
    if react.error:
        return "react_baseline_error_review"
    return "review_mismatch"


def avg_field(rows: list[dict[str, str]], field: str) -> str:
    values = [float(row[field]) for row in rows if row.get(field)]
    return f"{sum(values) / len(values):.3f}" if values else "0.000"


def elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0


def safe_error_summary(exc: Exception) -> str:
    text = str(exc).replace("\n", " ").strip()
    normalized = text.casefold()
    if "http 429" in normalized or "rate limit" in normalized:
        return "provider_rate_limit"
    if "timed out" in normalized or "timeout" in normalized:
        return "provider_timeout"
    if "tool_calls" in normalized or "tools" in normalized:
        return "provider_tool_calling_error"
    if "embedding" in normalized:
        return "embedding_provider_error"
    if "chat model request failed" in normalized:
        return "chat_provider_error"
    blocked_terms = ("api key", "authorization", "bearer", "raw_response")
    safe = text[:200]
    for term in blocked_terms:
        safe = safe.replace(term, "[redacted]")
        safe = safe.replace(term.title(), "[redacted]")
    return safe


def bool_text(value: bool) -> str:
    return str(value).lower()


def main() -> None:
    args = parse_args()
    if args.execute:
        _rows, summary = run_real_evaluation(
            output_dir=Path(args.output_dir),
            limit=args.limit,
        )
        label = "stage37 real-provider tool-calling-vs-react comparison"
    else:
        _rows, summary = run_evaluation(output_dir=Path(args.output_dir))
        label = "stage37 deterministic tool-calling-vs-react comparison"
    print(label)
    for row in summary:
        print(
            f"  {row['mode']}: errors={row['errors']} "
            f"avg_llm_calls={row['avg_llm_call_count']} "
            f"avg_tools={row['avg_tool_call_count']} "
            f"same_refusal={row['same_refusal_as_react']} "
            f"same_top_source={row['same_top_source_as_react']} "
            f"decision={row['decision']}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 37 Tool Calling Loop vs ReAct comparison."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Run against the configured real database and providers. ReAct uses "
            "planner + answer providers; tool_calling_agent uses the planner "
            "provider as the single tools-capable model."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of evaluation cases to run in --execute mode.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


if __name__ == "__main__":
    main()
