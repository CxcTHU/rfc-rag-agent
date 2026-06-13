from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_RESULTS = ROOT / "data" / "evaluation" / "stage29_real_quality_results.csv"
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "stage30_llm_judge_results.csv"
DEFAULT_API_KEY_ENV = "STAGE30_JUDGE_API_KEY"
DEFAULT_BASE_URL_ENV = "STAGE30_JUDGE_BASE_URL"
DEFAULT_MODEL_ENV = "STAGE30_JUDGE_MODEL"
DEFAULT_PROVIDER_ENV = "STAGE30_JUDGE_PROVIDER"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"

SENSITIVE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"Authorization:\s*[^\s]+", re.IGNORECASE),
]

FIELDS = [
    "run_at",
    "query_id",
    "judge_provider",
    "judge_model",
    "manual_run",
    "execute_requested",
    "faithfulness_score",
    "answer_relevancy_score",
    "groundedness_score",
    "judge_reason",
    "error_summary",
]


class JudgeClient(Protocol):
    def judge(self, row: Mapping[str, str]) -> dict[str, str]:
        """Return semantic judge scores for one stage 29 result row."""


@dataclass(frozen=True)
class OpenAICompatibleJudgeClient:
    provider: str
    model: str
    api_key: str
    base_url: str
    timeout_seconds: float = 45.0
    urlopen_func: Any = urllib.request.urlopen

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be empty")
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if not self.api_key.strip():
            raise ValueError("api_key must not be empty")
        if not self.base_url.strip():
            raise ValueError("base_url must not be empty")

    def judge(self, row: Mapping[str, str]) -> dict[str, str]:
        request = self._build_request(row)
        try:
            with self.urlopen_func(request, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"judge request failed with HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"judge request failed: {sanitize_text(str(exc.reason))}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("judge response was not valid JSON") from exc

        content = parse_openai_compatible_content(response_data)
        return parse_judge_payload(content)

    def _build_request(self, row: Mapping[str, str]) -> urllib.request.Request:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a cautious RAG evaluation judge. Return only a JSON "
                        "object with faithfulness_score, answer_relevancy_score, "
                        "groundedness_score, and judge_reason. Scores must be numbers "
                        "from 0 to 1. Do not include secrets or raw provider metadata."
                    ),
                },
                {"role": "user", "content": build_judge_prompt(row)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        return urllib.request.Request(
            endpoint_url(self.base_url),
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "rfc-rag-agent/stage30-semantic-judge",
            },
            method="POST",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Optional stage 30 LLM-as-Judge runner. Default mode is dry-run and "
            "does not call any real model. This script is not part of CI or the "
            "default deterministic scoring gate."
        )
    )
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--judge-provider", default="")
    parser.add_argument("--judge-model", default="")
    parser.add_argument("--judge-base-url", default="")
    parser.add_argument("--judge-api-key-env", default=DEFAULT_API_KEY_ENV)
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Explicitly run the manual semantic judge. Requires an API key in the "
            "configured environment variable. Default mode never calls a provider."
        ),
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="Optional row limit for dry-run/manual review planning. 0 means all rows.",
    )
    return parser.parse_args()


def read_stage29_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return [row for row in rows if row.get("expected_refused") == "false"]


def build_dry_run_rows(
    stage29_rows: list[dict[str, str]],
    *,
    judge_provider: str,
    judge_model: str,
    execute_requested: bool,
) -> list[dict[str, str]]:
    return run_judge_rows(
        stage29_rows,
        judge_provider=judge_provider,
        judge_model=judge_model,
        execute_requested=execute_requested,
        env={},
        api_key_env=DEFAULT_API_KEY_ENV,
    )


def run_judge_rows(
    stage29_rows: Sequence[Mapping[str, str]],
    *,
    judge_provider: str,
    judge_model: str,
    execute_requested: bool,
    env: Mapping[str, str] | None = None,
    api_key_env: str = DEFAULT_API_KEY_ENV,
    judge_base_url: str = "",
    timeout_seconds: float = 45.0,
    client: JudgeClient | None = None,
) -> list[dict[str, str]]:
    run_at = datetime.now(timezone.utc).isoformat()
    environment = env if env is not None else os.environ
    provider = resolve_provider(judge_provider, environment)
    model = resolve_model(judge_model, environment)

    if not execute_requested:
        return [
            make_output_row(
                run_at=run_at,
                source_row=row,
                judge_provider=provider,
                judge_model=model,
                manual_run=False,
                execute_requested=False,
                judge_reason=(
                    "dry_run_no_model_call; semantic faithfulness, answer relevancy, "
                    "and groundedness are not computed."
                ),
            )
            for row in stage29_rows
        ]

    api_key = environment.get(api_key_env, "").strip()
    base_url = resolve_base_url(judge_base_url, environment, provider)
    if not api_key:
        return [
            make_output_row(
                run_at=run_at,
                source_row=row,
                judge_provider=provider,
                judge_model=model,
                manual_run=True,
                execute_requested=True,
                judge_reason="manual_llm_judge_not_run; missing API key environment variable.",
                error_summary=f"missing_env:{api_key_env}",
            )
            for row in stage29_rows
        ]

    active_client = client or OpenAICompatibleJudgeClient(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
    output_rows: list[dict[str, str]] = []
    for row in stage29_rows:
        try:
            judged = active_client.judge(row)
            output_rows.append(
                make_output_row(
                    run_at=run_at,
                    source_row=row,
                    judge_provider=provider,
                    judge_model=model,
                    manual_run=True,
                    execute_requested=True,
                    faithfulness_score=judged["faithfulness_score"],
                    answer_relevancy_score=judged["answer_relevancy_score"],
                    groundedness_score=judged["groundedness_score"],
                    judge_reason=judged["judge_reason"],
                )
            )
        except Exception as exc:
            output_rows.append(
                make_output_row(
                    run_at=run_at,
                    source_row=row,
                    judge_provider=provider,
                    judge_model=model,
                    manual_run=True,
                    execute_requested=True,
                    judge_reason="manual_llm_judge_failed; see sanitized error_summary.",
                    error_summary=sanitize_text(str(exc), limit=240),
                )
            )
    return output_rows


def make_output_row(
    *,
    run_at: str,
    source_row: Mapping[str, str],
    judge_provider: str,
    judge_model: str,
    manual_run: bool,
    execute_requested: bool,
    faithfulness_score: str = "",
    answer_relevancy_score: str = "",
    groundedness_score: str = "",
    judge_reason: str = "",
    error_summary: str = "",
) -> dict[str, str]:
    return {
        "run_at": run_at,
        "query_id": source_row.get("query_id", ""),
        "judge_provider": judge_provider or "not_configured",
        "judge_model": judge_model or "not_configured",
        "manual_run": "true" if manual_run else "false",
        "execute_requested": "true" if execute_requested else "false",
        "faithfulness_score": faithfulness_score,
        "answer_relevancy_score": answer_relevancy_score,
        "groundedness_score": groundedness_score,
        "judge_reason": sanitize_text(judge_reason, limit=500),
        "error_summary": sanitize_text(error_summary, limit=240),
    }


def resolve_provider(judge_provider: str, env: Mapping[str, str]) -> str:
    return (judge_provider or env.get(DEFAULT_PROVIDER_ENV, "") or "deepseek").strip()


def resolve_model(judge_model: str, env: Mapping[str, str]) -> str:
    return (judge_model or env.get(DEFAULT_MODEL_ENV, "") or "deepseek-chat").strip()


def resolve_base_url(
    judge_base_url: str,
    env: Mapping[str, str],
    provider: str,
) -> str:
    configured = (judge_base_url or env.get(DEFAULT_BASE_URL_ENV, "")).strip()
    if configured:
        return configured
    if provider.strip().casefold() == "deepseek":
        return DEFAULT_DEEPSEEK_BASE_URL
    return ""


def endpoint_url(base_url: str) -> str:
    normalized_base_url = base_url.rstrip("/")
    if normalized_base_url.endswith("/chat/completions"):
        return normalized_base_url
    return f"{normalized_base_url}/chat/completions"


def build_judge_prompt(row: Mapping[str, str]) -> str:
    review_payload = {
        "query_id": row.get("query_id", ""),
        "question": row.get("question", ""),
        "expected_source_type": row.get("expected_source_type", ""),
        "top1_source_type": row.get("top1_source_type", ""),
        "top1_document_title": row.get("top1_document_title", ""),
        "top_titles": split_compact_titles(row.get("top_titles", "")),
        "precision_at_5": row.get("precision_at_5", ""),
        "rule_based_coverage_ratio": row.get("coverage_ratio", ""),
        "covered_points": split_semicolon_list(row.get("covered_points", "")),
        "missing_points": split_semicolon_list(row.get("missing_points", "")),
    }
    return (
        "Evaluate the retrieved evidence metadata for this RAG result. "
        "Do not treat rule_based_coverage_ratio as semantic faithfulness. "
        "Use the missing and covered point lists only as review hints.\n\n"
        f"{json.dumps(review_payload, ensure_ascii=False)}"
    )


def split_semicolon_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def split_compact_titles(value: str) -> list[str]:
    return [item.strip() for item in value.split("||") if item.strip()][:5]


def parse_openai_compatible_content(response_data: Mapping[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("judge response did not include choices")
    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        raise RuntimeError("judge response choice is not an object")
    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise RuntimeError("judge response choice did not include a message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("judge response message content is empty")
    return content.strip()


def parse_judge_payload(content: str) -> dict[str, str]:
    payload = json.loads(strip_json_fence(content))
    if not isinstance(payload, Mapping):
        raise RuntimeError("judge payload is not an object")
    return {
        "faithfulness_score": format_score(payload.get("faithfulness_score")),
        "answer_relevancy_score": format_score(payload.get("answer_relevancy_score")),
        "groundedness_score": format_score(payload.get("groundedness_score")),
        "judge_reason": sanitize_text(str(payload.get("judge_reason", "")), limit=500),
    }


def strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def format_score(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("judge score is missing or not numeric") from exc
    numeric = max(0.0, min(1.0, numeric))
    return f"{numeric:.3f}"


def sanitize_text(value: str, *, limit: int = 500) -> str:
    sanitized = " ".join((value or "").split())
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    forbidden_terms = ["raw_response", "Authorization", "Bearer"]
    for term in forbidden_terms:
        sanitized = re.sub(term, "[REDACTED]", sanitized, flags=re.IGNORECASE)
    if len(sanitized) > limit:
        sanitized = f"{sanitized[: limit - 3]}..."
    return sanitized


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    rows = read_stage29_rows(Path(args.results))
    if args.max_rows > 0:
        rows = rows[: args.max_rows]
    judge_rows = run_judge_rows(
        rows,
        judge_provider=args.judge_provider,
        judge_model=args.judge_model,
        judge_base_url=args.judge_base_url,
        execute_requested=bool(args.execute),
        api_key_env=args.judge_api_key_env,
        timeout_seconds=args.timeout_seconds,
    )
    write_rows(Path(args.output), judge_rows)
    mode = "manual_execute" if args.execute else "dry_run"
    real_model_calls = sum(
        1
        for row in judge_rows
        if row["manual_run"] == "true" and not row["error_summary"]
    )
    print(
        f"stage30 semantic judge {mode} rows={len(judge_rows)} output={args.output}; "
        f"real_model_calls={real_model_calls}"
    )


if __name__ == "__main__":
    main()
