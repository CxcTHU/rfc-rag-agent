import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.structured_logging import JsonLogFormatter, log_event, safe_text_summary
from app.main import create_app


ROOT = Path(__file__).resolve().parents[1]


def test_json_log_formatter_outputs_structured_fields_and_redacts_sensitive_data() -> None:
    logger = logging.getLogger("test.stage39.logging")
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn=__file__,
        lno=1,
        msg="agent_event",
        args=(),
        exc_info=None,
        extra={
            "request_id": "req-123",
            "structured": {
                "method": "POST",
                "path": "/agent/query",
                "api_key": "sk-secret",
                "Authorization": "Bearer secret",
                "raw_response": {"body": "sensitive"},
                "question_summary": "堆石混凝土施工质量如何控制？",
            },
        },
    )

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["event"] == "agent_event"
    assert payload["request_id"] == "req-123"
    assert payload["method"] == "POST"
    assert payload["path"] == "/agent/query"
    assert payload["api_key"] == "[redacted]"
    assert payload["Authorization"] == "[redacted]"
    assert payload["raw_response"] == "[redacted]"
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "sk-secret" not in serialized
    assert "Bearer secret" not in serialized


def test_safe_text_summary_truncates_long_user_text() -> None:
    long_question = "堆石混凝土施工质量控制" * 20

    summary = safe_text_summary(long_question, limit=24)

    assert len(summary) <= 24
    assert summary.endswith("…")
    assert summary != long_question


def test_request_middleware_emits_json_request_log(caplog) -> None:
    client = TestClient(create_app())

    with caplog.at_level(logging.INFO, logger="rfc_rag_agent.request"):
        response = client.get("/health", headers={"X-Request-ID": "stage39-test"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "stage39-test"
    records = [
        record
        for record in caplog.records
        if record.name == "rfc_rag_agent.request"
        and record.getMessage() == "request_completed"
    ]
    assert records
    structured = records[-1].structured
    assert structured["method"] == "GET"
    assert structured["path"] == "/health"
    assert structured["status_code"] == 200
    assert "latency_ms" in structured
    assert "authorization" not in json.dumps(structured).casefold()


def test_agent_logging_contract_uses_safe_events_and_not_sensitive_fields() -> None:
    agent_api = (ROOT / "app" / "api" / "agent.py").read_text(encoding="utf-8")
    tool_calling = (
        ROOT / "app" / "services" / "agent" / "tool_calling_service.py"
    ).read_text(encoding="utf-8")
    tool_executor = (
        ROOT / "app" / "services" / "agent" / "tool_executor.py"
    ).read_text(encoding="utf-8")
    combined = agent_api + "\n" + tool_calling + "\n" + tool_executor

    for event in [
        "query_received",
        "tool_call_executed",
        "answer_generated",
        "refusal_triggered",
    ]:
        assert event in combined

    assert "safe_text_summary" in combined
    assert "question_summary" in combined
    assert "log_event(" in combined
    log_event_lines = [
        line for line in combined.splitlines() if "log_event(" in line or "raw_response=" in line
    ]
    assert "api_key=" not in "\n".join(log_event_lines)
    assert "reasoning_content=" not in "\n".join(log_event_lines)
