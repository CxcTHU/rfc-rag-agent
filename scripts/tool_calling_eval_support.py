from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.services.generation.chat_model import (
    ChatModelProvider,
    create_chat_model_provider,
)


SENSITIVE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"Authorization:\s*[^\s]+", re.IGNORECASE),
)


def build_tool_calling_provider(settings: Any) -> ChatModelProvider:
    provider_name = (
        settings.runtime_identity_model_provider
        or settings.planner_chat_model_provider
    )
    model_name = (
        settings.runtime_identity_model_name
        or settings.planner_chat_model_name
    )
    if not provider_name.strip() or not model_name.strip():
        raise ValueError("a tool-calling runtime model is required for --execute")
    return create_chat_model_provider(
        provider_name=provider_name,
        model_name=model_name,
        api_key=(
            settings.runtime_identity_model_api_key
            or settings.planner_chat_model_api_key
        ),
        base_url=(
            settings.runtime_identity_model_base_url
            or settings.planner_chat_model_base_url
        ),
        temperature=settings.runtime_identity_model_temperature,
        timeout_seconds=settings.runtime_identity_model_timeout_seconds,
        max_attempts=1,
    )


@dataclass(frozen=True)
class OpenAICompatibleJudgeClient:
    provider: str
    model: str
    api_key: str
    base_url: str
    timeout_seconds: float = 60.0
    urlopen_func: Any = urllib.request.urlopen

    def judge(self, payload: Mapping[str, object]) -> dict[str, str]:
        try:
            with self.urlopen_func(
                self._build_request(payload),
                timeout=self.timeout_seconds,
            ) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"judge request failed with HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"judge request failed: {sanitize_text(str(exc.reason))}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("judge response was not valid JSON") from exc
        return parse_judge_payload(parse_openai_content(response_data))

    def _build_request(self, payload: Mapping[str, object]) -> urllib.request.Request:
        request_payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Judge RAG quality and return only JSON with faithfulness, "
                        "answer_coverage, citation_support, refusal_correctness, "
                        "conciseness, safety_leak_check, risk_level, short_reason, "
                        "and next_action. Scores are 0 to 1. Do not include hidden "
                        "reasoning, credentials, provider metadata, or long source text."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        return urllib.request.Request(
            endpoint_url(self.base_url),
            data=json.dumps(request_payload, ensure_ascii=True).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "rfc-rag-agent/tool-calling-judge",
            },
            method="POST",
        )


def source_summary(source: Any) -> dict[str, object]:
    return {
        "source_id": getattr(source, "source_id", ""),
        "title": truncate_text(getattr(source, "title", ""), 120),
        "source_type": getattr(source, "source_type", ""),
        "score": getattr(source, "score", ""),
        "evidence_snippet": sanitize_text(
            getattr(source, "content", "") or "",
            limit=220,
        ),
    }


def parse_openai_content(response_data: Mapping[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("judge response did not include choices")
    message = choices[0].get("message") if isinstance(choices[0], Mapping) else None
    if not isinstance(message, Mapping):
        raise RuntimeError("judge response did not include message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("judge response content is empty")
    return content.strip()


def parse_judge_payload(content: str) -> dict[str, str]:
    payload = json.loads(strip_json_fence(content))
    return {
        "faithfulness": format_score(payload.get("faithfulness")),
        "answer_coverage": format_score(payload.get("answer_coverage")),
        "citation_support": format_score(payload.get("citation_support")),
        "refusal_correctness": format_score(payload.get("refusal_correctness")),
        "conciseness": format_score(payload.get("conciseness")),
        "safety_leak_check": format_score(payload.get("safety_leak_check")),
        "risk_level": normalize_risk(payload.get("risk_level")),
        "short_reason": sanitize_text(str(payload.get("short_reason", "")), limit=300),
        "next_action": sanitize_text(str(payload.get("next_action", "")), limit=240),
    }


def strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def format_score(value: Any) -> str:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("judge score is missing or not numeric") from exc
    return f"{max(0.0, min(1.0, numeric_value)):.3f}"


def normalize_risk(value: Any) -> str:
    risk = str(value or "").strip().lower()
    return risk if risk in {"high", "medium", "low"} else "medium"


def endpoint_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/chat/completions") else f"{normalized}/chat/completions"


def truncate_text(value: str, limit: int) -> str:
    normalized = " ".join((value or "").split())
    return normalized if len(normalized) <= limit else f"{normalized[: limit - 3]}..."


def sanitize_text(value: str, *, limit: int = 500) -> str:
    sanitized = " ".join((value or "").split())
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    for term in ("raw_response", "Authorization", "Bearer", "reasoning_content"):
        sanitized = re.sub(term, "[REDACTED]", sanitized, flags=re.IGNORECASE)
    return truncate_text(sanitized, limit)
