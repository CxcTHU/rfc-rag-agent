from __future__ import annotations

import contextvars
import json
import os
import time
from pathlib import Path
from typing import Any

from app.core.structured_logging import sanitize_log_value


DEFAULT_TRACE_PATH = Path("data/logs/request_traces.jsonl")
MAX_EVENTS_PER_TRACE = 80

request_trace_var: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "request_trace",
    default=None,
)


def start_request_trace(
    *,
    request_id: str,
    method: str,
    path: str,
) -> contextvars.Token[dict[str, Any] | None]:
    trace = {
        "request_id": request_id,
        "method": method,
        "path": path,
        "started_at": time.time(),
        "events": [],
    }
    return request_trace_var.set(trace)


def record_request_event(event: str, **fields: object) -> None:
    trace = request_trace_var.get()
    if trace is None:
        return
    events = trace.setdefault("events", [])
    if not isinstance(events, list) or len(events) >= MAX_EVENTS_PER_TRACE:
        return
    events.append(
        {
            "event": event,
            "ts_ms": round((time.time() - float(trace["started_at"])) * 1000.0, 3),
            "fields": sanitize_log_value(fields),
        }
    )


def finish_request_trace(
    *,
    status_code: int,
    latency_ms: float,
    error_type: str | None = None,
    trace_path: Path | None = None,
) -> dict[str, Any] | None:
    trace = request_trace_var.get()
    if trace is None:
        return None

    events = trace.get("events", [])
    payload = {
        "request_id": trace["request_id"],
        "method": trace["method"],
        "path": trace["path"],
        "status_code": status_code,
        "latency_ms": round(float(latency_ms), 3),
        "error_type": error_type,
        "event_count": len(events) if isinstance(events, list) else 0,
        "events": events if isinstance(events, list) else [],
    }
    safe_payload = sanitize_log_value(payload)
    write_trace_line(trace_path or configured_trace_path(), safe_payload)
    return safe_payload


def reset_request_trace(token: contextvars.Token[dict[str, Any] | None]) -> None:
    request_trace_var.reset(token)


def configured_trace_path() -> Path:
    return Path(os.getenv("REQUEST_TRACE_PATH", str(DEFAULT_TRACE_PATH)))


def write_trace_line(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as file:
        file.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
