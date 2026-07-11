from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FORBIDDEN_SUBSTRINGS = (
    "api_key",
    "authorization",
    "bearer ",
    "raw_response",
    "reasoning_content",
    "jwt_secret",
)


@dataclass(frozen=True)
class E2ECase:
    case_id: str
    method: str
    path: str
    payload: dict[str, Any] | None
    expected_status: int
    expectation: str


def phase61_cases() -> list[E2ECase]:
    return [
        E2ECase(
            case_id="health_public_liveness",
            method="GET",
            path="/health",
            payload=None,
            expected_status=200,
            expectation="health status is ok",
        ),
        E2ECase(
            case_id="frontend_react_entry",
            method="GET",
            path="/",
            payload=None,
            expected_status=200,
            expectation="React frontend shell is served",
        ),
        E2ECase(
            case_id="hybrid_search_domain_query",
            method="POST",
            path="/search/hybrid",
            payload={"query": "堆石混凝土 施工 质量 控制", "top_k": 3},
            expected_status=200,
            expectation="hybrid search returns a bounded result envelope",
        ),
        E2ECase(
            case_id="agent_default_domain_query",
            method="POST",
            path="/agent/query",
            payload={
                "question": "请基于资料说明堆石混凝土施工质量控制通常关注哪些指标。",
                "mode": "tool_calling_agent",
                "top_k": 4,
                "max_tool_calls": 2,
            },
            expected_status=200,
            expectation="default tool-calling Agent returns answer/refusal envelope with metadata",
        ),
        E2ECase(
            case_id="agent_table_intent_query",
            method="POST",
            path="/agent/query",
            payload={
                "question": "请查找资料中的表格证据，说明堆石混凝土相关配合比或性能指标如何呈现。",
                "mode": "tool_calling_agent",
                "top_k": 4,
                "max_tool_calls": 3,
            },
            expected_status=200,
            expectation="table-intent Agent request completes without server error",
        ),
        E2ECase(
            case_id="agent_off_topic_refusal",
            method="POST",
            path="/agent/query",
            payload={
                "question": "请告诉我今天纽约天气和股票走势。",
                "mode": "tool_calling_agent",
                "top_k": 3,
                "max_tool_calls": 2,
            },
            expected_status=200,
            expectation="off-topic query is handled as a safe Agent envelope",
        ),
        E2ECase(
            case_id="input_limit_guard",
            method="POST",
            path="/agent/query",
            payload={
                "question": "x" * 4100,
                "mode": "tool_calling_agent",
            },
            expected_status=422,
            expectation="oversized Agent question is rejected by schema validation",
        ),
    ]


def request_json(base_url: str, case: E2ECase, timeout_seconds: int) -> tuple[int, Any, float, str | None]:
    url = base_url.rstrip("/") + case.path
    body = None
    headers = {"Accept": "application/json"}
    if case.payload is not None:
        body = json.dumps(case.payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = Request(url, data=body, method=case.method, headers=headers)
    started = time.perf_counter()
    try:
        with urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            parsed = parse_body(raw, response.headers.get("content-type", ""))
            status = response.status
            if case.case_id == "frontend_react_entry":
                legacy_req = Request(base_url.rstrip("/") + "/old", method="GET", headers=headers)
                with urlopen(legacy_req, timeout=timeout_seconds) as legacy_response:
                    legacy_raw = legacy_response.read()
                    legacy_parsed = parse_body(
                        legacy_raw,
                        legacy_response.headers.get("content-type", ""),
                    )
                    if isinstance(parsed, dict) and isinstance(legacy_parsed, dict):
                        parsed["_legacy_text"] = legacy_parsed.get("_text", "")
                    if legacy_response.status != 200:
                        status = legacy_response.status
                elapsed_ms = (time.perf_counter() - started) * 1000.0
            return status, parsed, elapsed_ms, None
    except HTTPError as exc:
        raw = exc.read()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return exc.code, parse_body(raw, exc.headers.get("content-type", "")), elapsed_ms, None
    except URLError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return 0, None, elapsed_ms, exc.reason.__class__.__name__


def parse_body(raw: bytes, content_type: str) -> Any:
    text = raw.decode("utf-8", errors="replace")
    if "application/json" in content_type:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"_unparsed": text[:500]}
    return {"_text": text[:1000]}


def evaluate_case(case: E2ECase, status: int, body: Any, error_type: str | None) -> tuple[bool, str, dict[str, Any]]:
    checks: dict[str, Any] = {
        "status": status,
        "error_type": error_type or "",
        "result_count": 0,
        "tool_call_count": 0,
        "source_count": 0,
        "refused": "",
        "has_latency_trace": False,
        "answer_preview": "",
    }
    if status != case.expected_status:
        return False, f"expected_status={case.expected_status} actual={status}", checks
    serialized = json.dumps(body, ensure_ascii=False).lower()
    leaked = [item for item in FORBIDDEN_SUBSTRINGS if item in serialized]
    if leaked:
        return False, "forbidden substrings: " + ",".join(leaked), checks

    if isinstance(body, dict):
        results = body.get("results")
        if isinstance(results, list):
            checks["result_count"] = len(results)
        tool_calls = body.get("tool_calls")
        if isinstance(tool_calls, list):
            checks["tool_call_count"] = len(tool_calls)
        sources = body.get("sources")
        if isinstance(sources, list):
            checks["source_count"] = len(sources)
        if "refused" in body:
            checks["refused"] = str(bool(body.get("refused"))).lower()
        latency_trace = body.get("latency_trace")
        checks["has_latency_trace"] = isinstance(latency_trace, dict)
        answer = body.get("answer")
        if isinstance(answer, str):
            checks["answer_preview"] = answer[:120].replace("\n", " ")

    if case.case_id == "health_public_liveness":
        ok = isinstance(body, dict) and body.get("status") == "ok"
        return ok, "health status ok" if ok else "health status is not ok", checks
    if case.case_id == "frontend_react_entry":
        text = body.get("_text", "") if isinstance(body, dict) else ""
        legacy_text = body.get("_legacy_text", "") if isinstance(body, dict) else ""
        ok = (
            'id="root"' in text
            and "/assets/" in text
            and "data-workspace-band" in legacy_text
            and "/static/app.js" in legacy_text
        )
        return ok, "frontend shell served" if ok else "frontend shell markers missing", checks
    if case.case_id == "input_limit_guard":
        return True, "schema rejected oversized input", checks
    if case.path == "/search/hybrid":
        ok = isinstance(body, dict) and isinstance(body.get("results"), list)
        return ok, "hybrid envelope ok" if ok else "hybrid results missing", checks
    if case.path == "/agent/query":
        ok = isinstance(body, dict) and "answer" in body and "refused" in body and "mode" in body
        return ok, "agent envelope ok" if ok else "agent envelope missing fields", checks
    return True, "status matched", checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 61 local E2E smoke cases.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default="data/evaluation/phase61_e2e_eval.csv")
    parser.add_argument("--json-out", default="data/evaluation/phase61_e2e_eval.json")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for case in phase61_cases():
        status, body, elapsed_ms, error_type = request_json(args.base_url, case, args.timeout_seconds)
        passed, reason, checks = evaluate_case(case, status, body, error_type)
        row = {
            "case_id": case.case_id,
            "method": case.method,
            "path": case.path,
            "expected_status": case.expected_status,
            "actual_status": status,
            "passed": passed,
            "reason": reason,
            "elapsed_ms": round(elapsed_ms, 3),
            "expectation": case.expectation,
            **checks,
        }
        rows.append(row)
        print(
            f"{case.case_id}: passed={passed} status={status} "
            f"elapsed_ms={row['elapsed_ms']} reason={reason}"
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [row for row in rows if not row["passed"]]
    print(f"summary: cases={len(rows)} passed={len(rows) - len(failed)} failed={len(failed)}")
    print(f"csv={out_path}")
    print(f"json={json_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
