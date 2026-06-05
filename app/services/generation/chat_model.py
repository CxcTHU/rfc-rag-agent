import json
import re
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol


ChatRole = Literal["system", "user", "assistant"]
VALID_CHAT_ROLES = {"system", "user", "assistant"}
SOURCE_MARKER_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole
    content: str

    def __post_init__(self) -> None:
        if self.role not in VALID_CHAT_ROLES:
            raise ValueError(f"Unsupported chat role: {self.role}")
        if not self.content.strip():
            raise ValueError("chat message content must not be empty")


@dataclass(frozen=True)
class ChatModelResult:
    answer: str
    provider: str
    model_name: str
    raw_response: dict[str, Any] | None = None


class ChatModelProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        """Generate one answer from ordered chat messages."""


@dataclass(frozen=True)
class DeterministicChatModelProvider:
    """Small local chat provider for tests and offline development."""

    model_name: str = "rule-based-chat-v1"
    provider_name: str = "deterministic"

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        if not messages:
            raise ValueError("messages must not be empty")

        question = extract_question(latest_user_message(messages))
        source_ids = extract_source_ids(messages)
        if source_ids:
            first_source = source_ids[0]
            answer = (
                f"Deterministic answer based on source [{first_source}]: "
                f"{question}"
            )
        else:
            answer = "No reliable context was provided for this question."

        return ChatModelResult(
            answer=answer,
            provider=self.provider_name,
            model_name=self.model_name,
            raw_response=None,
        )


@dataclass(frozen=True)
class OpenAICompatibleChatModelProvider:
    model_name: str
    api_key: str
    base_url: str
    temperature: float = 0.2
    timeout_seconds: float = 30.0
    provider_name: str = "openai-compatible"

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if not self.api_key.strip():
            raise ValueError("api_key must not be empty")
        if not self.base_url.strip():
            raise ValueError("base_url must not be empty")

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        if not messages:
            raise ValueError("messages must not be empty")

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "temperature": self.temperature,
        }
        request = urllib.request.Request(
            self._endpoint_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Chat model request failed with HTTP {exc.code}: {error_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Chat model request failed: {exc.reason}") from exc

        answer = parse_openai_compatible_answer(response_data)
        return ChatModelResult(
            answer=answer,
            provider=self.provider_name,
            model_name=self.model_name,
            raw_response=response_data,
        )

    def _endpoint_url(self) -> str:
        normalized_base_url = self.base_url.rstrip("/")
        if normalized_base_url.endswith("/chat/completions"):
            return normalized_base_url
        return f"{normalized_base_url}/chat/completions"


def latest_user_message(messages: Sequence[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content.strip()
    raise ValueError("messages must include at least one user message")


def extract_question(user_message: str) -> str:
    stripped = user_message.strip()
    marker = "Question:"
    context_marker = "\n\nContext:"
    if marker not in stripped:
        return stripped
    question_part = stripped.split(marker, 1)[1]
    if context_marker in question_part:
        question_part = question_part.split(context_marker, 1)[0]
    return question_part.strip() or stripped


def extract_source_ids(messages: Sequence[ChatMessage]) -> list[int]:
    source_ids: list[int] = []
    for message in messages:
        for match in SOURCE_MARKER_RE.finditer(message.content):
            source_id = int(match.group(1))
            if source_id not in source_ids:
                source_ids.append(source_id)
    return source_ids


def parse_openai_compatible_answer(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Chat model response did not include choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("Chat model response choice is not an object")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("Chat model response choice did not include a message")

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Chat model response message content is empty")
    return content.strip()


def create_chat_model_provider(
    provider_name: str | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.2,
    timeout_seconds: float = 30.0,
) -> ChatModelProvider:
    provider = (provider_name or "deterministic").strip().casefold()
    if provider in {"", "deterministic", "fake", "local"}:
        return DeterministicChatModelProvider(
            model_name=(model_name or "rule-based-chat-v1").strip()
            or "rule-based-chat-v1"
        )
    if provider in {"openai-compatible", "openai", "compatible", "domestic"}:
        return OpenAICompatibleChatModelProvider(
            model_name=(model_name or "").strip(),
            api_key=(api_key or "").strip(),
            base_url=(base_url or "").strip(),
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"Unsupported chat model provider: {provider_name}")
