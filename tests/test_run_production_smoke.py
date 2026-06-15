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
    write_csv,
)


def test_stage36_production_smoke_dry_run_rows_are_safe() -> None:
    rows = run_smoke(
        base_url="http://127.0.0.1:8000",
        execute=False,
        timeout_seconds=1,
        urlopen_func=lambda *args, **kwargs: None,
    )

    assert len(rows) == 7
    assert {row["status"] for row in rows} == {"dry_run"}
    assert all(row["execute_requested"] == "false" for row in rows)
    assert all(set(row) == set(SMOKE_FIELDS) for row in rows)
    assert all("Bearer" not in row["error_summary"] for row in rows)


def test_stage36_production_smoke_evaluates_agent_payload_without_body_leak() -> None:
    case = SmokeCase(
        case_id="agent",
        method="POST",
        endpoint="/agent/query",
        required_fields=("answer", "refused", "citations", "sources", "mode"),
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
