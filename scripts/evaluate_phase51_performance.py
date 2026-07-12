"""Phase 51 performance evaluation across Brain, Agent, LangGraph, and cache paths.

Default execution is a deterministic dry-run against an in-memory SQLite
fixture. It does not call real providers, Redis, or PostgreSQL. Use
``--execute`` to run against the locally configured database and providers.
CSV outputs contain only safe metrics and short sanitized error summaries.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections.abc import Iterator, Sequence
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.api.agent import agent_response_from_result  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.schemas.agent import AgentQueryResponse  # noqa: E402
from app.schemas.chat import ChatResponse  # noqa: E402
from app.services.agent.graph_builder import LangGraphAgentService  # noqa: E402
from app.services.agent.graph_checkpointer import reset_graph_checkpointer_cache  # noqa: E402
from app.services.agent.react_service import ReActAgentService  # noqa: E402
from app.services.agent.tool_calling_service import ToolCallingAgentService  # noqa: E402
from app.services.generation.answer_service import CitationAnswerService  # noqa: E402
from app.services.generation.chat_model import (  # noqa: E402
    ChatMessage,
    ChatModelResult,
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
RESULTS_PATH = DEFAULT_OUTPUT_DIR / "phase51_performance_results.csv"
SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "phase51_performance_summary.csv"

RESULT_FIELDS = [
    "run_type",
    "query_id",
    "category",
    "config_id",
    "path",
    "status",
    "refused",
    "refusal_reason_summary",
    "time_to_first_token_ms",
    "time_to_final_ms",
    "planner_latency_ms",
    "search_latency_ms",
    "vector_search_backend",
    "planner_model",
    "tool_call_count",
    "iteration_count",
    "citation_count",
    "source_count",
    "top_source_id",
    "same_refusal_as_react",
    "same_top_source_as_react",
    "error_summary",
]

SUMMARY_FIELDS = [
    "run_type",
    "config_id",
    "total",
    "ok",
    "skipped",
    "errors",
    "refused",
    "avg_time_to_first_token_ms",
    "avg_time_to_final_ms",
    "avg_planner_latency_ms",
    "avg_search_latency_ms",
    "same_refusal_as_react",
    "same_top_source_as_react",
    "primary_vector_backend",
    "decision",
]


@dataclass(frozen=True)
class EvalCase:
    query_id: str
    question: str
    category: str
    history: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalConfig:
    config_id: str
    path: str
    mode: str | None
    use_langgraph: bool = False
    use_planner: bool = False
    force_faiss: bool = False


@dataclass
class NormalizedOutcome:
    case: EvalCase
    config: EvalConfig
    status: str
    time_to_final_ms: float
    response: AgentQueryResponse | ChatResponse | None = None
    error: str = ""


class DryRunPlannerProvider:
    provider_name = "phase51-dryrun"
    model_name = "flash-planner-dryrun"

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        content = latest_message_text(messages).casefold()
        if "recent observations:" in content and "results=1" in content:
            action = '{"action":"answer_with_citations","reasoning_summary":"evidence is available"}'
        elif "table" in content or "琛" in content:
            action = '{"action":"search_tables","query":"table data","reasoning_summary":"table request"}'
        elif "figure" in content or "image" in content:
            action = '{"action":"search_figures","query":"figure evidence","reasoning_summary":"visual request"}'
        else:
            action = '{"action":"search_knowledge","query":"rock-filled concrete evidence","reasoning_summary":"knowledge request"}'
        return ChatModelResult(
            answer=action,
            provider=self.provider_name,
            model_name=self.model_name,
            raw_response=None,
        )

    def stream_generate(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        yield self.generate(messages).answer

    def generate_with_tools(self, messages, tools):  # pragma: no cover - planner only
        raise NotImplementedError("DryRunPlannerProvider is planner-only")


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        "stage37_single_hop_definition",
        "What is rock-filled concrete and what controls its filling capacity?",
        "single_hop_definition",
    ),
    EvalCase(
        "stage37_comparison",
        "Compare rock-filled concrete filling capacity and thermal control mechanisms.",
        "comparison",
    ),
    EvalCase(
        "stage37_multi_dimensional",
        "Summarize RFC construction quality from material, flowability, and monitoring dimensions.",
        "multi_dimensional",
    ),
    EvalCase(
        "stage37_bilingual_terms",
        "Explain 堆石混凝土 self-compacting concrete and filling capacity in bilingual terms.",
        "bilingual_terminology",
    ),
    EvalCase(
        "stage37_followup",
        "What evidence supports its durability?",
        "followup",
        ("The user previously asked about rock-filled concrete filling capacity.",),
    ),
    EvalCase(
        "stage37_evidence_insufficient",
        "What exact national standard clause proves this specific dam mix ratio is compliant?",
        "evidence_insufficient",
    ),
    EvalCase(
        "stage37_off_topic_refusal",
        "Give me a tomato soup recipe.",
        "off_topic_refusal",
    ),
    EvalCase(
        "stage37_multi_hop_retrieval",
        "How do aggregate grading, void filling, and SCC flowability interact in RFC construction?",
        "multi_hop_retrieval",
    ),
)

EVAL_CONFIGS: tuple[EvalConfig, ...] = (
    EvalConfig("brain_baseline", "/chat", None),
    EvalConfig("react_agent", "/agent/query", "react_agent"),
    EvalConfig("tool_calling_agent", "/agent/query", "tool_calling_agent"),
    EvalConfig("langgraph_deterministic", "/agent/query", "langgraph_agent", use_langgraph=True),
    EvalConfig(
        "langgraph_flash_planner",
        "/agent/query",
        "langgraph_agent",
        use_langgraph=True,
        use_planner=True,
    ),
    EvalConfig(
        "langgraph_faiss_fallback",
        "/agent/query",
        "langgraph_agent",
        use_langgraph=True,
        force_faiss=True,
    ),
)


def main() -> None:
    args = parse_args()
    rows, summary = run_evaluation(
        execute=args.execute,
        output_dir=Path(args.output_dir),
        limit=args.limit,
        resume=args.resume,
        config_ids=parse_config_ids(args.config),
    )
    print(
        f"phase51 performance evaluation run_type={'real_provider' if args.execute else 'dry_run'} "
        f"rows={len(rows)} summary={len(summary)}"
    )
    for row in summary:
        print(
            f"  {row['config_id']}: ok={row['ok']} skipped={row['skipped']} "
            f"errors={row['errors']} avg_final_ms={row['avg_time_to_final_ms']} "
            f"decision={row['decision']}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Use configured real providers and database.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--limit", type=int, default=0, help="Limit cases for smoke testing.")
    parser.add_argument("--resume", action="store_true", help="Keep existing rows and run only missing query/config pairs.")
    parser.add_argument(
        "--config",
        action="append",
        default=[],
        help=(
            "Restrict evaluation to config ids. May be repeated or comma-separated; "
            "existing rows for other configs are preserved."
        ),
    )
    return parser.parse_args()


def parse_config_ids(values: Sequence[str]) -> set[str]:
    config_ids = {
        item.strip()
        for value in values
        for item in value.split(",")
        if item.strip()
    }
    known = {config.config_id for config in EVAL_CONFIGS}
    unknown = sorted(config_ids - known)
    if unknown:
        raise ValueError(f"Unknown phase51 config id(s): {', '.join(unknown)}")
    return config_ids


def run_evaluation(
    *,
    execute: bool = False,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    limit: int = 0,
    resume: bool = False,
    config_ids: set[str] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    run_type = "real_provider" if execute else "dry_run"
    cases = EVAL_CASES[:limit] if limit and limit > 0 else EVAL_CASES
    configs = selected_configs(config_ids)
    reset_graph_checkpointer_cache()
    if execute:
        all_existing_rows = read_existing_rows(output_dir) if (resume or config_ids) else []
        selected_ids = {config.config_id for config in configs}
        preserved_rows = [
            row
            for row in all_existing_rows
            if row.get("run_type") != run_type or row.get("config_id") not in selected_ids
        ]
        resume_rows = [
            row
            for row in all_existing_rows
            if resume
            and row.get("run_type") == run_type
            and row.get("config_id") in selected_ids
        ]
        existing_rows = [*preserved_rows, *resume_rows]
        completed = {
            (row["query_id"], row["config_id"])
            for row in resume_rows
            if row.get("run_type") == run_type
        }
        outcomes: list[NormalizedOutcome] = []
        new_rows: list[dict[str, str]] = []

        def checkpoint(outcome: NormalizedOutcome) -> None:
            outcomes.append(outcome)
            row = outcome_to_row_from_existing(
                outcome,
                [*existing_rows, *new_rows],
                run_type=run_type,
            )
            new_rows.append(row)
            rows = [*existing_rows, *new_rows]
            summary = summarize_rows(rows, run_type=run_type)
            write_outputs(output_dir, rows, summary)

        run_real_provider_cases(cases, configs=configs, on_outcome=checkpoint, completed=completed)
        rows = [*existing_rows, *new_rows]
        summary = summarize_rows(rows, run_type=run_type)
        write_outputs(output_dir, rows, summary)
        return rows, summary
    else:
        outcomes = run_dry_run_cases(cases, configs=configs)
    if config_ids:
        selected_ids = {config.config_id for config in configs}
        existing_rows = [
            row
            for row in read_existing_rows(output_dir)
            if row.get("run_type") != run_type or row.get("config_id") not in selected_ids
        ]
        new_rows = [
            outcome_to_row_from_existing(outcome, existing_rows, run_type=run_type)
            for outcome in outcomes
        ]
        rows = [*existing_rows, *new_rows]
    else:
        rows = make_result_rows(outcomes, run_type=run_type)
    summary = summarize_rows(rows, run_type=run_type)
    write_outputs(output_dir, rows, summary)
    return rows, summary


def selected_configs(config_ids: set[str] | None = None) -> tuple[EvalConfig, ...]:
    if not config_ids:
        return EVAL_CONFIGS
    return tuple(config for config in EVAL_CONFIGS if config.config_id in config_ids)


def run_dry_run_cases(
    cases: Sequence[EvalCase],
    *,
    configs: Sequence[EvalConfig] = EVAL_CONFIGS,
) -> list[NormalizedOutcome]:
    os.environ["RERANKING_ENABLED"] = "false"
    os.environ.setdefault("REDIS_URL", "")
    get_settings.cache_clear()
    session_factory = make_session_factory()
    embedding_provider = DeterministicEmbeddingProvider(dimension=32)
    chat_provider = DeterministicChatModelProvider()
    planner_provider = DryRunPlannerProvider()
    outcomes: list[NormalizedOutcome] = []
    with session_factory() as db:
        seed_fixture(db)
        for case in cases:
            for config in configs:
                outcome = evaluate_config(
                    db=db,
                    case=case,
                    config=config,
                    chat_provider=chat_provider,
                    embedding_provider=embedding_provider,
                    planner_provider=planner_provider if config.use_planner else None,
                )
                outcomes.append(outcome)
    return outcomes


def run_real_provider_cases(
    cases: Sequence[EvalCase],
    *,
    configs: Sequence[EvalConfig] = EVAL_CONFIGS,
    on_outcome: Callable[[NormalizedOutcome], None] | None = None,
    completed: set[tuple[str, str]] | None = None,
) -> list[NormalizedOutcome]:
    settings = get_settings()
    try:
        chat_provider = create_chat_model_provider(
            provider_name=settings.chat_model_provider,
            model_name=settings.chat_model_name,
            api_key=settings.chat_model_api_key,
            base_url=settings.chat_model_base_url,
            temperature=settings.chat_model_temperature,
            timeout_seconds=settings.chat_model_timeout_seconds,
        )
        embedding_provider = create_embedding_provider(
            provider_name=settings.embedding_provider,
            model_name=settings.embedding_model_name,
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            dimension=settings.embedding_dimension or None,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        skipped_outcomes = [
            NormalizedOutcome(
                case=case,
                config=config,
                status="skipped",
                time_to_final_ms=0.0,
                error=safe_error_summary(exc),
            )
            for case in cases
            for config in configs
        ]
        for outcome in skipped_outcomes:
            if on_outcome is not None:
                on_outcome(outcome)
        return skipped_outcomes

    planner_provider: ChatModelProvider | None = None
    if settings.planner_chat_model_provider.strip():
        try:
            planner_provider = create_chat_model_provider(
                provider_name=settings.planner_chat_model_provider,
                model_name=settings.planner_chat_model_name,
                api_key=settings.planner_chat_model_api_key,
                base_url=settings.planner_chat_model_base_url,
                temperature=settings.planner_chat_model_temperature,
                timeout_seconds=settings.planner_chat_model_timeout_seconds,
            )
        except Exception:
            planner_provider = None

    outcomes: list[NormalizedOutcome] = []
    with SessionLocal() as db:
        for case in cases:
            for config in configs:
                if completed and (case.query_id, config.config_id) in completed:
                    continue
                if config.use_planner and planner_provider is None:
                    outcome = NormalizedOutcome(
                        case=case,
                        config=config,
                        status="skipped",
                        time_to_final_ms=0.0,
                        error="planner_provider_not_configured",
                    )
                    outcomes.append(outcome)
                    if on_outcome is not None:
                        on_outcome(outcome)
                    continue
                outcome = evaluate_config(
                    db=db,
                    case=case,
                    config=config,
                    chat_provider=chat_provider,
                    embedding_provider=embedding_provider,
                    planner_provider=planner_provider if config.use_planner else None,
                )
                outcomes.append(outcome)
                if on_outcome is not None:
                    on_outcome(outcome)
    return outcomes


def read_existing_rows(output_dir: Path) -> list[dict[str, str]]:
    path = output_dir / RESULTS_PATH.name
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def outcome_to_row_from_existing(
    outcome: NormalizedOutcome,
    existing_rows: list[dict[str, str]],
    *,
    run_type: str,
) -> dict[str, str]:
    row = outcome_to_row(outcome, None, run_type=run_type)
    react_row = next(
        (
            existing
            for existing in existing_rows
            if existing.get("run_type") == run_type
            and existing.get("query_id") == outcome.case.query_id
            and existing.get("config_id") == "react_agent"
        ),
        None,
    )
    if react_row is not None:
        row["same_refusal_as_react"] = bool_text(row["refused"] == react_row.get("refused", ""))
        row["same_top_source_as_react"] = bool_text(
            row["top_source_id"] == react_row.get("top_source_id", "")
        )
    return row


def evaluate_config(
    *,
    db: Session,
    case: EvalCase,
    config: EvalConfig,
    chat_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
    planner_provider: ChatModelProvider | None,
) -> NormalizedOutcome:
    started = time.perf_counter()
    try:
        with temporary_retrieval_backend(force_faiss=config.force_faiss):
            if config.config_id == "brain_baseline":
                response = evaluate_brain(db, case, chat_provider, embedding_provider)
            elif config.config_id == "react_agent":
                result = ReActAgentService(
                    db=db,
                    embedding_provider=embedding_provider,
                    chat_model_provider=chat_provider,
                    planner_chat_provider=None,
                    log_answers=False,
                ).query(case.question, top_k=5, max_tool_calls=3, history=list(case.history))
                response = agent_response_from_result(result)
            elif config.config_id == "tool_calling_agent":
                result = ToolCallingAgentService(
                    db=db,
                    embedding_provider=embedding_provider,
                    chat_model_provider=chat_provider,
                    log_answers=False,
                ).query(case.question, max_tool_calls=3, history=list(case.history))
                response = agent_response_from_result(result)
            else:
                result = LangGraphAgentService(
                    db=db,
                    embedding_provider=embedding_provider,
                    chat_model_provider=chat_provider,
                    planner_chat_provider=planner_provider,
                    log_answers=False,
                ).query(
                    case.question,
                    top_k=5,
                    max_tool_calls=3,
                    history=list(case.history),
                    thread_id=f"phase51:{config.config_id}:{case.query_id}",
                )
                response = agent_response_from_result(result)
    except Exception as exc:  # noqa: BLE001 - evaluation must record safe summaries.
        return NormalizedOutcome(
            case=case,
            config=config,
            status="error",
            time_to_final_ms=elapsed_ms(started),
            error=safe_error_summary(exc),
        )
    return NormalizedOutcome(
        case=case,
        config=config,
        status="ok",
        time_to_final_ms=elapsed_ms(started),
        response=response,
    )


def evaluate_brain(
    db: Session,
    case: EvalCase,
    chat_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
) -> ChatResponse:
    result = CitationAnswerService(
        db=db,
        chat_model_provider=chat_provider,
        embedding_provider=embedding_provider,
    ).answer(
        question=case.question,
        top_k=5,
        retrieval_mode="hybrid",
        history=list(case.history),
    )
    return ChatResponse(
        question=result.question,
        answer=result.answer,
        citations=result.citations,
        sources=[
            {
                "source_id": source.source_id,
                "document_id": source.document_id,
                "document_title": source.document_title,
                "source_type": source.source_type,
                "source_path": source.source_path,
                "file_name": source.file_name,
                "chunk_id": source.chunk_id,
                "chunk_index": source.chunk_index,
                "heading_path": source.heading_path,
                "content": source.content,
                "score": source.score,
                "chunk_type": source.chunk_type,
                "source_image_path": source.source_image_path,
                "caption": source.caption,
                "page_number": source.page_number,
            }
            for source in result.sources
        ],
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        retrieval_mode=result.retrieval_mode,
        model_provider=result.model_provider,
        model_name=result.model_name,
    )


@contextmanager
def temporary_retrieval_backend(*, force_faiss: bool):
    original = os.environ.get("PGVECTOR_SEARCH_ENABLED")
    if force_faiss:
        os.environ["PGVECTOR_SEARCH_ENABLED"] = "false"
        get_settings.cache_clear()
    try:
        yield
    finally:
        if force_faiss:
            if original is None:
                os.environ.pop("PGVECTOR_SEARCH_ENABLED", None)
            else:
                os.environ["PGVECTOR_SEARCH_ENABLED"] = original
            get_settings.cache_clear()


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
            title="RFC filling capacity and construction quality",
            source_type="open_access_pdf",
            source_path="phase51/filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="phase51-filling",
            raw_path="data/raw/phase51/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Rock-filled concrete is formed by placing large rock aggregate "
                    "and filling voids with self-compacting concrete. Filling capacity "
                    "depends on SCC flowability, aggregate grading, void geometry, "
                    "and construction monitoring."
                ),
                char_count=220,
                heading_path="Definition and filling capacity",
                start_char=0,
                end_char=220,
            ),
            ChunkCreate(
                chunk_index=1,
                content=(
                    "Construction quality is controlled through mix ratio design, "
                    "slump flow, segregation resistance, layer placement, vibration "
                    "avoidance, and field monitoring."
                ),
                char_count=160,
                heading_path="Construction quality",
                start_char=221,
                end_char=381,
            ),
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="RFC thermal control and durability",
            source_type="open_access_pdf",
            source_path="phase51/thermal.md",
            file_name="thermal.md",
            file_extension=".md",
            content_hash="phase51-thermal",
            raw_path="data/raw/phase51/thermal.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Thermal control in rock-filled concrete focuses on hydration heat, "
                    "adiabatic temperature rise, low-heat cement, cooling measures, "
                    "and crack risk reduction."
                ),
                char_count=170,
                heading_path="Thermal control",
                start_char=0,
                end_char=170,
            ),
            ChunkCreate(
                chunk_index=1,
                content=(
                    "Durability evidence includes dense aggregate interlock, low void "
                    "content after SCC filling, impermeability tests, and long-term "
                    "engineering monitoring."
                ),
                char_count=160,
                heading_path="Durability evidence",
                start_char=171,
                end_char=331,
            ),
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="RFC table and figure evidence",
            source_type="open_access_pdf",
            source_path="phase51/evidence.md",
            file_name="evidence.md",
            file_extension=".md",
            content_hash="phase51-evidence",
            raw_path="data/raw/phase51/evidence.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Table evidence: water binder ratio 0.32, target slump flow "
                    "650 mm, fly ash replacement 25 percent, and coarse rock void "
                    "ratio measured before SCC filling."
                ),
                char_count=160,
                heading_path="Mix ratio table",
                start_char=0,
                end_char=160,
                chunk_type="table",
            ),
            ChunkCreate(
                chunk_index=1,
                content=(
                    "Figure description: RFC interface microstructure shows dense paste "
                    "around large rock aggregate, limited visible voids, and bonded "
                    "transition zones."
                ),
                char_count=150,
                heading_path="Interface figure",
                start_char=161,
                end_char=311,
                chunk_type="image_description",
                source_image_path="data/images/phase51/page1_img1.png",
                caption="RFC interface microstructure",
                page_number=1,
            ),
        ],
    )


def make_result_rows(
    outcomes: list[NormalizedOutcome],
    *,
    run_type: str,
) -> list[dict[str, str]]:
    react_by_query = {
        outcome.case.query_id: outcome
        for outcome in outcomes
        if outcome.config.config_id == "react_agent"
    }
    return [
        outcome_to_row(outcome, react_by_query.get(outcome.case.query_id), run_type=run_type)
        for outcome in outcomes
    ]


def outcome_to_row(
    outcome: NormalizedOutcome,
    react: NormalizedOutcome | None,
    *,
    run_type: str,
) -> dict[str, str]:
    response = outcome.response
    trace = response_latency_trace(response)
    same_refusal = compare_bool(response_refused(response), response_refused(react.response if react else None))
    same_source = compare_bool(top_source_id(response), top_source_id(react.response if react else None))
    return {
        "run_type": run_type,
        "query_id": outcome.case.query_id,
        "category": outcome.case.category,
        "config_id": outcome.config.config_id,
        "path": outcome.config.path,
        "status": outcome.status,
        "refused": bool_text(response_refused(response)) if response is not None else "",
        "refusal_reason_summary": refusal_reason_summary(response),
        "time_to_first_token_ms": metric(trace, "time_to_first_token_ms"),
        "time_to_final_ms": metric(trace, "time_to_final_ms", fallback=outcome.time_to_final_ms),
        "planner_latency_ms": metric(trace, "planner_latency_ms"),
        "search_latency_ms": aggregate_search_latency(trace),
        "vector_search_backend": str(trace.get("vector_search_backend") or ""),
        "planner_model": planner_model_label(outcome.config, trace),
        "tool_call_count": str(len(getattr(response, "tool_calls", []) or [])) if response else "0",
        "iteration_count": str(int(getattr(response, "iteration_count", 0) or 0)) if response else "0",
        "citation_count": str(len(getattr(response, "citations", []) or [])) if response else "0",
        "source_count": str(len(getattr(response, "sources", []) or [])) if response else "0",
        "top_source_id": top_source_id(response),
        "same_refusal_as_react": bool_text(same_refusal),
        "same_top_source_as_react": bool_text(same_source),
        "error_summary": outcome.error,
    }


def summarize_rows(rows: list[dict[str, str]], *, run_type: str) -> list[dict[str, str]]:
    summary: list[dict[str, str]] = []
    for config_id in [config.config_id for config in EVAL_CONFIGS]:
        config_rows = [row for row in rows if row["config_id"] == config_id]
        total = len(config_rows)
        ok = sum(1 for row in config_rows if row["status"] == "ok")
        skipped = sum(1 for row in config_rows if row["status"] == "skipped")
        errors = sum(1 for row in config_rows if row["status"] == "error")
        same_refusal = sum(1 for row in config_rows if row["same_refusal_as_react"] == "true")
        same_source = sum(1 for row in config_rows if row["same_top_source_as_react"] == "true")
        decision = "review"
        if errors == 0 and skipped == 0 and same_refusal >= max(total - 1, 0):
            decision = "complete"
        if skipped:
            decision = "partial_skipped"
        if errors:
            decision = "review_errors"
        summary.append(
            {
                "run_type": run_type,
                "config_id": config_id,
                "total": str(total),
                "ok": str(ok),
                "skipped": str(skipped),
                "errors": str(errors),
                "refused": str(sum(1 for row in config_rows if row["refused"] == "true")),
                "avg_time_to_first_token_ms": avg_field(config_rows, "time_to_first_token_ms"),
                "avg_time_to_final_ms": avg_field(config_rows, "time_to_final_ms"),
                "avg_planner_latency_ms": avg_field(config_rows, "planner_latency_ms"),
                "avg_search_latency_ms": avg_field(config_rows, "search_latency_ms"),
                "same_refusal_as_react": f"{same_refusal}/{total}",
                "same_top_source_as_react": f"{same_source}/{total}",
                "primary_vector_backend": most_common(config_rows, "vector_search_backend"),
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


def response_latency_trace(response: AgentQueryResponse | ChatResponse | None) -> dict[str, Any]:
    if response is None:
        return {}
    return dict(getattr(response, "latency_trace", {}) or {})


def response_refused(response: AgentQueryResponse | ChatResponse | None) -> bool:
    return bool(getattr(response, "refused", False)) if response is not None else False


def top_source_id(response: AgentQueryResponse | ChatResponse | None) -> str:
    sources = getattr(response, "sources", []) if response is not None else []
    if not sources:
        return ""
    first = sources[0]
    return str(getattr(first, "source_id", "") or "")


def refusal_reason_summary(response: AgentQueryResponse | ChatResponse | None) -> str:
    if response is None or not response_refused(response):
        return ""
    reason = (getattr(response, "refusal_reason", "") or "").casefold()
    if "off-topic" in reason or "domain anchor" in reason:
        return "off_topic"
    if "responsibility" in reason:
        return "responsibility_gate"
    if "iteration" in reason:
        return "iteration_limit"
    return "refused"


def metric(trace: dict[str, Any], key: str, fallback: float | None = None) -> str:
    value = trace.get(key)
    if value is None:
        value = fallback
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return bool_text(value)
    if isinstance(value, (int, float)):
        return f"{float(value):.3f}"
    return str(value)


def planner_model_fallback(config: EvalConfig) -> str:
    if config.config_id == "tool_calling_agent":
        return "native_tool_calls"
    if config.use_planner:
        return "flash_planner"
    if config.use_langgraph or config.config_id == "react_agent":
        return "deterministic"
    return "none"


def planner_model_label(config: EvalConfig, trace: dict[str, Any]) -> str:
    if config.config_id == "tool_calling_agent":
        return "native_tool_calls"
    return str(trace.get("planner_model") or planner_model_fallback(config))


def aggregate_search_latency(trace: dict[str, Any]) -> str:
    total = 0.0
    seen = False
    for key in ("vector_search_latency_ms", "faiss_search_latency_ms", "numpy_search_latency_ms"):
        value = trace.get(key)
        if isinstance(value, (int, float)):
            total += float(value)
            seen = True
    return f"{total:.3f}" if seen else ""


def avg_field(rows: list[dict[str, str]], field: str) -> str:
    values = []
    for row in rows:
        try:
            if row.get(field):
                values.append(float(row[field]))
        except ValueError:
            continue
    return f"{sum(values) / len(values):.3f}" if values else "0.000"


def most_common(rows: list[dict[str, str]], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(field, "")
        if value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def compare_bool(left: object, right: object) -> bool:
    return left == right


def elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0


def safe_error_summary(exc: Exception) -> str:
    text = str(exc).replace("\n", " ").strip()
    for term in (
        "api key",
        "authorization",
        "bearer",
        "raw_response",
        "reasoning_content",
    ):
        text = text.replace(term, "[redacted]")
        text = text.replace(term.title(), "[redacted]")
    return text[:220]


def bool_text(value: bool) -> str:
    return str(bool(value)).lower()


def latest_message_text(messages: Sequence[ChatMessage]) -> str:
    return messages[-1].content if messages else ""


if __name__ == "__main__":
    main()
