from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


RESULTS_PATH = ROOT / "data" / "evaluation" / "stage36_production_smoke_results.csv"

SMOKE_FIELDS = [
    "run_at",
    "case_id",
    "endpoint",
    "method",
    "execute_requested",
    "auth_required",
    "status",
    "http_status",
    "latency_ms",
    "required_fields_present",
    "refused",
    "citation_count",
    "expected_mode",
    "actual_mode",
    "mode_matched",
    "validator_marker",
    "sensitive_field_detected",
    "error_summary",
]

SENSITIVE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE),
    re.compile(r"Authorization:\s*[^\s]+", re.IGNORECASE),
    re.compile(r"raw_response", re.IGNORECASE),
    re.compile(r"reasoning_content", re.IGNORECASE),
    re.compile(r"hidden_thought", re.IGNORECASE),
]

VALIDATOR_MARKERS = (
    "citation_validator",
    "validator_marker",
    "unsupported citation",
    "[validator]",
)


@dataclass(frozen=True)
class SmokeCase:
    case_id: str
    method: str
    endpoint: str
    payload: dict[str, Any] | None = None
    required_fields: tuple[str, ...] = ()
    stream: bool = False
    expected_mode: str | None = None
    auth_required: bool = False
    expected_http_statuses: tuple[int, ...] = (200,)


@dataclass(frozen=True)
class HttpResult:
    status_code: int
    text: str
    latency_ms: float


def main() -> None:
    args = parse_args()
    rows = run_smoke(
        base_url=args.base_url,
        execute=args.execute,
        timeout_seconds=args.timeout_seconds,
        auth_enabled=args.auth_enabled,
        smoke_username=args.smoke_username,
        smoke_email=args.smoke_email,
        smoke_password=args.smoke_password,
        image_asset_path=args.image_asset_path,
        urlopen_func=urllib.request.urlopen,
    )
    write_csv(Path(args.out), rows)
    failed = [row for row in rows if row["status"] != "passed" and args.execute]
    print(
        f"stage36 production smoke rows={len(rows)} "
        f"execute={str(args.execute).lower()} failed={len(failed)}"
    )
    print(f"wrote {args.out}")
    if failed:
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 36 production endpoint smoke.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default=str(RESULTS_PATH))
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually call the configured service endpoints.",
    )
    parser.add_argument(
        "--auth-enabled",
        action="store_true",
        help="Run AUTH_ENABLED=true smoke: register/login/me and bearer-token protected endpoints.",
    )
    parser.add_argument("--smoke-username", default="phase55_smoke")
    parser.add_argument("--smoke-email", default="phase55_smoke@example.com")
    parser.add_argument(
        "--image-asset-path",
        default="/assets/images/1059/page10_img1.png",
        help="Representative image asset path to verify data/images sync.",
    )
    parser.add_argument(
        "--smoke-password",
        default="phase55-local-password",
        help="Local smoke password. Do not use or print real user credentials.",
    )
    return parser.parse_args()


def auth_smoke_cases(
    *,
    smoke_username: str = "phase55_smoke",
    smoke_email: str = "phase55_smoke@example.com",
    smoke_password: str = "phase55-local-password",
) -> list[SmokeCase]:
    return [
        SmokeCase(
            case_id="agent_query_unauthenticated_401",
            method="POST",
            endpoint="/agent/query",
            payload={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 5,
            },
            expected_http_statuses=(401,),
        ),
        SmokeCase(
            case_id="auth_register_smoke_user",
            method="POST",
            endpoint="/auth/register",
            payload={
                "username": smoke_username,
                "email": smoke_email,
                "password": smoke_password,
            },
            required_fields=("id", "username", "email"),
            expected_http_statuses=(200, 409),
        ),
        SmokeCase(
            case_id="auth_login_smoke_user",
            method="POST",
            endpoint="/auth/login",
            payload={
                "username_or_email": smoke_username,
                "password": smoke_password,
            },
            required_fields=("access_token", "token_type", "expires_in", "user"),
        ),
        SmokeCase(
            case_id="auth_me",
            method="GET",
            endpoint="/auth/me",
            required_fields=("id", "username", "email"),
            auth_required=True,
        ),
    ]


def smoke_cases(
    *,
    authenticated: bool = False,
    image_asset_path: str = "/assets/images/1059/page10_img1.png",
) -> list[SmokeCase]:
    auth_required = authenticated
    return [
        SmokeCase(
            case_id="health",
            method="GET",
            endpoint="/health",
            required_fields=("status",),
        ),
        SmokeCase(
            case_id="frontend_home",
            method="GET",
            endpoint="/",
        ),
        SmokeCase(
            case_id="image_asset",
            method="GET",
            endpoint=image_asset_path,
        ),
        SmokeCase(
            case_id="quality_report_html",
            method="GET",
            endpoint="/quality-report",
        ),
        SmokeCase(
            case_id="quality_report_data",
            method="GET",
            endpoint="/quality-report/data.json",
            required_fields=("run_id", "dimension", "score", "status"),
        ),
        SmokeCase(
            case_id="chat_authenticated" if authenticated else "chat",
            method="POST",
            endpoint="/chat",
            payload={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 5,
                "retrieval_mode": "auto",
            },
            required_fields=("answer", "refused", "citations", "sources"),
            auth_required=auth_required,
        ),
        SmokeCase(
            case_id="agent_query_default_tool_calling",
            method="POST",
            endpoint="/agent/query",
            payload={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 5,
                "max_tool_calls": 3,
            },
            required_fields=("answer", "refused", "citations", "sources", "mode"),
            expected_mode="tool_calling_agent",
            auth_required=auth_required,
        ),
        SmokeCase(
            case_id="agent_query_react_agent_rollback",
            method="POST",
            endpoint="/agent/query",
            payload={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 5,
                "max_tool_calls": 3,
                "mode": "react_agent",
            },
            required_fields=("answer", "refused", "citations", "sources", "mode"),
            expected_mode="react_agent",
            auth_required=auth_required,
        ),
        SmokeCase(
            case_id="agent_query_tool_calling",
            method="POST",
            endpoint="/agent/query",
            payload={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 5,
                "max_tool_calls": 3,
                "mode": "tool_calling_agent",
            },
            required_fields=("answer", "refused", "citations", "sources", "mode"),
            expected_mode="tool_calling_agent",
            auth_required=auth_required,
        ),
        SmokeCase(
            case_id="agent_query_multiturn_transform",
            method="POST",
            endpoint="/agent/query",
            payload={
                "question": "Translate that into Chinese.",
                "history": [
                    "Assistant: Filling capacity depends on flowability and aggregate voids [1].",
                ],
                "mode": "default",
            },
            required_fields=("answer", "refused", "mode"),
            expected_mode="default",
            auth_required=auth_required,
        ),
        SmokeCase(
            case_id="agent_query_model_meta",
            method="POST",
            endpoint="/agent/query",
            payload={"question": "What model are you using?", "mode": "default"},
            required_fields=("answer", "refused", "mode"),
            expected_mode="meta",
            auth_required=auth_required,
        ),
        SmokeCase(
            case_id="agent_query_stream_default_tool_calling",
            method="POST",
            endpoint="/agent/query/stream",
            payload={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 5,
                "max_tool_calls": 3,
            },
            required_fields=("metadata", "done"),
            stream=True,
            expected_mode="tool_calling_agent",
            auth_required=auth_required,
        ),
        SmokeCase(
            case_id="agent_query_stream_react_agent_rollback",
            method="POST",
            endpoint="/agent/query/stream",
            payload={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 5,
                "max_tool_calls": 3,
                "mode": "react_agent",
            },
            required_fields=("metadata", "done"),
            stream=True,
            expected_mode="react_agent",
            auth_required=auth_required,
        ),
        SmokeCase(
            case_id="agent_query_tool_calling_stream",
            method="POST",
            endpoint="/agent/query/stream",
            payload={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 5,
                "max_tool_calls": 3,
                "mode": "tool_calling_agent",
            },
            required_fields=("metadata", "done"),
            stream=True,
            expected_mode="tool_calling_agent",
            auth_required=auth_required,
        ),
    ]


def run_smoke(
    *,
    base_url: str,
    execute: bool,
    timeout_seconds: float,
    auth_enabled: bool = False,
    smoke_username: str = "phase55_smoke",
    smoke_email: str = "phase55_smoke@example.com",
    smoke_password: str = "phase55-local-password",
    image_asset_path: str = "/assets/images/1059/page10_img1.png",
    urlopen_func: Callable[..., Any],
) -> list[dict[str, str]]:
    run_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, str]] = []
    auth_token = ""
    cases = smoke_cases(authenticated=auth_enabled, image_asset_path=image_asset_path)
    if auth_enabled:
        auth_cases = auth_smoke_cases(
            smoke_username=smoke_username,
            smoke_email=smoke_email,
            smoke_password=smoke_password,
        )
        cases = auth_cases + cases
    for case in cases:
        if not execute:
            rows.append(dry_run_row(run_at, case))
            continue
        row, maybe_token = execute_case(
            run_at=run_at,
            base_url=base_url,
            case=case,
            timeout_seconds=timeout_seconds,
            auth_token=auth_token,
            urlopen_func=urlopen_func,
        )
        rows.append(row)
        if maybe_token:
            auth_token = maybe_token
    return rows


def execute_case(
    *,
    run_at: str,
    base_url: str,
    case: SmokeCase,
    timeout_seconds: float,
    auth_token: str = "",
    urlopen_func: Callable[..., Any],
) -> tuple[dict[str, str], str]:
    try:
        result = perform_http_request(
            base_url=base_url,
            case=case,
            timeout_seconds=timeout_seconds,
            auth_token=auth_token,
            urlopen_func=urlopen_func,
        )
        return evaluate_http_result(run_at, case, result), extract_access_token(case, result)
    except Exception as exc:  # noqa: BLE001 - smoke should report sanitized failures.
        return (
            base_row(
                run_at=run_at,
                case=case,
                execute_requested=True,
                status="failed",
                error_summary=sanitize_text(str(exc), limit=240),
            ),
            "",
        )


def perform_http_request(
    *,
    base_url: str,
    case: SmokeCase,
    timeout_seconds: float,
    auth_token: str = "",
    urlopen_func: Callable[..., Any],
) -> HttpResult:
    started = time.perf_counter()
    request = build_request(base_url=base_url, case=case, auth_token=auth_token)
    try:
        with urlopen_func(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            status_code = int(getattr(response, "status", 200))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status_code = exc.code
    latency_ms = (time.perf_counter() - started) * 1000.0
    return HttpResult(status_code=status_code, text=body, latency_ms=latency_ms)


def build_request(*, base_url: str, case: SmokeCase, auth_token: str = "") -> urllib.request.Request:
    url = f"{base_url.rstrip('/')}{case.endpoint}"
    data = None
    headers = {"Accept": "application/json"}
    if case.payload is not None:
        data = json.dumps(case.payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if case.stream:
        headers["Accept"] = "text/event-stream"
    if case.auth_required and auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return urllib.request.Request(url, data=data, headers=headers, method=case.method)


def evaluate_http_result(
    run_at: str,
    case: SmokeCase,
    result: HttpResult,
) -> dict[str, str]:
    body = result.text
    if case.stream:
        parsed = parse_sse_events(body)
        required_present = all(name in parsed for name in case.required_fields)
        metadata = parsed.get("metadata")
        payload = metadata if isinstance(metadata, dict) else {}
    else:
        payload = parse_json_body(body)
        required_present = required_fields_present(payload, case.required_fields)

    refused = payload.get("refused") if isinstance(payload, dict) else None
    citations = payload.get("citations") if isinstance(payload, dict) else None
    citation_count = len(citations) if isinstance(citations, list) else 0
    actual_mode = payload.get("mode") if isinstance(payload, dict) else None
    mode_matched = case.expected_mode is None or actual_mode == case.expected_mode
    validator_marker = contains_validator_marker(body)
    sensitive = contains_sensitive_marker(body)
    expected_status = result.status_code in case.expected_http_statuses
    if case.case_id == "auth_register_smoke_user" and result.status_code == 409:
        required_present = True

    passed = (
        expected_status
        and required_present
        and mode_matched
        and not validator_marker
        and not sensitive
    )
    return base_row(
        run_at=run_at,
        case=case,
        execute_requested=True,
        status="passed" if passed else "failed",
        http_status=str(result.status_code),
        latency_ms=f"{result.latency_ms:.3f}",
        required_fields_present=str(required_present).lower(),
        refused=str(refused).lower() if isinstance(refused, bool) else "",
        citation_count=str(citation_count),
        actual_mode=actual_mode if isinstance(actual_mode, str) else "",
        mode_matched=str(mode_matched).lower(),
        validator_marker=str(validator_marker).lower(),
        sensitive_field_detected=str(sensitive).lower(),
        error_summary="" if passed else failure_summary(result.status_code, case.expected_http_statuses, required_present, mode_matched, validator_marker, sensitive),
    )


def dry_run_row(run_at: str, case: SmokeCase) -> dict[str, str]:
    return base_row(
        run_at=run_at,
        case=case,
        execute_requested=False,
        status="dry_run",
        required_fields_present="not_run",
        mode_matched="not_run",
        validator_marker="not_run",
        sensitive_field_detected="not_run",
        error_summary="Run with --execute to call real service endpoints.",
    )


def base_row(
    *,
    run_at: str,
    case: SmokeCase,
    execute_requested: bool,
    status: str,
    http_status: str = "",
    latency_ms: str = "",
    required_fields_present: str = "",
    refused: str = "",
    citation_count: str = "",
    actual_mode: str = "",
    mode_matched: str = "",
    validator_marker: str = "",
    sensitive_field_detected: str = "",
    error_summary: str = "",
) -> dict[str, str]:
    return {
        "run_at": run_at,
        "case_id": case.case_id,
        "endpoint": case.endpoint,
        "method": case.method,
        "execute_requested": str(execute_requested).lower(),
        "auth_required": str(case.auth_required).lower(),
        "status": status,
        "http_status": http_status,
        "latency_ms": latency_ms,
        "required_fields_present": required_fields_present,
        "refused": refused,
        "citation_count": citation_count,
        "expected_mode": case.expected_mode or "",
        "actual_mode": actual_mode,
        "mode_matched": mode_matched,
        "validator_marker": validator_marker,
        "sensitive_field_detected": sensitive_field_detected,
        "error_summary": sanitize_text(error_summary, limit=240),
    }


def parse_json_body(body: str) -> dict[str, Any] | list[Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, (dict, list)) else {}


def parse_sse_events(body: str) -> dict[str, Any]:
    events: dict[str, Any] = {}
    current_event: str | None = None
    current_data: list[str] = []
    for line in body.splitlines():
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
            current_data = []
            continue
        if line.startswith("data:"):
            current_data.append(line.split(":", 1)[1].strip())
            continue
        if line.strip() == "" and current_event:
            events[current_event] = decode_event_data("".join(current_data))
            current_event = None
            current_data = []
    if current_event:
        events[current_event] = decode_event_data("".join(current_data))
    return events


def decode_event_data(data: str) -> Any:
    if not data:
        return {}
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return data


def required_fields_present(payload: dict[str, Any] | list[Any], fields: Sequence[str]) -> bool:
    if isinstance(payload, dict):
        return all(field in payload for field in fields)
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return all(field in payload[0] for field in fields)
    return not fields


def contains_validator_marker(text: str) -> bool:
    normalized = text.casefold()
    return any(marker in normalized for marker in VALIDATOR_MARKERS)


def contains_sensitive_marker(text: str) -> bool:
    return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)


def failure_summary(
    http_status: int,
    expected_http_statuses: Sequence[int],
    required_present: bool,
    mode_matched: bool,
    validator_marker: bool,
    sensitive: bool,
) -> str:
    failures: list[str] = []
    if http_status not in expected_http_statuses:
        expected = "|".join(str(status) for status in expected_http_statuses)
        failures.append(f"http_status={http_status};expected={expected}")
    if not required_present:
        failures.append("required_fields_missing")
    if not mode_matched:
        failures.append("mode_mismatch")
    if validator_marker:
        failures.append("validator_marker_detected")
    if sensitive:
        failures.append("sensitive_field_detected")
    return "; ".join(failures)


def extract_access_token(case: SmokeCase, result: HttpResult) -> str:
    if case.case_id != "auth_login_smoke_user" or result.status_code != 200:
        return ""
    payload = parse_json_body(result.text)
    if not isinstance(payload, dict):
        return ""
    token = payload.get("access_token")
    return token if isinstance(token, str) else ""


def sanitize_text(value: str, *, limit: int = 500) -> str:
    sanitized = " ".join((value or "").split())
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    for term in ["raw_response", "Authorization", "Bearer", "reasoning_content"]:
        sanitized = re.sub(term, "[REDACTED]", sanitized, flags=re.IGNORECASE)
    if len(sanitized) <= limit:
        return sanitized
    return f"{sanitized[: limit - 3]}..."


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SMOKE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
