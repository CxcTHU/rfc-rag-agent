from __future__ import annotations

import argparse
import csv
import json
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path("data/evaluation/launch_chinese_smoke_results.csv")
DEFAULT_PASSWORD = "local-smoke-only-password"


@dataclass(frozen=True)
class LaunchSmokeCase:
    case_id: str
    question_escape: str
    history_escapes: tuple[str, ...] = field(default_factory=tuple)
    expect_refused: bool = False
    expect_source_type: str = ""


CASES = (
    LaunchSmokeCase(
        "advantages_1",
        r"\u5806\u77f3\u6df7\u51dd\u571f\u6709\u54ea\u4e9b\u4f18\u70b9\uff1f",
    ),
    LaunchSmokeCase(
        "advantages_2",
        r"\u5806\u77f3\u6df7\u51dd\u571f\u7684\u4f18\u52bf\u4e4b\u5904\uff1f",
    ),
    LaunchSmokeCase(
        "disadvantages",
        r"\u5806\u77f3\u6df7\u51dd\u571f\u6709\u54ea\u4e9b\u7f3a\u70b9\uff1f",
    ),
    LaunchSmokeCase(
        "crack_causes",
        r"\u5927\u575d\u88c2\u7f1d\u6210\u56e0\u6709\u54ea\u4e9b\uff1f\u8bf7\u8be6\u7ec6\u5217\u51fa\u6765",
    ),
    LaunchSmokeCase(
        "image_followup",
        r"\u6211\u9700\u8981\u56fe\u7247\u652f\u6491",
        history_escapes=(
            r"\u5927\u575d\u88c2\u7f1d\u6210\u56e0\u6709\u54ea\u4e9b\uff1f\u8bf7\u8be6\u7ec6\u5217\u51fa\u6765",
        ),
        expect_source_type="image_description",
    ),
    LaunchSmokeCase(
        "table_evidence",
        r"\u7ed9\u6211\u76f8\u5173\u8868\u683c\u8bc1\u636e",
        history_escapes=(
            r"\u5806\u77f3\u6df7\u51dd\u571f\u6709\u54ea\u4e9b\u4f18\u70b9\uff1f",
        ),
        expect_source_type="table",
    ),
)


FIELDS = (
    "run_at",
    "case_id",
    "status",
    "http_status",
    "latency_ms",
    "refused",
    "refusal_category",
    "citation_count",
    "source_count",
    "tool_call_count",
    "iteration_count",
    "source_types",
    "tool_summaries",
    "error_summary",
)


def main() -> None:
    args = parse_args()
    username = args.smoke_username or f"launch_cn_{uuid.uuid4().hex[:10]}"
    rows = run_smoke(
        base_url=args.base_url.rstrip("/"),
        execute=args.execute,
        auth_enabled=args.auth_enabled,
        username=username,
        password=args.smoke_password,
        timeout_seconds=args.timeout_seconds,
        max_tool_calls=args.max_tool_calls,
        use_stream=args.stream,
    )
    write_csv(Path(args.out), rows)
    failed = [row for row in rows if row["status"] != "passed"] if args.execute else []
    print(f"launch Chinese smoke rows={len(rows)} execute={str(args.execute).lower()} failed={len(failed)}")
    print(f"wrote {args.out}")
    if args.execute and failed:
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch Chinese smoke for deployed RFC-RAG-Agent.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8044")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--timeout-seconds", type=float, default=240.0)
    parser.add_argument("--max-tool-calls", type=int, default=2)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--stream", action="store_true", help="Use /agent/query/stream and parse metadata.")
    parser.add_argument("--auth-enabled", action="store_true")
    parser.add_argument("--smoke-username", default="")
    parser.add_argument("--smoke-password", default=DEFAULT_PASSWORD)
    return parser.parse_args()


def run_smoke(
    *,
    base_url: str,
    execute: bool,
    auth_enabled: bool,
    username: str,
    password: str,
    timeout_seconds: float,
    max_tool_calls: int,
    use_stream: bool,
) -> list[dict[str, str]]:
    token = ""
    if execute and auth_enabled:
        email = f"{username}@example.com"
        request_json(
            base_url,
            "/auth/register",
            {"username": username, "email": email, "password": password},
            timeout_seconds,
            token="",
            allow_statuses={200, 409},
        )
        login_status, login_payload, _latency = request_json(
            base_url,
            "/auth/login",
            {"username_or_email": username, "password": password},
            timeout_seconds,
            token="",
        )
        if login_status == 200:
            token = str(login_payload.get("access_token") or "")

    rows = []
    for case in CASES:
        rows.append(
            run_case(
                base_url=base_url,
                case=case,
                execute=execute,
                timeout_seconds=timeout_seconds,
                token=token,
                max_tool_calls=max_tool_calls,
                use_stream=use_stream,
            )
        )
    return rows


def run_case(
    *,
    base_url: str,
    case: LaunchSmokeCase,
    execute: bool,
    timeout_seconds: float,
    token: str,
    max_tool_calls: int,
    use_stream: bool,
) -> dict[str, str]:
    started = time.time()
    row = base_row(case.case_id)
    if not execute:
        row["status"] = "planned"
        return row

    payload = {
        "question": decode_escape(case.question_escape),
        "top_k": 8,
        "max_tool_calls": max_tool_calls,
        "mode": "tool_calling_agent",
        "history": [decode_escape(item) for item in case.history_escapes],
    }
    try:
        if use_stream:
            http_status, response_payload, latency_ms = request_stream_metadata(
                base_url,
                "/agent/query/stream",
                payload,
                timeout_seconds,
                token,
            )
        else:
            http_status, response_payload, latency_ms = request_json(
                base_url,
                "/agent/query",
                payload,
                timeout_seconds,
                token,
            )
        row.update(row_from_response(case, http_status, response_payload, latency_ms))
    except Exception as exc:  # noqa: BLE001 - smoke reports sanitized failures.
        row["status"] = "failed"
        row["latency_ms"] = str(int((time.time() - started) * 1000))
        row["error_summary"] = sanitize_error(str(exc))
    return row


def row_from_response(
    case: LaunchSmokeCase,
    http_status: int,
    payload: dict[str, Any],
    latency_ms: int,
) -> dict[str, str]:
    source_types = count_source_types(payload.get("sources") or [])
    refused = bool(payload.get("refused"))
    passed = http_status == 200 and refused is case.expect_refused
    if case.expect_source_type:
        passed = passed and source_types.get(case.expect_source_type, 0) > 0
    if not case.expect_refused:
        passed = passed and int_list_count(payload.get("citations")) > 0 and int_list_count(payload.get("sources")) > 0
    return {
        "status": "passed" if passed else "failed",
        "http_status": str(http_status),
        "latency_ms": str(latency_ms),
        "refused": str(refused).lower(),
        "refusal_category": str(payload.get("refusal_category") or ""),
        "citation_count": str(int_list_count(payload.get("citations"))),
        "source_count": str(int_list_count(payload.get("sources"))),
        "tool_call_count": str(int_list_count(payload.get("tool_calls"))),
        "iteration_count": str(payload.get("iteration_count") or 0),
        "source_types": json.dumps(source_types, ensure_ascii=False, sort_keys=True),
        "tool_summaries": json.dumps(tool_summaries(payload), ensure_ascii=False),
        "error_summary": "",
    }


def request_json(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    token: str,
    allow_statuses: set[int] | None = None,
) -> tuple[int, dict[str, Any], int]:
    started = time.time()
    data = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    headers = {"Content-Type": "application/json; charset=utf-8", "User-Agent": "rfc-launch-smoke/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(base_url + path, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.status, json.loads(response.read().decode("utf-8", "replace")), elapsed_ms(started)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        if allow_statuses and exc.code in allow_statuses:
            return exc.code, json.loads(body or "{}"), elapsed_ms(started)
        raise RuntimeError(f"HTTP {exc.code}: {body[:160]}") from exc


def request_stream_metadata(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    token: str,
) -> tuple[int, dict[str, Any], int]:
    started = time.time()
    data = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "text/event-stream",
        "User-Agent": "rfc-launch-smoke/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(base_url + path, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        metadata = parse_stream_metadata(response.read().decode("utf-8", "replace"))
        return response.status, metadata, elapsed_ms(started)


def parse_stream_metadata(text: str) -> dict[str, Any]:
    for raw_event in text.strip().split("\n\n"):
        event_name = ""
        data = "{}"
        for line in raw_event.splitlines():
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data = line.removeprefix("data:").strip()
        if event_name == "metadata":
            return json.loads(data)
        if event_name == "error":
            detail = json.loads(data).get("detail", "stream returned error")
            raise RuntimeError(str(detail))
    raise RuntimeError("stream ended without metadata")


def base_row(case_id: str) -> dict[str, str]:
    return {field: "" for field in FIELDS} | {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "case_id": case_id,
    }


def decode_escape(value: str) -> str:
    return value.encode("ascii").decode("unicode_escape")


def elapsed_ms(started: float) -> int:
    return int((time.time() - started) * 1000)


def int_list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def count_source_types(sources: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in sources:
        key = str(source.get("chunk_type") or source.get("source_type") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def tool_summaries(payload: dict[str, Any]) -> list[str]:
    summaries = []
    for tool_call in payload.get("tool_calls") or []:
        summary = str(tool_call.get("output_summary") or "")
        if summary:
            summaries.append(summary[:220])
    return summaries[:3]


def sanitize_error(value: str) -> str:
    lowered = value.replace("\n", " ").strip()
    for marker in ("api_key", "authorization", "bearer", "token", "password", "secret"):
        lowered = lowered.replace(marker, f"{marker}=<masked>")
    return lowered[:240]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
