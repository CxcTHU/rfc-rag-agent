"""Stage 23 deterministic agentic-vs-default evaluation.

This script deliberately avoids real provider calls by using the local
deterministic chat and embedding providers with a small synthetic fixture. It
does not replace the historical stage 21 evaluation; it isolates the stage 21
SSL/provider instability so phase 23 can reason about automatic routing without
making real APIs a test prerequisite.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.models import Base  # noqa: E402
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository  # noqa: E402
from app.services.agent.service import AgentQueryResult, AgentService  # noqa: E402
from app.services.agentic.graph import run_agentic_rag  # noqa: E402
from app.services.agentic.state import AgenticResult  # noqa: E402
from app.services.generation.chat_model import DeterministicChatModelProvider  # noqa: E402
from app.services.retrieval.embedding import DeterministicEmbeddingProvider  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / "data" / "evaluation"
RESULTS_PATH = DEFAULT_OUTPUT_DIR / "stage23_agentic_auto_routing_results.csv"
SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "stage23_agentic_auto_routing_summary.csv"
DECISION_PATH = DEFAULT_OUTPUT_DIR / "stage23_agentic_auto_routing_decision.csv"

RESULT_FIELDS = [
    "query_id",
    "category",
    "expected_complexity",
    "expected_refused",
    "expected_agentic_gain",
    "default_error",
    "agentic_error",
    "default_tool",
    "default_answer_like",
    "agentic_answer_like",
    "default_refused",
    "agentic_refused",
    "default_sources",
    "agentic_sources",
    "agentic_iterations",
    "agentic_gain",
    "notes",
]

SUMMARY_FIELDS = [
    "method",
    "total",
    "errors",
    "error_rate",
    "answer_like_count",
    "refusal_matches",
    "refusal_total",
    "agentic_gain_count",
]

DECISION_FIELDS = [
    "default_error_rate",
    "agentic_error_rate",
    "agentic_gain_count",
    "decision",
    "reason",
]


@dataclass(frozen=True)
class EvalCase:
    query_id: str
    question: str
    category: str
    expected_complexity: str
    expected_refused: bool = False
    expected_agentic_gain: bool = False


@dataclass(frozen=True)
class DefaultEvalOutcome:
    result: AgentQueryResult | None
    error: str = ""


@dataclass(frozen=True)
class AgenticEvalOutcome:
    result: AgenticResult | None
    error: str = ""


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        query_id="stage23_simple_filling",
        question="What affects filling capacity in rock-filled concrete?",
        category="simple_concept",
        expected_complexity="simple",
    ),
    EvalCase(
        query_id="stage23_complex_search_compare",
        question=(
            "Search and compare filling capacity and thermal control "
            "mechanisms in rock-filled concrete."
        ),
        category="complex_compare",
        expected_complexity="complex",
        expected_agentic_gain=True,
    ),
    EvalCase(
        query_id="stage23_complex_multi_evidence",
        question=(
            "Explain how flowability, aggregate grading, hydration heat, and "
            "adiabatic temperature rise jointly affect construction quality "
            "in rock-filled concrete."
        ),
        category="complex_multi_evidence",
        expected_complexity="complex",
    ),
    EvalCase(
        query_id="stage23_refusal_off_topic",
        question="What is the recipe for tomato soup?",
        category="refusal",
        expected_complexity="simple",
        expected_refused=True,
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
            title="Filling guide",
            source_type="open_access_pdf",
            source_path="stage23/filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="stage23-filling",
            raw_path="data/raw/stage23/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Rock-filled concrete filling capacity depends on "
                    "self-compacting concrete flowability and aggregate grading."
                ),
                char_count=105,
                heading_path="Filling capacity",
                start_char=0,
                end_char=105,
            )
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="Thermal guide",
            source_type="open_access_pdf",
            source_path="stage23/thermal.md",
            file_name="thermal.md",
            file_extension=".md",
            content_hash="stage23-thermal",
            raw_path="data/raw/stage23/thermal.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Rock-filled concrete thermal control manages hydration "
                    "heat, adiabatic temperature rise, cooling pipes, and "
                    "low-heat cement."
                ),
                char_count=126,
                heading_path="Thermal control",
                start_char=0,
                end_char=126,
            )
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="Construction quality guide",
            source_type="open_access_pdf",
            source_path="stage23/quality.md",
            file_name="quality.md",
            file_extension=".md",
            content_hash="stage23-quality",
            raw_path="data/raw/stage23/quality.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Construction quality control for rock-filled concrete "
                    "combines filling performance, compactness detection, "
                    "thermal monitoring, and risk review."
                ),
                char_count=138,
                heading_path="Construction quality",
                start_char=0,
                end_char=138,
            )
        ],
    )


def evaluate_default(
    db: Session,
    embedding_provider: DeterministicEmbeddingProvider,
    chat_provider: DeterministicChatModelProvider,
    case: EvalCase,
) -> DefaultEvalOutcome:
    try:
        result = AgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_provider,
            log_answers=False,
        ).query(case.question, top_k=3)
    except Exception as exc:
        return DefaultEvalOutcome(result=None, error=str(exc)[:200])
    return DefaultEvalOutcome(result=result)


def evaluate_agentic(
    db: Session,
    embedding_provider: DeterministicEmbeddingProvider,
    chat_provider: DeterministicChatModelProvider,
    case: EvalCase,
) -> AgenticEvalOutcome:
    try:
        result = run_agentic_rag(
            question=case.question,
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_provider,
        )
    except Exception as exc:
        return AgenticEvalOutcome(result=None, error=str(exc)[:200])
    return AgenticEvalOutcome(result=result)


def default_tool_name(outcome: DefaultEvalOutcome) -> str:
    if outcome.result is None or not outcome.result.tool_calls:
        return ""
    return outcome.result.tool_calls[0].tool_name


def default_answer_like(outcome: DefaultEvalOutcome) -> bool:
    if outcome.result is None or outcome.result.refused:
        return False
    return default_tool_name(outcome) == "answer_with_citations"


def agentic_answer_like(outcome: AgenticEvalOutcome) -> bool:
    if outcome.result is None or outcome.result.refused:
        return False
    return bool(outcome.result.answer.strip())


def has_agentic_gain(
    case: EvalCase,
    default_outcome: DefaultEvalOutcome,
    agentic_outcome: AgenticEvalOutcome,
) -> bool:
    if case.expected_refused or default_outcome.error or agentic_outcome.error:
        return False
    if not agentic_answer_like(agentic_outcome):
        return False
    if case.expected_agentic_gain and not default_answer_like(default_outcome):
        return True
    return False


def make_result_row(
    case: EvalCase,
    default_outcome: DefaultEvalOutcome,
    agentic_outcome: AgenticEvalOutcome,
) -> dict[str, str]:
    default_result = default_outcome.result
    agentic_result = agentic_outcome.result
    agentic_gain = has_agentic_gain(case, default_outcome, agentic_outcome)
    notes = []
    if case.expected_agentic_gain:
        notes.append("complex task benefits when default intent resolves to search-only")
    if case.expected_refused:
        notes.append("off-topic refusal boundary")
    if not notes:
        notes.append("parity or stability check")

    return {
        "query_id": case.query_id,
        "category": case.category,
        "expected_complexity": case.expected_complexity,
        "expected_refused": str(case.expected_refused).lower(),
        "expected_agentic_gain": str(case.expected_agentic_gain).lower(),
        "default_error": default_outcome.error,
        "agentic_error": agentic_outcome.error,
        "default_tool": default_tool_name(default_outcome),
        "default_answer_like": str(default_answer_like(default_outcome)).lower(),
        "agentic_answer_like": str(agentic_answer_like(agentic_outcome)).lower(),
        "default_refused": str(default_result.refused).lower() if default_result else "",
        "agentic_refused": str(agentic_result.refused).lower() if agentic_result else "",
        "default_sources": str(len(default_result.sources)) if default_result else "0",
        "agentic_sources": str(len(agentic_result.sources)) if agentic_result else "0",
        "agentic_iterations": str(agentic_result.iteration_count) if agentic_result else "0",
        "agentic_gain": str(agentic_gain).lower(),
        "notes": "; ".join(notes),
    }


def summarize_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, str]]:
    total = len(rows)
    default_errors = sum(1 for row in rows if row["default_error"])
    agentic_errors = sum(1 for row in rows if row["agentic_error"])
    refusal_rows = [row for row in rows if row["expected_refused"] == "true"]
    default_refusal_matches = sum(1 for row in refusal_rows if row["default_refused"] == "true")
    agentic_refusal_matches = sum(1 for row in refusal_rows if row["agentic_refused"] == "true")
    agentic_gain_count = sum(1 for row in rows if row["agentic_gain"] == "true")

    default_summary = {
        "method": "default_agent_service",
        "total": str(total),
        "errors": str(default_errors),
        "error_rate": f"{default_errors / total:.3f}" if total else "0.000",
        "answer_like_count": str(sum(1 for row in rows if row["default_answer_like"] == "true")),
        "refusal_matches": str(default_refusal_matches),
        "refusal_total": str(len(refusal_rows)),
        "agentic_gain_count": "",
    }
    agentic_summary = {
        "method": "agentic_langgraph",
        "total": str(total),
        "errors": str(agentic_errors),
        "error_rate": f"{agentic_errors / total:.3f}" if total else "0.000",
        "answer_like_count": str(sum(1 for row in rows if row["agentic_answer_like"] == "true")),
        "refusal_matches": str(agentic_refusal_matches),
        "refusal_total": str(len(refusal_rows)),
        "agentic_gain_count": str(agentic_gain_count),
    }

    decision = make_decision(default_summary, agentic_summary, agentic_gain_count)
    return [default_summary, agentic_summary], decision


def make_decision(
    default_summary: dict[str, str],
    agentic_summary: dict[str, str],
    agentic_gain_count: int,
) -> dict[str, str]:
    default_error_rate = float(default_summary["error_rate"])
    agentic_error_rate = float(agentic_summary["error_rate"])

    if default_error_rate >= 0.10 or agentic_error_rate >= 0.10:
        decision = "blocked_high_error_rate"
        reason = (
            "deterministic comparison still has error_rate >= 0.10; "
            "do not use it for auto-routing evidence"
        )
    elif agentic_gain_count > 0:
        decision = "reliable_auto_route_candidate"
        reason = (
            "deterministic comparison isolated provider SSL issues and found "
            "at least one complex task where agentic produced an answer-like "
            "result while default intent stayed search-only"
        )
    else:
        decision = "reliable_difference_small"
        reason = (
            "deterministic comparison is stable, but current fixture shows "
            "little agentic-vs-default difference"
        )

    return {
        "default_error_rate": f"{default_error_rate:.3f}",
        "agentic_error_rate": f"{agentic_error_rate:.3f}",
        "agentic_gain_count": str(agentic_gain_count),
        "decision": decision,
        "reason": reason,
    }


def run_evaluation(output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, str]]:
    session_factory = make_session_factory()
    embedding_provider = DeterministicEmbeddingProvider(dimension=32)
    chat_provider = DeterministicChatModelProvider()

    with session_factory() as db:
        seed_fixture(db)
        rows = [
            make_result_row(
                case,
                evaluate_default(db, embedding_provider, chat_provider, case),
                evaluate_agentic(db, embedding_provider, chat_provider, case),
            )
            for case in EVAL_CASES
        ]

    summary, decision = summarize_rows(rows)
    write_outputs(output_dir, rows, summary, decision)
    return rows, summary, decision


def write_outputs(
    output_dir: Path,
    rows: list[dict[str, str]],
    summary: list[dict[str, str]],
    decision: dict[str, str],
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

    with (output_dir / DECISION_PATH.name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DECISION_FIELDS)
        writer.writeheader()
        writer.writerow(decision)


def main() -> None:
    _rows, summary, decision = run_evaluation()
    default_summary = next(row for row in summary if row["method"] == "default_agent_service")
    agentic_summary = next(row for row in summary if row["method"] == "agentic_langgraph")

    print("stage23 deterministic agentic vs default comparison")
    print(
        "  default: "
        f"errors={default_summary['errors']} "
        f"error_rate={default_summary['error_rate']} "
        f"answer_like={default_summary['answer_like_count']}"
    )
    print(
        "  agentic: "
        f"errors={agentic_summary['errors']} "
        f"error_rate={agentic_summary['error_rate']} "
        f"answer_like={agentic_summary['answer_like_count']} "
        f"gains={agentic_summary['agentic_gain_count']}"
    )
    print(f"  decision: {decision['decision']}")
    print(f"  reason: {decision['reason']}")


if __name__ == "__main__":
    main()
