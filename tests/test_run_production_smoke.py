import json
from pathlib import Path

from scripts.run_production_smoke import (
    SMOKE_FIELDS,
    HttpResult,
    SmokeCase,
    contains_sensitive_marker,
    contains_validator_marker,
    evaluate_http_result,
    parse_sse_events,
    required_fields_present,
    run_smoke,
    smoke_cases,
    write_csv,
)


def test_stage36_production_smoke_dry_run_rows_are_safe() -> None:
    rows = run_smoke(
        base_url="http://127.0.0.1:8000",
        execute=False,
        timeout_seconds=1,
        urlopen_func=lambda *args, **kwargs: None,
    )

    assert len(rows) == 14
    assert {row["status"] for row in rows} == {"dry_run"}
    assert all(row["execute_requested"] == "false" for row in rows)
    assert all(set(row) == set(SMOKE_FIELDS) for row in rows)
    assert all("Bearer" not in row["error_summary"] for row in rows)
    assert all(row["mode_matched"] == "not_run" for row in rows)
    assert "agent_query_default_tool_calling" in {row["case_id"] for row in rows}
    assert "chat" in {row["case_id"] for row in rows}
    assert "frontend_home" in {row["case_id"] for row in rows}
    assert "image_asset" in {row["case_id"] for row in rows}
    assert "agent_query_tool_calling" in {row["case_id"] for row in rows}
    assert "agent_query_stream_default_tool_calling" in {row["case_id"] for row in rows}
    assert "agent_query_tool_calling_stream" in {row["case_id"] for row in rows}


def test_stage37_production_smoke_covers_tool_calling_agent() -> None:
    cases = {case.case_id: case for case in smoke_cases()}

    assert "mode" not in cases["agent_query_default_tool_calling"].payload
    assert cases["agent_query_default_tool_calling"].expected_mode == "tool_calling_agent"
    assert cases["agent_query_tool_calling"].payload["mode"] == "tool_calling_agent"
    assert cases["agent_query_tool_calling"].expected_mode == "tool_calling_agent"
    assert "mode" not in cases["agent_query_stream_default_tool_calling"].payload
    assert (
        cases["agent_query_stream_default_tool_calling"].expected_mode
        == "tool_calling_agent"
    )
    assert (
        cases["agent_query_tool_calling_stream"].payload["mode"]
        == "tool_calling_agent"
    )
    assert cases["agent_query_tool_calling_stream"].expected_mode == "tool_calling_agent"
    assert cases["agent_query_tool_calling_stream"].stream is True
    assert cases["chat"].endpoint == "/chat"
    assert cases["chat"].auth_required is False
    assert cases["frontend_home"].endpoint == "/"
    assert cases["image_asset"].endpoint.startswith("/assets/images/")


def test_phase55_auth_enabled_smoke_uses_token_in_memory_only() -> None:
    class FakeResponse:
        def __init__(self, status: int, body: str) -> None:
            self.status = status
            self._body = body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return self._body

    seen_authorized_paths: list[str] = []

    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202 - urllib test double
        path = request.full_url.removeprefix("http://127.0.0.1:8000")
        headers = dict(request.header_items())
        body = json.loads(request.data.decode("utf-8")) if request.data else {}
        requested_mode = body.get("mode") or "tool_calling_agent"
        if body.get("question") == "What model are you using?":
            requested_mode = "meta"
        if headers.get("Authorization") == "Bearer token-secret-value":
            seen_authorized_paths.append(path)
        if path == "/agent/query" and "Authorization" not in headers:
            return FakeResponse(401, '{"detail":"authentication required"}')
        if path == "/auth/register":
            return FakeResponse(
                200,
                '{"id":1,"username":"phase55_smoke","email":"phase55_smoke@example.com","is_active":true,"created_at":"2026-06-26T00:00:00"}',
            )
        if path == "/auth/login":
            return FakeResponse(
                200,
                '{"access_token":"token-secret-value","token_type":"bearer","expires_in":3600,"user":{"id":1,"username":"phase55_smoke","email":"phase55_smoke@example.com","is_active":true,"created_at":"2026-06-26T00:00:00"}}',
            )
        if path == "/auth/me":
            return FakeResponse(
                200,
                '{"id":1,"username":"phase55_smoke","email":"phase55_smoke@example.com","is_active":true,"created_at":"2026-06-26T00:00:00"}',
            )
        if path == "/health":
            return FakeResponse(200, '{"status":"ok"}')
        if path == "/":
            return FakeResponse(200, "<html>ok</html>")
        if path == "/assets/images/1059/page10_img1.png":
            return FakeResponse(200, "image-bytes")
        if path == "/quality-report":
            return FakeResponse(200, "<html>ok</html>")
        if path == "/quality-report/data.json":
            return FakeResponse(200, '[{"run_id":"stage30","dimension":"overall","score":"91.52","status":"pass"}]')
        if path == "/chat":
            return FakeResponse(
                200,
                '{"answer":"ok","refused":false,"citations":[],"sources":[]}',
            )
        if path == "/agent/query/stream":
            return FakeResponse(
                200,
                f'event: metadata\ndata: {{"answer":"ok","refused":false,"citations":[],"sources":[],"mode":"{requested_mode}"}}\n\n'
                "event: done\ndata: {}\n\n",
            )
        if path == "/agent/query":
            return FakeResponse(
                200,
                f'{{"answer":"ok","refused":false,"citations":[],"sources":[],"mode":"{requested_mode}"}}',
            )
        raise AssertionError(path)

    rows = run_smoke(
        base_url="http://127.0.0.1:8000",
        execute=True,
        timeout_seconds=1,
        auth_enabled=True,
        urlopen_func=fake_urlopen,
    )

    rows_by_id = {row["case_id"]: row for row in rows}

    assert rows_by_id["agent_query_unauthenticated_401"]["status"] == "passed"
    assert rows_by_id["auth_login_smoke_user"]["status"] == "passed"
    assert rows_by_id["auth_me"]["status"] == "passed"
    assert "/auth/me" in seen_authorized_paths
    assert "/agent/query" in seen_authorized_paths
    assert all("token-secret-value" not in value for row in rows for value in row.values())


def test_stage36_production_smoke_evaluates_agent_payload_without_body_leak() -> None:
    case = SmokeCase(
        case_id="agent",
        method="POST",
        endpoint="/agent/query",
        required_fields=("answer", "refused", "citations", "sources", "mode"),
        expected_mode="react_agent",
    )
    result = HttpResult(
        status_code=200,
        text=(
            '{"answer":"ok","refused":false,"citations":[1,2],'
            '"sources":[],"mode":"react_agent"}'
        ),
        latency_ms=12.3456,
    )

    row = evaluate_http_result("2026-06-15T00:00:00+00:00", case, result)

    assert row["status"] == "passed"
    assert row["required_fields_present"] == "true"
    assert row["refused"] == "false"
    assert row["citation_count"] == "2"
    assert row["actual_mode"] == "react_agent"
    assert row["mode_matched"] == "true"
    assert row["latency_ms"] == "12.346"
    assert "ok" not in row.values()


def test_stage36_production_smoke_detects_sensitive_and_validator_markers() -> None:
    assert contains_sensitive_marker("Authorization: secret")
    assert contains_sensitive_marker("Bearer abcdefghijklmnopqrstuvwxyz.123")
    assert contains_sensitive_marker("reasoning_content should not appear")
    assert not contains_sensitive_marker("I do not expose bearer tokens or raw provider responses.")
    assert contains_validator_marker("citation_validator removed this sentence")


def test_stage36_production_smoke_accepts_quality_report_row_lists() -> None:
    assert required_fields_present(
        [{"run_id": "stage30", "dimension": "retrieval", "score": "1", "status": "strong"}],
        ("run_id", "dimension", "score", "status"),
    )


def test_stage36_production_smoke_parses_sse_metadata_and_done() -> None:
    body = (
        'event: token\ndata: {"text":"hi"}\n\n'
        'event: metadata\ndata: {"answer":"hi","refused":false,"citations":[1],"sources":[],"mode":"react_agent"}\n\n'
        "event: done\ndata: {}\n\n"
    )
    case = SmokeCase(
        case_id="stream",
        method="POST",
        endpoint="/agent/query/stream",
        required_fields=("metadata", "done"),
        stream=True,
        expected_mode="react_agent",
    )

    parsed = parse_sse_events(body)
    row = evaluate_http_result(
        "2026-06-15T00:00:00+00:00",
        case,
        HttpResult(status_code=200, text=body, latency_ms=1.0),
    )

    assert parsed["metadata"]["refused"] is False
    assert row["status"] == "passed"
    assert row["citation_count"] == "1"
    assert row["actual_mode"] == "react_agent"
    assert row["mode_matched"] == "true"


def test_stage38_production_smoke_fails_mode_mismatch() -> None:
    case = SmokeCase(
        case_id="default-mode",
        method="POST",
        endpoint="/agent/query",
        required_fields=("answer", "refused", "mode"),
        expected_mode="tool_calling_agent",
    )
    result = HttpResult(
        status_code=200,
        text='{"answer":"ok","refused":false,"mode":"default"}',
        latency_ms=1.0,
    )

    row = evaluate_http_result("2026-06-15T00:00:00+00:00", case, result)

    assert row["status"] == "failed"
    assert row["actual_mode"] == "default"
    assert row["mode_matched"] == "false"
    assert "mode_mismatch" in row["error_summary"]


def test_stage36_production_smoke_writes_expected_csv(tmp_path: Path) -> None:
    path = tmp_path / "smoke.csv"
    rows = run_smoke(
        base_url="http://127.0.0.1:8000",
        execute=False,
        timeout_seconds=1,
        urlopen_func=lambda *args, **kwargs: None,
    )

    write_csv(path, rows)
    content = path.read_text(encoding="utf-8")

    assert "case_id,endpoint,method" in content
    assert "raw_response" not in content
    assert "reasoning_content" not in content
