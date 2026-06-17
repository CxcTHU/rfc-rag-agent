import json
import logging

from fastapi.testclient import TestClient

from app.core.request_logger import (
    finish_request_trace,
    reset_request_trace,
    start_request_trace,
)
from app.core.structured_logging import log_event
from app.main import create_app


def test_request_trace_writes_sanitized_jsonl(tmp_path) -> None:
    trace_path = tmp_path / "request_traces.jsonl"
    token = start_request_trace(
        request_id="trace-123",
        method="POST",
        path="/agent/query",
    )
    logger = logging.getLogger("test.request.trace")

    log_event(
        logger,
        "provider_call_completed",
        provider="deterministic",
        model="rule-based-chat-v1",
        api_key="sk-secret",
        raw_response={"body": "sensitive"},
        citation_count=2,
    )
    payload = finish_request_trace(
        status_code=200,
        latency_ms=12.3456,
        trace_path=trace_path,
    )
    reset_request_trace(token)

    assert payload is not None
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    written = json.loads(lines[0])
    serialized = json.dumps(written, ensure_ascii=False)
    assert written["request_id"] == "trace-123"
    assert written["status_code"] == 200
    assert written["events"][0]["event"] == "provider_call_completed"
    assert written["events"][0]["fields"]["api_key"] == "[redacted]"
    assert written["events"][0]["fields"]["raw_response"] == "[redacted]"
    assert "sk-secret" not in serialized
    assert "sensitive" not in serialized


def test_request_middleware_writes_trace_with_request_id(tmp_path, monkeypatch) -> None:
    trace_path = tmp_path / "request_traces.jsonl"
    monkeypatch.setenv("REQUEST_TRACE_PATH", str(trace_path))
    client = TestClient(create_app())

    response = client.get("/health", headers={"X-Request-ID": "trace-health"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "trace-health"
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["request_id"] == "trace-health"
    assert rows[-1]["method"] == "GET"
    assert rows[-1]["path"] == "/health"
    assert rows[-1]["status_code"] == 200
    assert any(event["event"] == "request_completed" for event in rows[-1]["events"])
