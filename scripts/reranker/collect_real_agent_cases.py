from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.repositories import QuestionAnswerLogCreate, QuestionAnswerLogRepository  # noqa: E402
from app.db.session import create_database_engine  # noqa: E402
from app.services.agent.react_service import ReActAgentService  # noqa: E402
from app.services.agent.service import AgentQueryResult, AgentService  # noqa: E402
from app.services.agent.tool_calling_service import ToolCallingAgentService  # noqa: E402
from app.services.generation.chat_model import create_chat_model_provider  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from scripts.reranker.export_training_pairs import DEFAULT_OUTPUT_DIR, normalize_text  # noqa: E402

AgentMode = Literal["tool_calling_agent", "react_agent", "default"]
DEFAULT_EVAL_QUERIES = DEFAULT_OUTPUT_DIR / "eval_queries.jsonl"
DEFAULT_OUTPUT = DEFAULT_OUTPUT_DIR / "real_agent_cases.jsonl"

TARGET_CATEGORIES: tuple[str, ...] = (
    "construction",
    "filling",
    "hydration_heat",
    "mechanics",
    "crack",
    "case",
    "refusal",
)
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "construction": (
        "construction",
        "placement",
        "compaction",
        "\u65bd\u5de5",
        "\u6d47\u7b51",
        "\u8d28\u91cf\u63a7\u5236",
        "\u7b51\u575d",
    ),
    "filling": (
        "filling",
        "flowability",
        "aggregate grading",
        "void",
        "\u586b\u5145",
        "\u6d41\u52a8\u6027",
        "\u7ea7\u914d",
        "\u7a7a\u9699",
    ),
    "hydration_heat": (
        "hydration",
        "temperature",
        "thermal",
        "cooling",
        "\u6c34\u5316\u70ed",
        "\u6e29\u63a7",
        "\u6e29\u5ea6",
        "\u51b7\u5374",
    ),
    "mechanics": (
        "mechanical",
        "strength",
        "modulus",
        "stress",
        "peridynamics",
        "\u5f3a\u5ea6",
        "\u6a21\u91cf",
        "\u5e94\u529b",
        "\u529b\u5b66",
    ),
    "crack": (
        "crack",
        "cracking",
        "shrinkage",
        "fracture",
        "\u88c2\u7f1d",
        "\u88c2\u7eb9",
        "\u65ad\u88c2",
        "\u9632\u88c2",
    ),
    "case": (
        "case",
        "project",
        "application",
        "engineering",
        "\u5de5\u7a0b\u6848\u4f8b",
        "\u5e94\u7528",
        "\u793a\u4f8b",
    ),
    "refusal": (
        "refusal",
        "out_of_scope",
        "boundary",
        "\u7b7e\u5b57",
        "\u5ba1\u6838",
        "\u8d23\u4efb\u8fb9\u754c",
        "lunar",
        "moon",
    ),
}
PASSTHROUGH_CATEGORIES: dict[str, str] = {
    "refusal": "refusal",
    "multi_turn_refusal": "refusal",
    "new_cn_dam": "case",
    "new_cn_rfc": "case",
    "new_en_rfc": "case",
    "web": "case",
    "wikipedia": "case",
    "topic_switch": "case",
    "follow_up": "case",
    "constrained_follow_up": "case",
    "pronoun_ellipsis": "case",
    "clarification": "case",
    "user_correction": "case",
    "reference_previous_turn": "case",
}


@dataclass(frozen=True)
class RealAgentCase:
    query_id: str
    question: str
    category: str
    mode: str
    status: str
    refused: bool
    citation_count: int
    source_count: int
    qa_log_written: bool
    qa_log_id: int | None = None
    error_summary: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect real Agent cases for RFC reranker training.")
    parser.add_argument("--eval-queries", type=Path, default=DEFAULT_EVAL_QUERIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--database-url", default="")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--mode", choices=["tool_calling_agent", "react_agent", "default"], default="tool_calling_agent")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--max-tool-calls", type=int, default=3)
    parser.add_argument("--execute", action="store_true", help="Call the configured real providers.")
    parser.add_argument("--log-answers", action="store_true", help="Persist answers to qa_logs; requires --execute.")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.log_answers and not args.execute:
        raise SystemExit("--log-answers requires --execute")
    cases = collect_real_agent_cases(
        eval_queries_path=args.eval_queries,
        output_path=args.output,
        database_url=args.database_url,
        limit=args.limit,
        mode=args.mode,
        top_k=args.top_k,
        max_tool_calls=args.max_tool_calls,
        execute=args.execute,
        log_answers=args.log_answers,
        resume=args.resume,
    )
    print(
        f"real_agent_cases execute={args.execute} log_answers={args.log_answers} "
        f"rows={len(cases)} output={args.output}"
    )


def collect_real_agent_cases(
    *,
    eval_queries_path: Path,
    output_path: Path,
    database_url: str = "",
    limit: int = 50,
    mode: AgentMode = "tool_calling_agent",
    top_k: int = 6,
    max_tool_calls: int = 3,
    execute: bool = False,
    log_answers: bool = False,
    resume: bool = False,
) -> list[RealAgentCase]:
    if log_answers and not execute:
        raise ValueError("log_answers requires execute=True")
    queries = select_balanced_queries(read_jsonl(eval_queries_path), limit=limit)
    existing_ids = existing_query_ids(output_path) if resume else set()
    queries = [query for query in queries if str(query.get("query_id", "")) not in existing_ids]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode_flag = "a" if resume and output_path.exists() else "w"
    cases: list[RealAgentCase] = []
    with output_path.open(mode_flag, encoding="utf-8", newline="\n") as handle:
        if not execute:
            for query in queries:
                case = RealAgentCase(
                    query_id=str(query.get("query_id", "")),
                    question=str(query.get("question", "")),
                    category=str(query.get("category", "")),
                    mode=mode,
                    status="dry_run",
                    refused=False,
                    citation_count=0,
                    source_count=0,
                    qa_log_written=False,
                )
                cases.append(case)
                handle.write(json.dumps(asdict(case), ensure_ascii=False, separators=(",", ":")) + "\n")
            return cases

        settings = get_settings()
        engine = create_database_engine(database_url or settings.database_url)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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
        with session_local() as db:
            for query in queries:
                question = str(query.get("question", "")).strip()
                try:
                    result = run_agent_case(
                        db=db,
                        mode=mode,
                        question=question,
                        top_k=top_k,
                        max_tool_calls=max_tool_calls,
                        chat_provider=chat_provider,
                        embedding_provider=embedding_provider,
                    )
                    qa_log_id = None
                    if log_answers:
                        qa_log = QuestionAnswerLogRepository(db).save_log(
                            QuestionAnswerLogCreate(
                                question=result.question,
                                answer=result.answer,
                                retrieved_chunk_ids=[source.chunk_id for source in result.sources],
                                citations=result.citations,
                                model_provider=chat_provider.provider_name,
                                model_name=chat_provider.model_name,
                                retrieval_mode=mode,
                                refused=result.refused,
                                refusal_reason=result.refusal_reason,
                            )
                        )
                        qa_log_id = qa_log.id
                    case = RealAgentCase(
                        query_id=str(query.get("query_id", "")),
                        question=question,
                        category=str(query.get("category", "")),
                        mode=mode,
                        status="completed",
                        refused=result.refused,
                        citation_count=len(result.citations),
                        source_count=len(result.sources),
                        qa_log_written=bool(log_answers),
                        qa_log_id=qa_log_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    case = RealAgentCase(
                        query_id=str(query.get("query_id", "")),
                        question=question,
                        category=str(query.get("category", "")),
                        mode=mode,
                        status="error",
                        refused=False,
                        citation_count=0,
                        source_count=0,
                        qa_log_written=False,
                        error_summary=type(exc).__name__,
                    )
                cases.append(case)
                handle.write(json.dumps(asdict(case), ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
    return cases


def run_agent_case(
    *,
    db,
    mode: AgentMode,
    question: str,
    top_k: int,
    max_tool_calls: int,
    chat_provider,
    embedding_provider,
) -> AgentQueryResult:
    if mode == "tool_calling_agent":
        return ToolCallingAgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_provider,
            log_answers=False,
        ).query(question, max_tool_calls=max_tool_calls)
    if mode == "react_agent":
        return ReActAgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_provider,
            log_answers=False,
        ).query(question, top_k=top_k, max_tool_calls=max_tool_calls)
    return AgentService(
        db=db,
        embedding_provider=embedding_provider,
        chat_model_provider=chat_provider,
        log_answers=False,
    ).query(question, top_k=top_k, max_tool_calls=max_tool_calls)


def select_balanced_queries(rows: list[dict[str, object]], *, limit: int) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    seen_questions: set[str] = set()
    classified_rows = [{**row, "category": infer_category(row)} for row in rows]
    for category in TARGET_CATEGORIES:
        for row in classified_rows:
            question = normalize_text(str(row.get("question", "")))
            if not question or question in seen_questions:
                continue
            if row.get("category") == category:
                selected.append(row)
                seen_questions.add(question)
                break
    for row in classified_rows:
        if len(selected) >= limit:
            break
        question = normalize_text(str(row.get("question", "")))
        if question and question not in seen_questions:
            selected.append(row)
            seen_questions.add(question)
    return selected[: max(limit, 0)]


def infer_category(row: dict[str, object]) -> str:
    category = str(row.get("category", "") or "").strip().casefold()
    expected_refused = str(row.get("expected_refused", "") or "").strip().casefold()
    if expected_refused in {"true", "yes", "1"}:
        return "refusal"
    if category in TARGET_CATEGORIES:
        return category
    haystack = " ".join(
        normalize_text(str(row.get(key, "") or ""))
        for key in ("query_id", "question", "expected_source_terms", "source_file")
    ).casefold()
    crack_strong_signals = (
        "crack",
        "cracking",
        "fracture",
        "\u88c2\u7f1d",
        "\u88c2\u7eb9",
        "\u65ad\u88c2",
    )
    if any(signal in haystack for signal in crack_strong_signals):
        return "crack"
    for target in TARGET_CATEGORIES:
        if any(keyword.casefold() in haystack for keyword in CATEGORY_KEYWORDS[target]):
            return target
    if category in PASSTHROUGH_CATEGORIES:
        return PASSTHROUGH_CATEGORIES[category]
    return category


def existing_query_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {str(row.get("query_id", "")) for row in read_jsonl(path)}


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
