from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.agent.service import AgentService  # noqa: E402
from app.services.generation.answer_service import CitationAnswerService  # noqa: E402
from app.services.generation.chat_model import create_chat_model_provider  # noqa: E402
from app.services.generation.outline_first_strategy import generate_outline_first_answer  # noqa: E402
from app.services.generation.prompt_builder import build_rag_prompt  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from scripts.judge_stage34_generation_quality import (  # noqa: E402
    OpenAICompatibleStage34JudgeClient,
    parse_judge_payload,
    sanitize_text,
    source_summary,
)


RESULTS_PATH = ROOT / "data" / "evaluation" / "stage36_judge_strategy_ab_results.csv"
SUMMARY_PATH = ROOT / "data" / "evaluation" / "stage36_judge_strategy_ab_summary.csv"
DECISION_PATH = ROOT / "docs" / "stage36_judge_strategy_decision.md"
STAGE29_QUERIES = ROOT / "data" / "evaluation" / "stage29_new_corpus_queries.csv"
USER_QUERIES = ROOT / "data" / "evaluation" / "user_questions.csv"
STAGE18_QUERIES = ROOT / "data" / "evaluation" / "stage18_hard_queries.csv"

STRATEGIES = ("baseline", "outline_first", "answer_provider_ab")

RESULT_FIELDS = [
    "run_at",
    "query_id",
    "strategy",
    "status",
    "question",
    "expected_refused",
    "answer_provider",
    "answer_model",
    "judge_provider",
    "judge_model",
    "refused",
    "citation_count",
    "source_count",
    "faithfulness",
    "answer_coverage",
    "citation_support",
    "refusal_correctness",
    "conciseness",
    "safety_leak_check",
    "risk_level",
    "short_reason",
    "next_action",
    "error",
]

SUMMARY_FIELDS = [
    "strategy",
    "status",
    "total_rows",
    "completed_rows",
    "avg_answer_coverage",
    "avg_citation_support",
    "avg_safety_leak_check",
    "high_risk_count",
    "medium_risk_count",
    "judge_gate",
    "decision",
]


@dataclass(frozen=True)
class Stage36JudgeQuery:
    query_id: str
    question: str
    expected_refused: bool
    expected_answer_points: tuple[str, ...]
    category: str


@dataclass(frozen=True)
class StrategyAnswer:
    answer: str
    provider: str
    model_name: str
    citations: list[int]
    sources: list[Any]
    refused: bool
    refusal_reason: str | None


def main() -> None:
    args = parse_args()
    apply_runtime_fallbacks(args)
    queries = load_stage36_queries(limit=args.limit)
    rows = build_rows(args, queries)
    summary = summarize(rows)
    write_csv(Path(args.out_results), RESULT_FIELDS, rows)
    write_csv(Path(args.out_summary), SUMMARY_FIELDS, summary)
    write_decision_report(Path(args.out_decision), summary, rows, execute=args.execute)
    print(
        f"stage36 judge strategy rows={len(rows)} queries={len(queries)} "
        f"execute={str(args.execute).lower()}"
    )
    print(f"wrote {args.out_results}")
    print(f"wrote {args.out_summary}")
    print(f"wrote {args.out_decision}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 36 offline Judge strategy A/B.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--out-results", default=str(RESULTS_PATH))
    parser.add_argument("--out-summary", default=str(SUMMARY_PATH))
    parser.add_argument("--out-decision", default=str(DECISION_PATH))
    parser.add_argument("--judge-provider", default=env_value("STAGE36_JUDGE_PROVIDER") or env_value("STAGE34_JUDGE_PROVIDER"))
    parser.add_argument("--judge-model", default=env_value("STAGE36_JUDGE_MODEL") or env_value("STAGE34_JUDGE_MODEL"))
    parser.add_argument("--judge-base-url", default=env_value("STAGE36_JUDGE_BASE_URL") or env_value("STAGE34_JUDGE_BASE_URL"))
    parser.add_argument("--judge-api-key", default=env_value("STAGE36_JUDGE_API_KEY") or env_value("STAGE34_JUDGE_API_KEY"))
    parser.add_argument("--ab-answer-provider", default=env_value("STAGE36_AB_ANSWER_PROVIDER"))
    parser.add_argument("--ab-answer-model", default=env_value("STAGE36_AB_ANSWER_MODEL") or "DeepSeek-V3.2-Thinking")
    parser.add_argument("--ab-answer-base-url", default=env_value("STAGE36_AB_ANSWER_BASE_URL"))
    parser.add_argument("--ab-answer-api-key", default=env_value("STAGE36_AB_ANSWER_API_KEY"))
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    return parser.parse_args()


def apply_runtime_fallbacks(args: argparse.Namespace) -> None:
    settings = get_settings()
    if not args.judge_provider:
        args.judge_provider = settings.chat_model_provider
    if not args.judge_model:
        args.judge_model = settings.chat_model_name
    if not args.judge_base_url:
        args.judge_base_url = settings.chat_model_base_url
    if not args.judge_api_key:
        args.judge_api_key = settings.chat_model_api_key
    if not args.ab_answer_provider:
        args.ab_answer_provider = settings.chat_model_provider
    if not args.ab_answer_base_url:
        args.ab_answer_base_url = settings.chat_model_base_url
    if not args.ab_answer_api_key:
        args.ab_answer_api_key = settings.chat_model_api_key


def build_rows(args: argparse.Namespace, queries: Sequence[Stage36JudgeQuery]) -> list[dict[str, str]]:
    run_at = datetime.now(timezone.utc).isoformat()
    if not args.execute:
        return [
            dry_run_row(run_at, query, strategy, args)
            for query in queries
            for strategy in STRATEGIES
        ]
    if missing_judge_config(args):
        return [
            skipped_row(run_at, query, strategy, args, "missing_judge_configuration")
            for query in queries
            for strategy in STRATEGIES
        ]

    try:
        answers = build_strategy_answers(args, queries)
    except Exception as exc:  # noqa: BLE001
        return [
            skipped_row(run_at, query, strategy, args, sanitize_text(str(exc), limit=160))
            for query in queries
            for strategy in STRATEGIES
        ]

    judge = OpenAICompatibleStage34JudgeClient(
        provider=args.judge_provider or "not_configured",
        model=args.judge_model or "not_configured",
        api_key=args.judge_api_key,
        base_url=args.judge_base_url,
        timeout_seconds=args.timeout_seconds,
    )
    rows: list[dict[str, str]] = []
    for query in queries:
        for strategy in STRATEGIES:
            answer = answers[(query.query_id, strategy)]
            payload = judge_payload(query, answer, strategy)
            try:
                judged = judge.judge(payload)
                rows.append(completed_row(run_at, query, strategy, args, answer, judged))
            except Exception as exc:  # noqa: BLE001
                rows.append(error_row(run_at, query, strategy, args, answer, exc))
    return rows


def build_strategy_answers(
    args: argparse.Namespace,
    queries: Sequence[Stage36JudgeQuery],
) -> dict[tuple[str, str], StrategyAnswer]:
    settings = get_settings()
    init_db()
    default_chat = create_chat_model_provider(
        provider_name=settings.chat_model_provider,
        model_name=settings.chat_model_name,
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=args.timeout_seconds,
    )
    embedding = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension or None,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    ab_chat = create_chat_model_provider(
        provider_name=args.ab_answer_provider or settings.chat_model_provider,
        model_name=args.ab_answer_model or settings.chat_model_name,
        api_key=args.ab_answer_api_key or settings.chat_model_api_key,
        base_url=args.ab_answer_base_url or settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=args.timeout_seconds,
    )
    answers: dict[tuple[str, str], StrategyAnswer] = {}
    with SessionLocal() as db:
        baseline_service = AgentService(
            db=db,
            chat_model_provider=default_chat,
            embedding_provider=embedding,
            log_answers=False,
        )
        answer_service = CitationAnswerService(
            db=db,
            chat_model_provider=default_chat,
            embedding_provider=embedding,
            log_answers=False,
        )
        for query in queries:
            baseline = baseline_service.query(query.question, top_k=5, max_tool_calls=3)
            answers[(query.query_id, "baseline")] = StrategyAnswer(
                answer=baseline.answer,
                provider=default_chat.provider_name,
                model_name=default_chat.model_name,
                citations=baseline.citations,
                sources=baseline.sources,
                refused=baseline.refused,
                refusal_reason=baseline.refusal_reason,
            )
            retrieval = answer_service.retrieve(
                question=query.question,
                top_k=5,
                retrieval_mode="hybrid",
                min_score=0.0,
            )
            if not retrieval.results:
                empty = StrategyAnswer(
                    answer="当前资料库中没有找到足够可靠的依据。",
                    provider=default_chat.provider_name,
                    model_name=default_chat.model_name,
                    citations=[],
                    sources=[],
                    refused=True,
                    refusal_reason=retrieval.refusal_reason,
                )
                answers[(query.query_id, "outline_first")] = empty
                answers[(query.query_id, "answer_provider_ab")] = empty
                continue
            rag_prompt = build_rag_prompt(query.question, retrieval.results)
            outline = generate_outline_first_answer(
                question=query.question,
                sources=rag_prompt.sources,
                chat_model_provider=default_chat,
            )
            answers[(query.query_id, "outline_first")] = StrategyAnswer(
                answer=outline.answer,
                provider=outline.provider,
                model_name=outline.model_name,
                citations=outline.citations,
                sources=list(rag_prompt.sources),
                refused=False,
                refusal_reason=None,
            )
            ab_result = ab_chat.generate(rag_prompt.messages)
            from app.services.brain.workflow import extract_citations  # local to keep import narrow

            answers[(query.query_id, "answer_provider_ab")] = StrategyAnswer(
                answer=ab_result.answer,
                provider=ab_result.provider,
                model_name=ab_result.model_name,
                citations=extract_citations(
                    ab_result.answer,
                    [source.source_id for source in rag_prompt.sources],
                ),
                sources=list(rag_prompt.sources),
                refused=False,
                refusal_reason=None,
            )
    return answers


def judge_payload(
    query: Stage36JudgeQuery,
    answer: StrategyAnswer,
    strategy: str,
) -> dict[str, object]:
    return {
        "query_id": query.query_id,
        "strategy": strategy,
        "question": truncate_text(query.question, 240),
        "expected_refused": query.expected_refused,
        "expected_answer_points": list(query.expected_answer_points[:8]),
        "answer_summary": sanitize_text(answer.answer, limit=700),
        "citation_count": len(answer.citations),
        "source_summaries": [source_summary(source) for source in answer.sources[:5]],
        "refused": answer.refused,
        "refusal_reason": sanitize_text(answer.refusal_reason or "", limit=160),
    }


def load_stage36_queries(limit: int = 20) -> list[Stage36JudgeQuery]:
    queries: list[Stage36JudgeQuery] = []
    queries.extend(load_stage29_queries(STAGE29_QUERIES))
    queries.extend(load_user_queries(USER_QUERIES))
    queries.extend(load_stage18_queries(STAGE18_QUERIES))
    deduped: list[Stage36JudgeQuery] = []
    seen: set[str] = set()
    for query in queries:
        if query.query_id in seen:
            continue
        seen.add(query.query_id)
        deduped.append(query)
        if len(deduped) >= limit:
            break
    return deduped


def load_stage29_queries(path: Path) -> list[Stage36JudgeQuery]:
    rows = read_csv(path)
    return [
        Stage36JudgeQuery(
            query_id=row["query_id"],
            question=row["question"],
            expected_refused=parse_bool(row.get("expected_refused", "")),
            expected_answer_points=split_points(row.get("expected_answer_points", "")),
            category=row.get("category", "stage29"),
        )
        for row in rows
    ]


def load_user_queries(path: Path) -> list[Stage36JudgeQuery]:
    rows = read_csv(path)
    return [
        Stage36JudgeQuery(
            query_id=row["query_id"],
            question=row["question"],
            expected_refused=parse_bool(row.get("expected_refused", "")),
            expected_answer_points=split_points(row.get("expected_answer_points", "")),
            category=row.get("language_type", "user_question"),
        )
        for row in rows
    ]


def load_stage18_queries(path: Path) -> list[Stage36JudgeQuery]:
    rows = read_csv(path)
    return [
        Stage36JudgeQuery(
            query_id=row["query_id"],
            question=row["query"],
            expected_refused=parse_bool(row.get("expected_refused", "")),
            expected_answer_points=split_points(row.get("expected_answer_points", "")),
            category=row.get("difficulty_type", "stage18"),
        )
        for row in rows
    ]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_bool(value: str) -> bool:
    return value.strip().casefold() in {"true", "yes", "1"}


def split_points(value: str) -> tuple[str, ...]:
    return tuple(point.strip() for point in re_split_points(value) if point.strip())


def re_split_points(value: str) -> list[str]:
    import re

    return re.split(r"[;|]", value or "")


def dry_run_row(
    run_at: str,
    query: Stage36JudgeQuery,
    strategy: str,
    args: argparse.Namespace,
) -> dict[str, str]:
    return base_row(
        run_at=run_at,
        query=query,
        strategy=strategy,
        args=args,
        status="dry_run",
        answer_provider=strategy_provider(strategy, args),
        answer_model=strategy_model(strategy, args),
        error="Run with --execute for real offline Judge A/B.",
    )


def skipped_row(
    run_at: str,
    query: Stage36JudgeQuery,
    strategy: str,
    args: argparse.Namespace,
    error: str,
) -> dict[str, str]:
    return base_row(
        run_at=run_at,
        query=query,
        strategy=strategy,
        args=args,
        status="skipped",
        answer_provider=strategy_provider(strategy, args),
        answer_model=strategy_model(strategy, args),
        error=error,
    )


def completed_row(
    run_at: str,
    query: Stage36JudgeQuery,
    strategy: str,
    args: argparse.Namespace,
    answer: StrategyAnswer,
    judged: Mapping[str, str],
) -> dict[str, str]:
    row = base_row(
        run_at=run_at,
        query=query,
        strategy=strategy,
        args=args,
        status="completed",
        answer_provider=answer.provider,
        answer_model=answer.model_name,
        refused=str(answer.refused).lower(),
        citation_count=str(len(answer.citations)),
        source_count=str(len(answer.sources)),
    )
    for key in [
        "faithfulness",
        "answer_coverage",
        "citation_support",
        "refusal_correctness",
        "conciseness",
        "safety_leak_check",
        "risk_level",
        "short_reason",
        "next_action",
    ]:
        row[key] = sanitize_text(str(judged.get(key, "")), limit=300)
    return row


def error_row(
    run_at: str,
    query: Stage36JudgeQuery,
    strategy: str,
    args: argparse.Namespace,
    answer: StrategyAnswer,
    exc: Exception,
) -> dict[str, str]:
    return base_row(
        run_at=run_at,
        query=query,
        strategy=strategy,
        args=args,
        status="error",
        answer_provider=answer.provider,
        answer_model=answer.model_name,
        refused=str(answer.refused).lower(),
        citation_count=str(len(answer.citations)),
        source_count=str(len(answer.sources)),
        error=sanitize_text(str(exc), limit=240),
    )


def base_row(
    *,
    run_at: str,
    query: Stage36JudgeQuery,
    strategy: str,
    args: argparse.Namespace,
    status: str,
    answer_provider: str,
    answer_model: str,
    refused: str = "",
    citation_count: str = "",
    source_count: str = "",
    error: str = "",
) -> dict[str, str]:
    return {
        "run_at": run_at,
        "query_id": query.query_id,
        "strategy": strategy,
        "status": status,
        "question": truncate_text(query.question, 160),
        "expected_refused": str(query.expected_refused).lower(),
        "answer_provider": answer_provider or "not_configured",
        "answer_model": answer_model or "not_configured",
        "judge_provider": args.judge_provider or "not_configured",
        "judge_model": args.judge_model or "not_configured",
        "refused": refused,
        "citation_count": citation_count,
        "source_count": source_count,
        "faithfulness": "",
        "answer_coverage": "",
        "citation_support": "",
        "refusal_correctness": "",
        "conciseness": "",
        "safety_leak_check": "",
        "risk_level": "",
        "short_reason": "",
        "next_action": "",
        "error": sanitize_text(error, limit=240),
    }


def summarize(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    for strategy in STRATEGIES:
        strategy_rows = [row for row in rows if row["strategy"] == strategy]
        completed = [row for row in strategy_rows if row["status"] == "completed"]
        avg_cov = average_score(completed, "answer_coverage")
        avg_cit = average_score(completed, "citation_support")
        avg_safety = average_score(completed, "safety_leak_check")
        high = sum(1 for row in completed if row.get("risk_level") == "high")
        medium = sum(1 for row in completed if row.get("risk_level") == "medium")
        gate = judge_gate(avg_cov, avg_cit, avg_safety, high, completed)
        summaries.append(
            {
                "strategy": strategy,
                "status": "completed" if completed else (strategy_rows[0]["status"] if strategy_rows else "empty"),
                "total_rows": str(len(strategy_rows)),
                "completed_rows": str(len(completed)),
                "avg_answer_coverage": avg_cov,
                "avg_citation_support": avg_cit,
                "avg_safety_leak_check": avg_safety,
                "high_risk_count": str(high),
                "medium_risk_count": str(medium),
                "judge_gate": gate,
                "decision": decision_for_gate(gate),
            }
        )
    return summaries


def average_score(rows: Sequence[dict[str, str]], field: str) -> str:
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(row.get(field, "")))
        except ValueError:
            continue
    if not values:
        return ""
    return f"{sum(values) / len(values):.3f}"


def judge_gate(
    avg_cov: str,
    avg_cit: str,
    avg_safety: str,
    high: int,
    completed: Sequence[dict[str, str]],
) -> str:
    if not completed:
        return "not_run"
    try:
        passed = float(avg_cov) >= 0.8 and float(avg_cit) >= 0.8 and float(avg_safety) >= 0.8
    except ValueError:
        return "review_required"
    if high:
        return "blocked"
    return "pass" if passed else "review_required"


def decision_for_gate(gate: str) -> str:
    if gate == "pass":
        return "candidate_for_human_review_before_production"
    if gate == "not_run":
        return "run_with_execute_before_claiming_judge_result"
    return "do_not_package_as_pass; document_root_cause"


def write_decision_report(
    path: Path,
    summary: Sequence[dict[str, str]],
    rows: Sequence[dict[str, str]],
    *,
    execute: bool,
) -> None:
    completed = sum(1 for row in rows if row["status"] == "completed")
    query_count = len({row["query_id"] for row in rows})
    lines = [
        "# 阶段 36 Judge 策略 A/B 决策草稿",
        "",
        f"- execute: `{str(execute).lower()}`",
        f"- queries: `{query_count}`",
        f"- completed_rows: `{completed}`",
        "",
        "## Summary",
        "",
        "| strategy | completed | cov | cit | safety | gate | decision |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in summary:
        lines.append(
            "| {strategy} | {completed_rows} | {avg_answer_coverage} | "
            "{avg_citation_support} | {avg_safety_leak_check} | {judge_gate} | {decision} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            "This file is a draft. A production change is not authorized by this report alone. "
            "If no strategy reaches the gate on at least 20 real judged queries, Phase 36 must "
            "document the failure honestly and keep the production Brain path unchanged.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def missing_judge_config(args: argparse.Namespace) -> bool:
    return not (args.judge_api_key and args.judge_base_url and args.judge_model)


def strategy_provider(strategy: str, args: argparse.Namespace) -> str:
    if strategy == "answer_provider_ab":
        return args.ab_answer_provider or "default_provider"
    return "default_provider"


def strategy_model(strategy: str, args: argparse.Namespace) -> str:
    if strategy == "answer_provider_ab":
        return args.ab_answer_model or "DeepSeek-V3.2-Thinking"
    return "default_model"


def truncate_text(value: str, limit: int) -> str:
    normalized = " ".join((value or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def env_value(name: str, *, env_file: Path = ROOT / ".env") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    if not env_file.exists():
        return ""
    prefix = f"{name}="
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        value = stripped[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value.startswith(("'", '"')):
            return value[1:-1].strip()
        return value
    return ""


if __name__ == "__main__":
    main()
