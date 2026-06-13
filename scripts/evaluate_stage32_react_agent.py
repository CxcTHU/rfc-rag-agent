"""Stage 32 deterministic ReAct agent comparison.

The script compares default AgentService, the old LangGraph agentic path, and
the new ReAct agent against a small local fixture. It deliberately uses
deterministic providers so CI and full local tests never depend on real MIMO,
Jina, or other external APIs.
"""

from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["RERANKING_ENABLED"] = "false"

from app.core.config import get_settings  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository  # noqa: E402
from app.services.agent.service import AgentQueryResult, AgentService  # noqa: E402
from app.services.agent.react_service import ReActAgentService  # noqa: E402
from app.services.agentic.graph import run_agentic_rag  # noqa: E402
from app.services.agentic.state import AgenticResult  # noqa: E402
from app.services.generation.chat_model import DeterministicChatModelProvider  # noqa: E402
from app.services.retrieval.embedding import DeterministicEmbeddingProvider  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / "data" / "evaluation"
RESULTS_PATH = DEFAULT_OUTPUT_DIR / "stage32_react_agent_results.csv"
SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "stage32_react_agent_summary.csv"

RESULT_FIELDS = [
    "query_id",
    "category",
    "expected_refused",
    "mode",
    "error",
    "answer_like",
    "refused",
    "refusal_match",
    "refusal_category",
    "source_count",
    "citation_valid",
    "tool_count",
    "iteration_count",
    "workflow_step_count",
    "notes",
]

SUMMARY_FIELDS = [
    "mode",
    "total",
    "errors",
    "error_rate",
    "answer_like_count",
    "refusal_matches",
    "refusal_total",
    "avg_tool_count",
    "avg_iteration_count",
    "decision",
]


@dataclass(frozen=True)
class EvalCase:
    query_id: str
    question: str
    category: str
    expected_refused: bool = False
    notes: str = ""


@dataclass(frozen=True)
class ModeOutcome:
    mode: str
    result: AgentQueryResult | AgenticResult | None
    error: str = ""


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        query_id="stage32_filling_capacity",
        question="What controls filling capacity in rock-filled concrete?",
        category="direct_retrieval",
        notes="baseline retrieval and citation check",
    ),
    EvalCase(
        query_id="stage32_rewrite_flowability",
        question="Rewrite if needed and find evidence about RFC flow and compactness.",
        category="rewrite_then_retrieve",
        notes="ReAct should be able to choose rewrite or retrieval under control",
    ),
    EvalCase(
        query_id="stage32_multi_evidence",
        question=(
            "Compare filling quality, thermal control, and durability evidence "
            "for rock-filled concrete construction."
        ),
        category="multi_evidence",
        notes="multi-source answer stability",
    ),
    EvalCase(
        query_id="stage32_refusal_off_topic",
        question="Give me a recipe for tomato soup.",
        category="refusal",
        expected_refused=True,
        notes="domain refusal boundary",
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
            source_path="stage32/filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="stage32-filling",
            raw_path="data/raw/stage32/filling.md",
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
            source_path="stage32/thermal.md",
            file_name="thermal.md",
            file_extension=".md",
            content_hash="stage32-thermal",
            raw_path="data/raw/stage32/thermal.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Rock-filled concrete thermal control manages hydration "
                    "heat, adiabatic temperature rise, cooling pipes, and "
                    "low-heat cement to reduce cracking risk."
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
            title="RFC durability",
            source_type="open_access_pdf",
            source_path="stage32/durability.md",
            file_name="durability.md",
            file_extension=".md",
            content_hash="stage32-durability",
            raw_path="data/raw/stage32/durability.md",
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


def evaluate_default(
    db: Session,
    embedding_provider: DeterministicEmbeddingProvider,
    chat_provider: DeterministicChatModelProvider,
    case: EvalCase,
) -> ModeOutcome:
    try:
        result = AgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_provider,
            log_answers=False,
        ).query(case.question, top_k=3, max_tool_calls=3)
    except Exception as exc:
        return ModeOutcome(mode="default", result=None, error=str(exc)[:200])
    return ModeOutcome(mode="default", result=result)


def evaluate_agentic(
    db: Session,
    embedding_provider: DeterministicEmbeddingProvider,
    chat_provider: DeterministicChatModelProvider,
    case: EvalCase,
) -> ModeOutcome:
    try:
        result = run_agentic_rag(
            question=case.question,
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_provider,
        )
    except Exception as exc:
        return ModeOutcome(mode="agentic_langgraph", result=None, error=str(exc)[:200])
    return ModeOutcome(mode="agentic_langgraph", result=result)


def evaluate_react(
    db: Session,
    embedding_provider: DeterministicEmbeddingProvider,
    chat_provider: DeterministicChatModelProvider,
    case: EvalCase,
) -> ModeOutcome:
    try:
        result = ReActAgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_provider,
            log_answers=False,
        ).query(case.question, top_k=3, max_tool_calls=3)
    except Exception as exc:
        return ModeOutcome(mode="react_agent", result=None, error=str(exc)[:200])
    return ModeOutcome(mode="react_agent", result=result)


def result_sources(result: AgentQueryResult | AgenticResult | None) -> int:
    if result is None:
        return 0
    return len(getattr(result, "sources", []) or [])


def result_refused(result: AgentQueryResult | AgenticResult | None) -> bool:
    return bool(getattr(result, "refused", False)) if result is not None else False


def result_answer_like(result: AgentQueryResult | AgenticResult | None) -> bool:
    if result is None or result_refused(result):
        return False
    return bool((getattr(result, "answer", "") or "").strip())


def result_citation_valid(result: AgentQueryResult | AgenticResult | None) -> bool:
    if result is None:
        return False
    invalid = getattr(result, "invalid_citations", []) or []
    if invalid:
        return False
    if result_refused(result):
        return True
    return result_sources(result) > 0


def result_tool_count(result: AgentQueryResult | AgenticResult | None) -> int:
    if result is None:
        return 0
    tool_calls = getattr(result, "tool_calls", []) or []
    if tool_calls:
        return len(tool_calls)
    workflow_steps = getattr(result, "workflow_steps", []) or []
    return len(workflow_steps)


def result_workflow_steps(result: AgentQueryResult | AgenticResult | None) -> int:
    if result is None:
        return 0
    return len(getattr(result, "workflow_steps", []) or [])


def result_iterations(result: AgentQueryResult | AgenticResult | None) -> int:
    if result is None:
        return 0
    return int(getattr(result, "iteration_count", 0) or 0)


def make_result_rows(case: EvalCase, outcomes: list[ModeOutcome]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for outcome in outcomes:
        result = outcome.result
        refused = result_refused(result)
        refusal_match = refused == case.expected_refused
        rows.append(
            {
                "query_id": case.query_id,
                "category": case.category,
                "expected_refused": str(case.expected_refused).lower(),
                "mode": outcome.mode,
                "error": outcome.error,
                "answer_like": str(result_answer_like(result)).lower(),
                "refused": str(refused).lower() if result else "",
                "refusal_match": str(refusal_match).lower() if result else "false",
                "refusal_category": str(getattr(result, "refusal_category", "") or "") if result else "",
                "source_count": str(result_sources(result)),
                "citation_valid": str(result_citation_valid(result)).lower(),
                "tool_count": str(result_tool_count(result)),
                "iteration_count": str(result_iterations(result)),
                "workflow_step_count": str(result_workflow_steps(result)),
                "notes": case.notes,
            }
        )
    return rows


def summarize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    summary: list[dict[str, str]] = []
    modes = sorted({row["mode"] for row in rows})
    for mode in modes:
        mode_rows = [row for row in rows if row["mode"] == mode]
        total = len(mode_rows)
        errors = sum(1 for row in mode_rows if row["error"])
        refusal_rows = [row for row in mode_rows if row["expected_refused"] == "true"]
        tool_counts = [int(row["tool_count"] or "0") for row in mode_rows]
        iteration_counts = [int(row["iteration_count"] or "0") for row in mode_rows]
        decision = "pass" if errors == 0 and all(row["citation_valid"] == "true" for row in mode_rows) else "review"
        summary.append(
            {
                "mode": mode,
                "total": str(total),
                "errors": str(errors),
                "error_rate": f"{errors / total:.3f}" if total else "0.000",
                "answer_like_count": str(sum(1 for row in mode_rows if row["answer_like"] == "true")),
                "refusal_matches": str(sum(1 for row in refusal_rows if row["refusal_match"] == "true")),
                "refusal_total": str(len(refusal_rows)),
                "avg_tool_count": f"{sum(tool_counts) / total:.2f}" if total else "0.00",
                "avg_iteration_count": f"{sum(iteration_counts) / total:.2f}" if total else "0.00",
                "decision": decision,
            }
        )
    return summary


def run_evaluation(output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    os.environ["RERANKING_ENABLED"] = "false"
    get_settings.cache_clear()
    session_factory = make_session_factory()
    embedding_provider = DeterministicEmbeddingProvider(dimension=32)
    chat_provider = DeterministicChatModelProvider()

    with session_factory() as db:
        seed_fixture(db)
        rows: list[dict[str, str]] = []
        for case in EVAL_CASES:
            outcomes = [
                evaluate_default(db, embedding_provider, chat_provider, case),
                evaluate_agentic(db, embedding_provider, chat_provider, case),
                evaluate_react(db, embedding_provider, chat_provider, case),
            ]
            rows.extend(make_result_rows(case, outcomes))

    summary = summarize_rows(rows)
    write_outputs(output_dir, rows, summary)
    return rows, summary


def write_outputs(output_dir: Path, rows: list[dict[str, str]], summary: list[dict[str, str]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / RESULTS_PATH.name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    with (output_dir / SUMMARY_PATH.name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary)


def main() -> None:
    _rows, summary = run_evaluation()
    print("stage32 deterministic react-agent comparison")
    for row in summary:
        print(
            f"  {row['mode']}: errors={row['errors']} "
            f"error_rate={row['error_rate']} answer_like={row['answer_like_count']} "
            f"refusal_matches={row['refusal_matches']}/{row['refusal_total']} "
            f"avg_tools={row['avg_tool_count']} decision={row['decision']}"
        )


if __name__ == "__main__":
    main()
