"""Stage 43 multi-turn LLM Judge runner.

The script judges multi-turn generation quality across Stage 43 history modes.
It defaults to dry-run and writes only sanitized scores/reasons. Real answer
generation and Judge calls require ``--execute`` and local provider config.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.agent.service import AgentQueryResult, AgentService  # noqa: E402
from app.services.generation.chat_model import create_chat_model_provider  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from scripts.evaluate_stage43_multi_turn import (  # noqa: E402
    CASE_PATH,
    HISTORY_MODE_CHOICES,
    HISTORY_MODES,
    MultiTurnCaseRow,
    build_memory_hint,
    build_summary,
    group_cases,
    load_cases,
)
from scripts.judge_stage34_generation_quality import (  # noqa: E402
    OpenAICompatibleStage34JudgeClient,
    endpoint_url,
    sanitize_text,
    source_summary,
    strip_json_fence,
)


RESULTS_PATH = ROOT / "data" / "evaluation" / "stage43_multi_turn_judge_results.csv"
SUMMARY_PATH = ROOT / "data" / "evaluation" / "stage43_multi_turn_judge_summary.csv"

RESULT_FIELDS = [
    "run_at",
    "case_id",
    "scenario",
    "turn_index",
    "history_mode",
    "status",
    "expected_refused",
    "answer_provider",
    "answer_model",
    "judge_provider",
    "judge_model",
    "refused",
    "citation_count",
    "source_count",
    "answer_faithfulness",
    "citation_accuracy",
    "context_coherence",
    "refusal_consistency",
    "risk_level",
    "short_reason",
    "next_action",
    "error",
]

SUMMARY_FIELDS = [
    "history_mode",
    "status",
    "total_rows",
    "completed_rows",
    "skipped_rows",
    "error_rows",
    "avg_answer_faithfulness",
    "avg_citation_accuracy",
    "avg_context_coherence",
    "avg_refusal_consistency",
    "high_risk_count",
    "medium_risk_count",
    "judge_gate",
    "decision",
]

SENSITIVE_FIELD_NAMES = {
    "answer",
    "raw_answer",
    "raw_response",
    "reasoning_content",
    "api_key",
    "bearer_token",
    "authorization",
    "chunk_content",
}


@dataclass(frozen=True)
class Stage43JudgeCase:
    case_id: str
    scenario: str
    turn_index: int
    question: str
    history_mode: str
    history: tuple[str, ...]
    expected_refused: bool
    expected_answer_points: tuple[str, ...]
    expected_source_terms: tuple[str, ...]


@dataclass(frozen=True)
class AnswerRecord:
    result: AgentQueryResult
    provider: str
    model_name: str


class OpenAICompatibleStage43JudgeClient(OpenAICompatibleStage34JudgeClient):
    def judge(self, payload: Mapping[str, object]) -> dict[str, str]:
        request = self._build_request(payload)
        import urllib.error
        import urllib.request

        try:
            with self.urlopen_func(request, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"judge request failed with HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"judge request failed: {sanitize_text(str(exc.reason))}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("judge response was not valid JSON") from exc

        choices = response_data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("judge response did not include choices")
        message = choices[0].get("message") if isinstance(choices[0], Mapping) else None
        if not isinstance(message, Mapping):
            raise RuntimeError("judge response did not include message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("judge response content is empty")
        return parse_stage43_judge_payload(content)

    def _build_request(self, payload: Mapping[str, object]):
        request_payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a careful multi-turn RAG quality judge. Return only JSON with "
                        "answer_faithfulness, citation_accuracy, context_coherence, "
                        "refusal_consistency, risk_level, short_reason, and next_action. "
                        "Scores must be numbers from 0 to 1. Judge whether the answer uses "
                        "conversation context correctly while grounding claims in retrieved "
                        "knowledge-base sources. Memory, summaries, and prior user text are "
                        "not citation sources. Do not include chain-of-thought, raw provider "
                        "metadata, secrets, credentials, or long source text."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        import urllib.request

        return urllib.request.Request(
            endpoint_url(self.base_url),
            data=json.dumps(request_payload, ensure_ascii=True).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "rfc-rag-agent/stage43-multi-turn-judge",
            },
            method="POST",
        )


def main() -> None:
    args = parse_args()
    cases = build_judge_cases(load_cases(Path(args.cases)), args.history_mode, args.recent_turns)
    if args.limit:
        cases = cases[: args.limit]
    output_path = Path(args.out_results)
    if args.execute and should_merge_default_results(args.history_mode, output_path):
        rows = build_rows_incremental(args, cases, output_path)
    else:
        rows = build_rows(args, cases)
    if should_merge_default_results(args.history_mode, output_path) and not (
        args.execute and output_path.resolve() == RESULTS_PATH.resolve()
    ):
        rows = merge_result_rows(read_result_rows(output_path), rows, replacement_mode=args.history_mode)
    else:
        rows = sort_result_rows(rows)
    summaries = summarize(rows)
    write_csv(output_path, RESULT_FIELDS, rows)
    write_csv(Path(args.out_summary), SUMMARY_FIELDS, summaries)
    print(
        f"stage43 multi-turn judge rows={len(rows)} completed="
        f"{sum(1 for row in rows if row['status'] == 'completed')} "
        f"execute={str(args.execute).lower()} out={args.out_results}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 43 multi-turn LLM Judge.")
    parser.add_argument("--cases", default=str(CASE_PATH))
    parser.add_argument("--out-results", default=str(RESULTS_PATH))
    parser.add_argument("--out-summary", default=str(SUMMARY_PATH))
    parser.add_argument("--history-mode", choices=HISTORY_MODE_CHOICES, default="all")
    parser.add_argument("--recent-turns", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help="Re-run completed rows for the selected history mode when using the default results file.",
    )
    parser.add_argument("--judge-provider", default=env_value("STAGE43_JUDGE_PROVIDER") or env_value("STAGE42_JUDGE_PROVIDER") or env_value("STAGE34_JUDGE_PROVIDER"))
    parser.add_argument("--judge-model", default=env_value("STAGE43_JUDGE_MODEL") or env_value("STAGE42_JUDGE_MODEL") or env_value("STAGE34_JUDGE_MODEL"))
    parser.add_argument("--judge-base-url", default=env_value("STAGE43_JUDGE_BASE_URL") or env_value("STAGE42_JUDGE_BASE_URL") or env_value("STAGE34_JUDGE_BASE_URL"))
    parser.add_argument("--judge-api-key", default=env_value("STAGE43_JUDGE_API_KEY") or env_value("STAGE42_JUDGE_API_KEY") or env_value("STAGE34_JUDGE_API_KEY"))
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args()


def build_judge_cases(
    rows: Sequence[MultiTurnCaseRow],
    history_mode: str,
    recent_turns: int,
) -> list[Stage43JudgeCase]:
    modes = HISTORY_MODES if history_mode == "all" else (history_mode,)
    grouped = group_cases(list(rows))
    cases: list[Stage43JudgeCase] = []
    for mode in modes:
        for case_id in sorted(grouped):
            previous: list[MultiTurnCaseRow] = []
            for turn in grouped[case_id]:
                cases.append(
                    Stage43JudgeCase(
                        case_id=turn.case_id,
                        scenario=turn.scenario,
                        turn_index=turn.turn_index,
                        question=turn.user_question,
                        history_mode=mode,
                        history=history_for_mode(previous, mode, recent_turns, turn.user_question),
                        expected_refused=turn.expected_refused,
                        expected_answer_points=turn.expected_answer_points,
                        expected_source_terms=turn.expected_source_terms,
                    )
                )
                previous.append(turn)
    return cases


def history_for_mode(
    previous: Sequence[MultiTurnCaseRow],
    history_mode: str,
    recent_turns: int,
    current_question: str = "",
) -> tuple[str, ...]:
    if history_mode == "no_history":
        return ()
    recent = tuple(turn.user_question for turn in previous[-recent_turns:])
    if history_mode == "recent_only":
        return recent
    summary = build_summary(list(previous))
    if history_mode == "summary_recent":
        return tuple(item for item in (summary, *recent) if item)
    if history_mode == "layered_memory":
        memory = build_memory_hint(list(previous), current_question=current_question)
        return tuple(item for item in (summary, memory, *recent) if item)
    raise ValueError(f"Unsupported history mode: {history_mode}")


def build_rows(args: argparse.Namespace, cases: Sequence[Stage43JudgeCase]) -> list[dict[str, str]]:
    run_at = datetime.now(timezone.utc).isoformat()
    provider, model, base_url, api_key = resolve_judge_config(args)
    if not args.execute:
        return [dry_run_row(run_at, case, provider, model) for case in cases]
    if not (api_key and base_url and model):
        return [skipped_row(run_at, case, provider, model, "missing_judge_configuration") for case in cases]

    try:
        answers = build_answers(cases)
    except Exception as exc:  # noqa: BLE001 - write safe summary only.
        return [skipped_row(run_at, case, provider, model, sanitize_text(str(exc), limit=180)) for case in cases]

    client = OpenAICompatibleStage43JudgeClient(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=args.timeout_seconds,
    )
    rows: list[dict[str, str]] = []
    for case in cases:
        answer = answers[case_key(case)]
        payload = judge_payload(case, answer)
        try:
            judged = client.judge(payload)
            rows.append(completed_row(run_at, case, provider, model, answer, judged))
        except Exception as exc:  # noqa: BLE001 - write safe summary only.
            rows.append(error_row(run_at, case, provider, model, answer, exc))
    return rows


def build_rows_incremental(
    args: argparse.Namespace,
    cases: Sequence[Stage43JudgeCase],
    output_path: Path,
) -> list[dict[str, str]]:
    run_at = datetime.now(timezone.utc).isoformat()
    provider, model, base_url, api_key = resolve_judge_config(args)
    if not (api_key and base_url and model):
        rows = [skipped_row(run_at, case, provider, model, "missing_judge_configuration") for case in cases]
        return merge_result_rows(read_result_rows(output_path), rows, replacement_mode=args.history_mode)

    existing_rows = read_result_rows(output_path)
    row_by_key = {result_row_key(row): row for row in existing_rows}
    completed_keys = {
        result_row_key(row)
        for row in existing_rows
        if row.get("history_mode") == args.history_mode and row.get("status") == "completed"
    }

    settings = get_settings()
    init_db()
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
    client = OpenAICompatibleStage43JudgeClient(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=args.timeout_seconds,
    )

    with SessionLocal() as db:
        service = AgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_provider,
            log_answers=False,
        )
        for case in cases:
            key = case_key(case)
            if key in completed_keys and not args.force_rerun:
                continue
            try:
                result = service.query(case.question, top_k=5, max_tool_calls=3, history=list(case.history))
                answer = AnswerRecord(
                    result=result,
                    provider=chat_provider.provider_name,
                    model_name=chat_provider.model_name,
                )
                judged = client.judge(judge_payload(case, answer))
                row = completed_row(run_at, case, provider, model, answer, judged)
            except Exception as exc:  # noqa: BLE001 - write safe summary only.
                fallback = AnswerRecord(
                    result=AgentQueryResult(question=case.question, answer="", tool_calls=[]),
                    provider=chat_provider.provider_name,
                    model_name=chat_provider.model_name,
                )
                row = error_row(run_at, case, provider, model, fallback, exc)
            row_by_key[key] = row
            merged_rows = sort_result_rows(row_by_key.values())
            write_csv(output_path, RESULT_FIELDS, merged_rows)
            write_csv(SUMMARY_PATH, SUMMARY_FIELDS, summarize(merged_rows))

    return sort_result_rows(row_by_key.values())


def build_answers(cases: Sequence[Stage43JudgeCase]) -> dict[str, AnswerRecord]:
    settings = get_settings()
    init_db()
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
    answers: dict[str, AnswerRecord] = {}
    with SessionLocal() as db:
        service = AgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_provider,
            log_answers=False,
        )
        for case in cases:
            result = service.query(case.question, top_k=5, max_tool_calls=3, history=list(case.history))
            answers[case_key(case)] = AnswerRecord(
                result=result,
                provider=chat_provider.provider_name,
                model_name=chat_provider.model_name,
            )
    return answers


def judge_payload(case: Stage43JudgeCase, answer: AnswerRecord) -> dict[str, object]:
    result = answer.result
    return {
        "case_id": case.case_id,
        "scenario": case.scenario,
        "turn_index": case.turn_index,
        "history_mode": case.history_mode,
        "question": sanitize_text(case.question, limit=240),
        "history_summary": [sanitize_text(item, limit=160) for item in case.history[-4:]],
        "expected_refused": case.expected_refused,
        "expected_answer_points": [sanitize_text(item, limit=120) for item in case.expected_answer_points[:6]],
        "expected_source_terms": [sanitize_text(item, limit=120) for item in case.expected_source_terms[:6]],
        "answer_summary": sanitize_text(result.answer, limit=700),
        "refused": result.refused,
        "refusal_reason": sanitize_text(result.refusal_reason or "", limit=180),
        "citation_count": len(result.citations),
        "source_summaries": [source_summary(source) for source in result.sources[:5]],
    }


def parse_stage43_judge_payload(content: str) -> dict[str, str]:
    payload = json.loads(strip_json_fence(content))
    return {
        "answer_faithfulness": format_score(payload.get("answer_faithfulness")),
        "citation_accuracy": format_score(payload.get("citation_accuracy")),
        "context_coherence": format_score(payload.get("context_coherence")),
        "refusal_consistency": format_score(payload.get("refusal_consistency")),
        "risk_level": normalize_risk(payload.get("risk_level")),
        "short_reason": sanitize_text(str(payload.get("short_reason", "")), limit=300),
        "next_action": sanitize_text(str(payload.get("next_action", "")), limit=240),
    }


def dry_run_row(run_at: str, case: Stage43JudgeCase, provider: str, model: str) -> dict[str, str]:
    return base_row(
        run_at,
        case,
        provider,
        model,
        status="dry_run",
        answer_provider="not_run",
        answer_model="not_run",
        error="Run with --execute for real multi-turn Judge.",
    )


def skipped_row(run_at: str, case: Stage43JudgeCase, provider: str, model: str, error: str) -> dict[str, str]:
    return base_row(
        run_at,
        case,
        provider,
        model,
        status="skipped",
        answer_provider="not_run",
        answer_model="not_run",
        error=error,
    )


def completed_row(
    run_at: str,
    case: Stage43JudgeCase,
    provider: str,
    model: str,
    answer: AnswerRecord,
    judged: Mapping[str, str],
) -> dict[str, str]:
    row = base_row(
        run_at,
        case,
        provider,
        model,
        status="completed",
        answer_provider=answer.provider,
        answer_model=answer.model_name,
        refused=str(answer.result.refused).lower(),
        citation_count=str(len(answer.result.citations)),
        source_count=str(len(answer.result.sources)),
    )
    for key in [
        "answer_faithfulness",
        "citation_accuracy",
        "context_coherence",
        "refusal_consistency",
        "risk_level",
        "short_reason",
        "next_action",
    ]:
        row[key] = sanitize_text(str(judged.get(key, "")), limit=300)
    return row


def error_row(
    run_at: str,
    case: Stage43JudgeCase,
    provider: str,
    model: str,
    answer: AnswerRecord,
    exc: Exception,
) -> dict[str, str]:
    return base_row(
        run_at,
        case,
        provider,
        model,
        status="error",
        answer_provider=answer.provider,
        answer_model=answer.model_name,
        refused=str(answer.result.refused).lower(),
        citation_count=str(len(answer.result.citations)),
        source_count=str(len(answer.result.sources)),
        error=sanitize_text(str(exc), limit=240),
    )


def base_row(
    run_at: str,
    case: Stage43JudgeCase,
    provider: str,
    model: str,
    *,
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
        "case_id": case.case_id,
        "scenario": case.scenario,
        "turn_index": str(case.turn_index),
        "history_mode": case.history_mode,
        "status": status,
        "expected_refused": str(case.expected_refused).lower(),
        "answer_provider": answer_provider,
        "answer_model": answer_model,
        "judge_provider": provider or "not_configured",
        "judge_model": model or "not_configured",
        "refused": refused,
        "citation_count": citation_count,
        "source_count": source_count,
        "answer_faithfulness": "",
        "citation_accuracy": "",
        "context_coherence": "",
        "refusal_consistency": "",
        "risk_level": "",
        "short_reason": "",
        "next_action": "",
        "error": sanitize_text(error, limit=240),
    }


def summarize(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["history_mode"]].append(row)
    for mode in sorted(grouped):
        mode_rows = grouped[mode]
        completed = [row for row in mode_rows if row["status"] == "completed"]
        skipped = [row for row in mode_rows if row["status"] == "skipped"]
        errors = [row for row in mode_rows if row["status"] == "error"]
        high = sum(1 for row in completed if row.get("risk_level") == "high")
        medium = sum(1 for row in completed if row.get("risk_level") == "medium")
        gate = judge_gate(completed, high)
        summaries.append(
            {
                "history_mode": mode,
                "status": "completed" if completed and not errors else mode_rows[0]["status"],
                "total_rows": str(len(mode_rows)),
                "completed_rows": str(len(completed)),
                "skipped_rows": str(len(skipped)),
                "error_rows": str(len(errors)),
                "avg_answer_faithfulness": average_score(completed, "answer_faithfulness"),
                "avg_citation_accuracy": average_score(completed, "citation_accuracy"),
                "avg_context_coherence": average_score(completed, "context_coherence"),
                "avg_refusal_consistency": average_score(completed, "refusal_consistency"),
                "high_risk_count": str(high),
                "medium_risk_count": str(medium),
                "judge_gate": gate,
                "decision": decision_for_mode(mode, gate),
            }
        )
    return summaries


def judge_gate(completed: Sequence[dict[str, str]], high: int) -> str:
    if not completed:
        return "not_run"
    fields = [
        "answer_faithfulness",
        "citation_accuracy",
        "context_coherence",
        "refusal_consistency",
    ]
    try:
        passed = all(float(average_score(completed, field)) >= 0.8 for field in fields)
    except ValueError:
        return "review_required"
    if high:
        return "blocked"
    return "pass" if passed else "review_required"


def decision_for_mode(mode: str, gate: str) -> str:
    if gate == "not_run":
        return "run_with_execute_before_claiming_real_judge_result"
    if mode == "layered_memory":
        return "compare_against_summary_recent_before_default_change"
    if mode == "summary_recent":
        return "current_default_reference"
    return "comparison_baseline"


def average_score(rows: Sequence[dict[str, str]], field: str) -> str:
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(row.get(field, "")))
        except ValueError:
            continue
    return f"{sum(values) / len(values):.3f}" if values else ""


def resolve_judge_config(args: argparse.Namespace) -> tuple[str, str, str, str]:
    settings = get_settings()
    provider = (args.judge_provider or settings.chat_model_provider or "not_configured").strip()
    model = (args.judge_model or settings.chat_model_name or "").strip()
    base_url = (args.judge_base_url or settings.chat_model_base_url or "").strip()
    api_key = (args.judge_api_key or settings.chat_model_api_key or "").strip()
    return provider, model, base_url, api_key


def format_score(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("judge score is missing or not numeric") from exc
    return f"{max(0.0, min(1.0, numeric)):.3f}"


def normalize_risk(value: Any) -> str:
    risk = str(value or "").strip().lower()
    return risk if risk in {"high", "medium", "low"} else "medium"


def case_key(case: Stage43JudgeCase) -> str:
    return f"{case.history_mode}:{case.case_id}:{case.turn_index}"


def result_row_key(row: Mapping[str, str]) -> str:
    return f"{row.get('history_mode', '')}:{row.get('case_id', '')}:{row.get('turn_index', '')}"


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


def read_result_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(RESULT_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing stage43 judge result fields: {', '.join(sorted(missing))}")
        return [{field: row.get(field, "") for field in RESULT_FIELDS} for row in reader]


def merge_result_rows(
    existing_rows: Sequence[dict[str, str]],
    replacement_rows: Sequence[dict[str, str]],
    *,
    replacement_mode: str,
) -> list[dict[str, str]]:
    preserved = [row for row in existing_rows if row.get("history_mode") != replacement_mode]
    return sort_result_rows([*preserved, *replacement_rows])


def sort_result_rows(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    mode_order = {mode: index for index, mode in enumerate(HISTORY_MODES)}

    def row_key(row: dict[str, str]) -> tuple[int, str, int]:
        turn_index = row.get("turn_index") or "0"
        return (
            mode_order.get(row.get("history_mode", ""), len(mode_order)),
            row.get("case_id", ""),
            int(turn_index) if turn_index.isdigit() else 0,
        )

    return sorted(rows, key=row_key)


def should_merge_default_results(history_mode: str, output_path: Path) -> bool:
    return history_mode != "all" and output_path.resolve() == RESULTS_PATH.resolve()


if __name__ == "__main__":
    main()
