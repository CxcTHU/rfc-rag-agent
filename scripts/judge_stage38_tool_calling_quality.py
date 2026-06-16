"""Stage 38 real Judge A/B for default tool-calling final answers.

This script compares the current ``baseline`` tool-calling prompt with the
``structured_final_answer`` strategy on the expanded Stage 38 evaluation set.
It defaults to dry-run. Real provider and Judge calls require ``--execute``.
"""

from __future__ import annotations

import argparse
import csv
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
from app.services.agent.service import AgentQueryResult  # noqa: E402
from app.services.agent.tool_calling_service import (  # noqa: E402
    ToolCallingAgentService,
    ToolCallingFinalAnswerStrategy,
)
from app.services.generation.chat_model import create_chat_model_provider  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from scripts.evaluate_stage37_tool_calling_vs_react import build_planner_provider  # noqa: E402
from scripts.evaluate_stage38_tool_calling_quality import EVAL_CASES  # noqa: E402
from scripts.judge_stage34_generation_quality import (  # noqa: E402
    OpenAICompatibleStage34JudgeClient,
    parse_judge_payload,
    sanitize_text,
    source_summary,
)


RESULTS_PATH = ROOT / "data" / "evaluation" / "stage38_tool_calling_judge_results.csv"
SUMMARY_PATH = ROOT / "data" / "evaluation" / "stage38_tool_calling_judge_summary.csv"

STRATEGIES: tuple[ToolCallingFinalAnswerStrategy, ...] = (
    "baseline",
    "structured_final_answer",
)

RESULT_FIELDS = [
    "run_at",
    "query_id",
    "category",
    "strategy",
    "status",
    "expected_refused",
    "answer_provider",
    "answer_model",
    "judge_provider",
    "judge_model",
    "refused",
    "citation_count",
    "source_count",
    "llm_call_count",
    "tool_call_count",
    "executed_tool_call_count",
    "skipped_tool_call_count",
    "citation_repair_count",
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
    "avg_faithfulness",
    "avg_answer_coverage",
    "avg_citation_support",
    "avg_refusal_correctness",
    "avg_conciseness",
    "avg_safety_leak_check",
    "high_risk_count",
    "medium_risk_count",
    "judge_gate",
    "decision",
]


@dataclass(frozen=True)
class StrategyAnswer:
    result: AgentQueryResult
    provider: str
    model_name: str


def main() -> None:
    args = parse_args()
    apply_runtime_fallbacks(args)
    if args.summarize_existing:
        rows = read_csv(Path(args.out_results))
        cases = list({row.get("query_id", "") for row in rows if row.get("query_id")})
    else:
        cases = list(EVAL_CASES[: args.limit] if args.limit else EVAL_CASES)
        rows = build_rows(args, cases)
    summary = summarize(rows)
    if not args.summarize_existing:
        write_csv(Path(args.out_results), RESULT_FIELDS, rows)
    write_csv(Path(args.out_summary), SUMMARY_FIELDS, summary)
    print(
        f"stage38 tool-calling judge rows={len(rows)} cases={len(cases)} "
        f"execute={str(args.execute).lower()} "
        f"summarize_existing={str(args.summarize_existing).lower()}"
    )
    for row in summary:
        print(
            f"  {row['strategy']}: completed={row['completed_rows']} "
            f"faith={row['avg_faithfulness']} "
            f"cov={row['avg_answer_coverage']} cit={row['avg_citation_support']} "
            f"refusal={row['avg_refusal_correctness']} "
            f"concise={row['avg_conciseness']} "
            f"safety={row['avg_safety_leak_check']} gate={row['judge_gate']}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 38 tool-calling Judge A/B.")
    parser.add_argument("--limit", type=int, default=len(EVAL_CASES))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--out-results", default=str(RESULTS_PATH))
    parser.add_argument("--out-summary", default=str(SUMMARY_PATH))
    parser.add_argument(
        "--summarize-existing",
        action="store_true",
        help="Rebuild the six-metric summary from an existing results CSV without provider calls.",
    )
    parser.add_argument("--judge-provider", default=env_value("STAGE38_JUDGE_PROVIDER") or env_value("STAGE34_JUDGE_PROVIDER"))
    parser.add_argument("--judge-model", default=env_value("STAGE38_JUDGE_MODEL") or env_value("STAGE34_JUDGE_MODEL"))
    parser.add_argument("--judge-base-url", default=env_value("STAGE38_JUDGE_BASE_URL") or env_value("STAGE34_JUDGE_BASE_URL"))
    parser.add_argument("--judge-api-key", default=env_value("STAGE38_JUDGE_API_KEY") or env_value("STAGE34_JUDGE_API_KEY"))
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
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


def build_rows(args: argparse.Namespace, cases: Sequence[Any]) -> list[dict[str, str]]:
    run_at = datetime.now(timezone.utc).isoformat()
    if not args.execute:
        return [
            dry_run_row(run_at, case, strategy, args)
            for case in cases
            for strategy in STRATEGIES
        ]
    if missing_judge_config(args):
        return [
            skipped_row(run_at, case, strategy, args, "missing_judge_configuration")
            for case in cases
            for strategy in STRATEGIES
        ]

    try:
        answers = build_strategy_answers(args, cases)
    except Exception as exc:  # noqa: BLE001 - safe summary only.
        return [
            skipped_row(run_at, case, strategy, args, sanitize_text(str(exc), limit=180))
            for case in cases
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
    for case in cases:
        for strategy in STRATEGIES:
            answer = answers[(case.query_id, strategy)]
            payload = judge_payload(case, strategy, answer)
            try:
                judged = judge.judge(payload)
                rows.append(completed_row(run_at, case, strategy, args, answer, judged))
            except Exception as exc:  # noqa: BLE001 - safe summary only.
                rows.append(error_row(run_at, case, strategy, args, answer, exc))
    return rows


def build_strategy_answers(
    args: argparse.Namespace,
    cases: Sequence[Any],
) -> dict[tuple[str, str], StrategyAnswer]:
    settings = get_settings()
    init_db()
    embedding_provider = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension or None,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    planner_provider = build_planner_provider(settings)
    answers: dict[tuple[str, str], StrategyAnswer] = {}
    with SessionLocal() as db:
        for strategy in STRATEGIES:
            service = ToolCallingAgentService(
                db=db,
                embedding_provider=embedding_provider,
                chat_model_provider=planner_provider,
                log_answers=False,
                final_answer_strategy=strategy,
            )
            for case in cases:
                result = service.query(
                    case.question,
                    top_k=5,
                    max_tool_calls=3,
                    history=list(case.history),
                )
                answers[(case.query_id, strategy)] = StrategyAnswer(
                    result=result,
                    provider=planner_provider.provider_name,
                    model_name=planner_provider.model_name,
                )
    return answers


def judge_payload(case: Any, strategy: str, answer: StrategyAnswer) -> dict[str, object]:
    result = answer.result
    return {
        "query_id": case.query_id,
        "category": case.category,
        "strategy": strategy,
        "question": sanitize_text(case.question, limit=240),
        "expected_refused": expected_refused_for_case(case),
        "answer_summary": sanitize_text(result.answer, limit=700),
        "citation_count": len(result.citations),
        "source_summaries": [source_summary(source) for source in result.sources[:5]],
        "refused": result.refused,
        "refusal_reason": sanitize_text(result.refusal_reason or "", limit=180),
    }


def dry_run_row(
    run_at: str,
    case: Any,
    strategy: str,
    args: argparse.Namespace,
) -> dict[str, str]:
    return base_row(
        run_at=run_at,
        case=case,
        strategy=strategy,
        args=args,
        status="dry_run",
        answer_provider="tool_calling_agent",
        answer_model="not_run",
        error="Run with --execute for real tool-calling Judge A/B.",
    )


def skipped_row(
    run_at: str,
    case: Any,
    strategy: str,
    args: argparse.Namespace,
    error: str,
) -> dict[str, str]:
    return base_row(
        run_at=run_at,
        case=case,
        strategy=strategy,
        args=args,
        status="skipped",
        answer_provider="tool_calling_agent",
        answer_model="not_run",
        error=error,
    )


def completed_row(
    run_at: str,
    case: Any,
    strategy: str,
    args: argparse.Namespace,
    answer: StrategyAnswer,
    judged: Mapping[str, str],
) -> dict[str, str]:
    result = answer.result
    row = base_row(
        run_at=run_at,
        case=case,
        strategy=strategy,
        args=args,
        status="completed",
        answer_provider=answer.provider,
        answer_model=answer.model_name,
        refused=str(result.refused).lower(),
        citation_count=str(len(result.citations)),
        source_count=str(len(result.sources)),
        llm_call_count=str(metric_int(result, "llm_call_count")),
        tool_call_count=str(len(result.tool_calls)),
        executed_tool_call_count=str(metric_int(result, "executed_tool_call_count")),
        skipped_tool_call_count=str(metric_int(result, "skipped_tool_call_count")),
        citation_repair_count=str(metric_int(result, "citation_repair_count")),
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
    case: Any,
    strategy: str,
    args: argparse.Namespace,
    answer: StrategyAnswer,
    exc: Exception,
) -> dict[str, str]:
    result = answer.result
    return base_row(
        run_at=run_at,
        case=case,
        strategy=strategy,
        args=args,
        status="error",
        answer_provider=answer.provider,
        answer_model=answer.model_name,
        refused=str(result.refused).lower(),
        citation_count=str(len(result.citations)),
        source_count=str(len(result.sources)),
        error=sanitize_text(str(exc), limit=240),
    )


def base_row(
    *,
    run_at: str,
    case: Any,
    strategy: str,
    args: argparse.Namespace,
    status: str,
    answer_provider: str,
    answer_model: str,
    refused: str = "",
    citation_count: str = "",
    source_count: str = "",
    llm_call_count: str = "",
    tool_call_count: str = "",
    executed_tool_call_count: str = "",
    skipped_tool_call_count: str = "",
    citation_repair_count: str = "",
    error: str = "",
) -> dict[str, str]:
    return {
        "run_at": run_at,
        "query_id": case.query_id,
        "category": case.category,
        "strategy": strategy,
        "status": status,
        "expected_refused": str(expected_refused_for_case(case)).lower(),
        "answer_provider": answer_provider,
        "answer_model": answer_model,
        "judge_provider": args.judge_provider or "not_configured",
        "judge_model": args.judge_model or "not_configured",
        "refused": refused,
        "citation_count": citation_count,
        "source_count": source_count,
        "llm_call_count": llm_call_count,
        "tool_call_count": tool_call_count,
        "executed_tool_call_count": executed_tool_call_count,
        "skipped_tool_call_count": skipped_tool_call_count,
        "citation_repair_count": citation_repair_count,
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
        avg_faithfulness = average_score(completed, "faithfulness")
        avg_cov = average_score(completed, "answer_coverage")
        avg_cit = average_score(completed, "citation_support")
        avg_refusal = average_score(completed, "refusal_correctness")
        avg_conciseness = average_score(completed, "conciseness")
        avg_safety = average_score(completed, "safety_leak_check")
        high = sum(1 for row in completed if row.get("risk_level") == "high")
        medium = sum(1 for row in completed if row.get("risk_level") == "medium")
        gate = judge_gate(
            {
                "faithfulness": avg_faithfulness,
                "answer_coverage": avg_cov,
                "citation_support": avg_cit,
                "refusal_correctness": avg_refusal,
                "conciseness": avg_conciseness,
                "safety_leak_check": avg_safety,
            },
            high=high,
            completed=completed,
        )
        summaries.append(
            {
                "strategy": strategy,
                "status": (
                    "completed"
                    if completed
                    else strategy_rows[0]["status"]
                    if strategy_rows
                    else "empty"
                ),
                "total_rows": str(len(strategy_rows)),
                "completed_rows": str(len(completed)),
                "avg_faithfulness": avg_faithfulness,
                "avg_answer_coverage": avg_cov,
                "avg_citation_support": avg_cit,
                "avg_refusal_correctness": avg_refusal,
                "avg_conciseness": avg_conciseness,
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
    return f"{sum(values) / len(values):.3f}" if values else ""


def judge_gate(
    averages: Mapping[str, str],
    *,
    high: int,
    completed: Sequence[dict[str, str]],
) -> str:
    if not completed:
        return "not_run"
    try:
        passed = all(float(value) >= 0.8 for value in averages.values())
    except ValueError:
        return "review_required"
    if high:
        return "blocked"
    return "pass" if passed else "review_required"


def decision_for_gate(gate: str) -> str:
    if gate == "pass":
        return "candidate_for_default_after_human_review"
    if gate == "not_run":
        return "run_with_execute_before_claiming_judge_result"
    return "do_not_package_as_pass; document_root_cause"


def missing_judge_config(args: argparse.Namespace) -> bool:
    return not (args.judge_api_key and args.judge_base_url and args.judge_model)


def expected_refused_for_case(case: Any) -> bool:
    return case.category in {
        "off_topic",
        "responsibility_boundary",
        "evidence_insufficient",
    }


def metric_int(result: AgentQueryResult, key: str) -> int:
    value = (result.latency_trace or {}).get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


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


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    main()
