"""Phase 50 LangGraph Agent vs ReAct deterministic comparison.

The default run uses an in-memory SQLite fixture and deterministic providers.
It does not read API keys, call real providers, or require Redis. CSV outputs
contain metrics and safe summaries only.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["RERANKING_ENABLED"] = "false"
os.environ.setdefault("REDIS_URL", "")

from app.core.config import get_settings  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository  # noqa: E402
from app.services.agent.graph_builder import LangGraphAgentService  # noqa: E402
from app.services.agent.graph_checkpointer import reset_graph_checkpointer_cache  # noqa: E402
from app.services.agent.react_service import ReActAgentService  # noqa: E402
from app.services.agent.service import AgentQueryResult  # noqa: E402
from app.services.generation.chat_model import DeterministicChatModelProvider  # noqa: E402
from app.services.retrieval.embedding import DeterministicEmbeddingProvider  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / "data" / "evaluation"
RESULTS_PATH = DEFAULT_OUTPUT_DIR / "phase50_langgraph_vs_react_results.csv"
SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "phase50_langgraph_vs_react_summary.csv"

RESULT_FIELDS = [
    "run_type",
    "query_id",
    "category",
    "mode",
    "status",
    "refused",
    "refusal_reason_summary",
    "tool_call_count",
    "iteration_count",
    "time_to_final_ms",
    "citation_count",
    "source_count",
    "top_source_id",
    "same_refusal_as_react",
    "same_top_source_as_react",
    "same_citation_count_as_react",
    "query_embedding_cache_backend",
    "langgraph_checkpointer_backend",
    "error_summary",
    "decision_candidate",
]

SUMMARY_FIELDS = [
    "mode",
    "total",
    "errors",
    "refused",
    "avg_tool_call_count",
    "avg_iteration_count",
    "avg_time_to_final_ms",
    "avg_citation_count",
    "avg_source_count",
    "same_refusal_as_react",
    "same_top_source_as_react",
    "same_citation_count_as_react",
    "decision",
]


@dataclass(frozen=True)
class EvalCase:
    query_id: str
    question: str
    category: str
    history: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModeOutcome:
    case: EvalCase
    mode: str
    result: AgentQueryResult | None
    time_to_final_ms: float
    error: str = ""


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        "phase50_filling_capacity",
        "What controls filling capacity in rock-filled concrete?",
        "knowledge_search",
    ),
    EvalCase(
        "phase50_thermal_control",
        "Compare filling capacity and thermal control mechanisms in RFC.",
        "comparison",
    ),
    EvalCase(
        "phase50_table_evidence",
        "Use the table evidence to summarize mix ratio and flowability data.",
        "table_search",
    ),
    EvalCase(
        "phase50_figure_evidence",
        "Find figure evidence about RFC interface microstructure.",
        "figure_search",
    ),
    EvalCase(
        "phase50_followup_history",
        "What about its durability evidence?",
        "followup",
        ("User previously asked about rock-filled concrete filling capacity.",),
    ),
    EvalCase(
        "phase50_off_topic",
        "Give me a tomato soup recipe.",
        "off_topic_refusal",
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
            source_path="phase50/filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="phase50-filling",
            raw_path="data/raw/phase50/filling.md",
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
            ),
            ChunkCreate(
                chunk_index=1,
                content=(
                    "Mix ratio table: cement 240 kg/m3, fly ash 80 kg/m3, "
                    "water 150 kg/m3, target slump flow 650 mm."
                ),
                char_count=111,
                heading_path="Mix ratio table",
                start_char=152,
                end_char=263,
                chunk_type="table",
            ),
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="RFC thermal and durability evidence",
            source_type="open_access_pdf",
            source_path="phase50/thermal.md",
            file_name="thermal.md",
            file_extension=".md",
            content_hash="phase50-thermal",
            raw_path="data/raw/phase50/thermal.md",
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
            ),
            ChunkCreate(
                chunk_index=1,
                content=(
                    "Durability evidence includes impermeability, aggregate "
                    "interlock, construction quality control, and long-term monitoring."
                ),
                char_count=126,
                heading_path="Durability",
                start_char=151,
                end_char=277,
            ),
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="RFC interface microstructure figure",
            source_type="open_access_pdf",
            source_path="phase50/figure.md",
            file_name="figure.md",
            file_extension=".md",
            content_hash="phase50-figure",
            raw_path="data/raw/phase50/figure.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Figure description: RFC interface microstructure shows dense "
                    "paste around large rock aggregate and limited visible voids."
                ),
                char_count=120,
                heading_path="Interface figure",
                start_char=0,
                end_char=120,
                chunk_type="image_description",
                source_image_path="data/processed/images/phase50/page1_img1.png",
                caption="RFC interface microstructure",
                page_number=1,
            ),
        ],
    )


def evaluate_react(
    db: Session,
    embedding_provider: DeterministicEmbeddingProvider,
    case: EvalCase,
) -> ModeOutcome:
    started = time.perf_counter()
    try:
        result = ReActAgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        ).query(case.question, top_k=3, max_tool_calls=3, history=list(case.history))
    except Exception as exc:  # noqa: BLE001 - evaluation records safe summaries.
        return ModeOutcome(
            case=case,
            mode="react_agent",
            result=None,
            time_to_final_ms=elapsed_ms(started),
            error=safe_error_summary(exc),
        )
    return ModeOutcome(case, "react_agent", result, elapsed_ms(started))


def evaluate_langgraph(
    db: Session,
    embedding_provider: DeterministicEmbeddingProvider,
    case: EvalCase,
) -> ModeOutcome:
    started = time.perf_counter()
    try:
        result = LangGraphAgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        ).query(
            case.question,
            top_k=3,
            max_tool_calls=3,
            history=list(case.history),
            thread_id=f"phase50-eval:{case.query_id}",
        )
    except Exception as exc:  # noqa: BLE001 - evaluation records safe summaries.
        return ModeOutcome(
            case=case,
            mode="langgraph_agent",
            result=None,
            time_to_final_ms=elapsed_ms(started),
            error=safe_error_summary(exc),
        )
    return ModeOutcome(case, "langgraph_agent", result, elapsed_ms(started))


def run_evaluation(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    os.environ["RERANKING_ENABLED"] = "false"
    os.environ["REDIS_URL"] = ""
    get_settings.cache_clear()
    reset_graph_checkpointer_cache()
    session_factory = make_session_factory()
    embedding_provider = DeterministicEmbeddingProvider(dimension=32)

    with session_factory() as db:
        seed_fixture(db)
        outcomes: list[ModeOutcome] = []
        for case in EVAL_CASES:
            outcomes.append(evaluate_react(db, embedding_provider, case))
            outcomes.append(evaluate_langgraph(db, embedding_provider, case))

    rows = make_result_rows(outcomes)
    summary = summarize_rows(rows)
    write_outputs(output_dir, rows, summary)
    return rows, summary


def make_result_rows(outcomes: list[ModeOutcome]) -> list[dict[str, str]]:
    react_by_query = {
        outcome.case.query_id: outcome
        for outcome in outcomes
        if outcome.mode == "react_agent"
    }
    return [outcome_to_row(outcome, react_by_query[outcome.case.query_id]) for outcome in outcomes]


def outcome_to_row(outcome: ModeOutcome, react: ModeOutcome) -> dict[str, str]:
    result = outcome.result
    react_result = react.result
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
    same_citations = (
        citation_count(result) == citation_count(react_result)
        if result is not None and react_result is not None
        else False
    )
    return {
        "run_type": "deterministic",
        "query_id": outcome.case.query_id,
        "category": outcome.case.category,
        "mode": outcome.mode,
        "status": "error" if outcome.error else "ok",
        "refused": bool_text(result_refused(result)) if result is not None else "",
        "refusal_reason_summary": refusal_reason_summary(result),
        "tool_call_count": str(len(getattr(result, "tool_calls", []) or [])) if result else "0",
        "iteration_count": str(int(getattr(result, "iteration_count", 0) or 0)) if result else "0",
        "time_to_final_ms": f"{outcome.time_to_final_ms:.3f}",
        "citation_count": str(citation_count(result)),
        "source_count": str(len(getattr(result, "sources", []) or [])) if result else "0",
        "top_source_id": top_source_id(result),
        "same_refusal_as_react": bool_text(same_refusal),
        "same_top_source_as_react": bool_text(same_source),
        "same_citation_count_as_react": bool_text(same_citations),
        "query_embedding_cache_backend": metric_text(result, "query_embedding_cache_backend"),
        "langgraph_checkpointer_backend": metric_text(result, "langgraph_checkpointer_backend"),
        "error_summary": outcome.error,
        "decision_candidate": decision_candidate(outcome, react, same_refusal, same_source),
    }


def summarize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    summary: list[dict[str, str]] = []
    for mode in sorted({row["mode"] for row in rows}):
        mode_rows = [row for row in rows if row["mode"] == mode]
        total = len(mode_rows)
        errors = sum(1 for row in mode_rows if row["status"] == "error")
        same_refusal = sum(1 for row in mode_rows if row["same_refusal_as_react"] == "true")
        same_source = sum(1 for row in mode_rows if row["same_top_source_as_react"] == "true")
        same_citations = sum(
            1 for row in mode_rows if row["same_citation_count_as_react"] == "true"
        )
        decision = "review"
        if errors == 0 and same_refusal == total and same_source >= total - 1:
            decision = "parallel_candidate"
        summary.append(
            {
                "mode": mode,
                "total": str(total),
                "errors": str(errors),
                "refused": str(sum(1 for row in mode_rows if row["refused"] == "true")),
                "avg_tool_call_count": avg_field(mode_rows, "tool_call_count"),
                "avg_iteration_count": avg_field(mode_rows, "iteration_count"),
                "avg_time_to_final_ms": avg_field(mode_rows, "time_to_final_ms"),
                "avg_citation_count": avg_field(mode_rows, "citation_count"),
                "avg_source_count": avg_field(mode_rows, "source_count"),
                "same_refusal_as_react": f"{same_refusal}/{total}",
                "same_top_source_as_react": f"{same_source}/{total}",
                "same_citation_count_as_react": f"{same_citations}/{total}",
                "decision": decision,
            }
        )
    return summary


def write_outputs(
    output_dir: Path,
    rows: list[dict[str, str]],
    summary: list[dict[str, str]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / RESULTS_PATH.name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / SUMMARY_PATH.name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary)


def result_refused(result: AgentQueryResult | None) -> bool:
    return bool(getattr(result, "refused", False)) if result is not None else False


def citation_count(result: AgentQueryResult | None) -> int:
    return len(getattr(result, "citations", []) or []) if result else 0


def top_source_id(result: AgentQueryResult | None) -> str:
    if result is None or not result.sources:
        return ""
    return result.sources[0].source_id


def metric_text(result: AgentQueryResult | None, key: str) -> str:
    if result is None:
        return ""
    value = (getattr(result, "latency_trace", {}) or {}).get(key)
    return "" if value is None else str(value)


def refusal_reason_summary(result: AgentQueryResult | None) -> str:
    if result is None or not getattr(result, "refused", False):
        return ""
    reason = (getattr(result, "refusal_reason", "") or "").casefold()
    if "off-topic" in reason or "domain anchor" in reason:
        return "off_topic"
    if "iteration limit" in reason:
        return "iteration_limit"
    if "tool execution failed" in reason or "request failed" in reason:
        return "tool_error"
    return "refused"


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
    safe = text[:200]
    for term in ("api key", "authorization", "bearer", "raw_response"):
        safe = safe.replace(term, "[redacted]")
        safe = safe.replace(term.title(), "[redacted]")
    return safe


def bool_text(value: bool) -> str:
    return str(value).lower()


def main() -> None:
    args = parse_args()
    _rows, summary = run_evaluation(output_dir=Path(args.output_dir))
    print("phase50 deterministic langgraph-vs-react comparison")
    for row in summary:
        print(
            f"  {row['mode']}: errors={row['errors']} "
            f"avg_tools={row['avg_tool_call_count']} "
            f"same_refusal={row['same_refusal_as_react']} "
            f"same_top_source={row['same_top_source_as_react']} "
            f"decision={row['decision']}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 50 LangGraph Agent vs ReAct deterministic comparison."
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


if __name__ == "__main__":
    main()
