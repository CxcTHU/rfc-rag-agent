from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from collections.abc import Mapping
from typing import Any


request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)

SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "bearer",
    "token",
    "raw_response",
    "reasoning_content",
    "hidden_thought",
    "password",
    "secret",
)
MAX_LOG_TEXT_LENGTH = 160


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or request_id_var.get()
        if request_id:
            payload["request_id"] = str(request_id)
        structured = getattr(record, "structured", None)
        if isinstance(structured, Mapping):
            payload.update(sanitize_log_value(structured))
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_structured_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if getattr(root, "_rfc_rag_structured_logging", False):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root.handlers = [handler]
    root.setLevel(level)
    setattr(root, "_rfc_rag_structured_logging", True)


def new_request_id() -> str:
    return uuid.uuid4().hex


def set_request_id(request_id: str | None) -> contextvars.Token[str | None]:
    return request_id_var.set(request_id)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    request_id_var.reset(token)


def log_event(
    logger: logging.Logger,
    event: str,
    **fields: object,
) -> None:
    safe_fields = sanitize_log_value(fields)
    logger.info(event, extra={"structured": safe_fields})
    try:
        from app.core.request_logger import record_request_event

        if isinstance(safe_fields, Mapping):
            record_request_event(event, **safe_fields)
    except Exception:
        # Request traces are diagnostic best-effort output and must never break
        # the application path.
        return


def safe_text_summary(value: str | None, *, limit: int = MAX_LOG_TEXT_LENGTH) -> str:
    normalized = " ".join((value or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1]}…"


def sanitize_log_value(value: object) -> object:
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            if is_sensitive_key(key_text):
                sanitized[key_text] = "[redacted]"
                continue
            sanitized[key_text] = sanitize_log_value(item)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [sanitize_log_value(item) for item in value[:20]]
    if isinstance(value, str):
        return safe_text_summary(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return safe_text_summary(str(value))


def is_sensitive_key(key: str) -> bool:
    normalized = key.casefold()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
