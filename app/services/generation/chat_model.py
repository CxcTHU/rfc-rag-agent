import json
import http.client
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Iterator, Literal, Protocol

from app.services.generation.http_pool import HTTP_JSON_CONNECTION_POOL
from app.services.observability.latency_trace import get_current_latency_trace


ChatRole = Literal["system", "user", "assistant", "tool"]
VALID_CHAT_ROLES = {"system", "user", "assistant", "tool"}
SOURCE_MARKER_RE = re.compile(r"\[(\d+)\]")

# Transient HTTP statuses worth retrying. 4xx client errors (bad key, bad
# request) are excluded because retrying them only wastes quota.
RETRYABLE_HTTP_STATUS = frozenset({429, 500, 502, 503, 504})


class TransientHTTPStatusError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole
    content: str
    tool_call_id: str | None = None
    assistant_tool_calls: "tuple[ChatToolCall, ...] | None" = None

    def __post_init__(self) -> None:
        if self.role not in VALID_CHAT_ROLES:
            raise ValueError(f"Unsupported chat role: {self.role}")
        if not self.content.strip() and not self.assistant_tool_calls:
            raise ValueError("chat message content must not be empty")
        if self.role == "tool" and not (self.tool_call_id or "").strip():
            raise ValueError("tool messages must include tool_call_id")


@dataclass(frozen=True)
class ChatToolFunction:
    name: str
    description: str
    parameters: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("tool function name must not be empty")
        if not self.description.strip():
            raise ValueError("tool function description must not be empty")


@dataclass(frozen=True)
class ChatToolDefinition:
    function: ChatToolFunction
    type: Literal["function"] = "function"


@dataclass(frozen=True)
class ChatToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("tool call id must not be empty")
        if not self.name.strip():
            raise ValueError("tool call name must not be empty")


@dataclass(frozen=True)
class ChatModelResult:
    answer: str
    provider: str
    model_name: str
    raw_response: dict[str, Any] | None = None
    tool_calls: list[ChatToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ToolCallingChatModelResult:
    content: str
    tool_calls: list[ChatToolCall]
    provider: str
    model_name: str


class ChatModelProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        """Generate one answer from ordered chat messages."""

    def stream_generate(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        """Yield answer text fragments from ordered chat messages."""

    def generate_with_tools(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ChatToolDefinition],
    ) -> ToolCallingChatModelResult:
        """Generate content or structured tool calls from ordered chat messages."""


@dataclass(frozen=True)
class DeterministicChatModelProvider:
    """Small local chat provider for tests and offline development."""

    model_name: str = "rule-based-chat-v1"
    provider_name: str = "deterministic"
    tool_call_rounds: tuple[tuple[ChatToolCall, ...], ...] = ()

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

    def stream_generate(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        answer = self.generate(messages).answer
        for chunk in split_streaming_text(answer):
            yield chunk
            time.sleep(0.02)

    def generate_with_tools(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ChatToolDefinition],
    ) -> ToolCallingChatModelResult:
        if not messages:
            raise ValueError("messages must not be empty")
        if not tools:
            result = self.generate(messages)
            return ToolCallingChatModelResult(
                content=result.answer,
                tool_calls=[],
                provider=result.provider,
                model_name=result.model_name,
            )

        tool_result_count = sum(1 for message in messages if message.role == "tool")
        if tool_result_count < len(self.tool_call_rounds):
            return ToolCallingChatModelResult(
                content="",
                tool_calls=list(self.tool_call_rounds[tool_result_count]),
                provider=self.provider_name,
                model_name=self.model_name,
            )

        if tool_result_count == 0:
            question = extract_question(latest_user_message(messages))
            preferred_tool = next(
                (
                    tool.function.name
                    for tool in tools
                    if tool.function.name == "hybrid_search_knowledge"
                ),
                tools[0].function.name,
            )
            return ToolCallingChatModelResult(
                content="",
                tool_calls=[
                    ChatToolCall(
                        id="deterministic-tool-call-1",
                        name=preferred_tool,
                        arguments={"query": question, "top_k": 5},
                    )
                ],
                provider=self.provider_name,
                model_name=self.model_name,
            )

        source_ids = extract_source_ids(messages)
        source_marker = f"[{source_ids[0]}]" if source_ids else "[1]"
        return ToolCallingChatModelResult(
            content=f"Deterministic tool-calling answer based on source {source_marker}.",
            tool_calls=[],
            provider=self.provider_name,
            model_name=self.model_name,
        )


@dataclass(frozen=True)
class OpenAICompatibleChatModelProvider:
    model_name: str
    api_key: str
    base_url: str
    temperature: float = 0.2
    timeout_seconds: float = 30.0
    provider_name: str = "openai-compatible"
    max_attempts: int = 3
    retry_backoff_seconds: float = 0.5
    max_tokens: int | None = None
    extra_body: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if not self.api_key.strip():
            raise ValueError("api_key must not be empty")
        if not self.base_url.strip():
            raise ValueError("base_url must not be empty")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be greater than 0")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be greater than or equal to 0")

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        if not messages:
            raise ValueError("messages must not be empty")

        request = self._build_request(messages, stream=False)
        response_data = self._request_with_retry(request)

        answer = parse_openai_compatible_answer(response_data)
        return ChatModelResult(
            answer=answer,
            provider=self.provider_name,
            model_name=self.model_name,
            raw_response=response_data,
        )

    def stream_generate(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        if not messages:
            raise ValueError("messages must not be empty")

        request = self._build_request(messages, stream=True)
        # Retry only covers connection establishment. Once tokens start
        # streaming we cannot safely retry without duplicating output.
        response = self._open_stream_with_retry(request)
        try:
            yield from parse_openai_compatible_stream(response)
            response.mark_complete()
        finally:
            response.close()

    def generate_with_tools(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ChatToolDefinition],
    ) -> ToolCallingChatModelResult:
        if not messages:
            raise ValueError("messages must not be empty")
        if not tools:
            result = self.generate(messages)
            return ToolCallingChatModelResult(
                content=result.answer,
                tool_calls=[],
                provider=result.provider,
                model_name=result.model_name,
            )

        request = self._build_request(messages, stream=False, tools=tools)
        response_data = self._request_with_retry(request)
        content, tool_calls = parse_openai_compatible_tool_response(response_data)
        return ToolCallingChatModelResult(
            content=content,
            tool_calls=tool_calls,
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def _request_with_retry(self, request: urllib.request.Request) -> dict[str, Any]:
        """Send the request, retrying transient network failures.

        Transient TLS/connection drops (e.g. ``UNEXPECTED_EOF_WHILE_READING``),
        timeouts, and 429/5xx responses are retried with a short backoff. Other
        4xx responses fail immediately because retrying them cannot help.
        """

        for attempt in range(1, self.max_attempts + 1):
            is_last_attempt = attempt >= self.max_attempts
            self._trace_attempt(attempt)
            try:
                if is_deepseek_endpoint(self.base_url):
                    return request_deepseek_with_curl(
                        request,
                        timeout_seconds=self.timeout_seconds,
                    )
                response_data = request_json_without_proxy(
                    request,
                    timeout=self.timeout_seconds,
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                )
                return response_data
            except TimeoutError as exc:
                if is_last_attempt:
                    raise RuntimeError("Chat model request timed out") from exc
            except TransientHTTPStatusError as exc:
                if is_last_attempt:
                    raise RuntimeError(str(exc)) from exc
            except urllib.error.HTTPError as exc:
                if exc.code not in RETRYABLE_HTTP_STATUS or is_last_attempt:
                    error_body = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(
                        f"Chat model request failed with HTTP {exc.code}: {error_body}"
                    ) from exc
            except urllib.error.URLError as exc:
                if is_last_attempt:
                    raise RuntimeError(f"Chat model request failed: {exc.reason}") from exc
            self._sleep_before_retry(attempt)
        # Defensive: the loop either returns or raises on the last attempt.
        raise RuntimeError("Chat model request failed after retries")

    def _open_stream_with_retry(self, request: urllib.request.Request):
        for attempt in range(1, self.max_attempts + 1):
            is_last_attempt = attempt >= self.max_attempts
            self._trace_attempt(attempt)
            try:
                return HTTP_JSON_CONNECTION_POOL.open_sse(
                    request,
                    timeout=self.timeout_seconds,
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                )
            except TimeoutError as exc:
                if is_last_attempt:
                    raise RuntimeError("Chat model stream request timed out") from exc
            except urllib.error.HTTPError as exc:
                if exc.code not in RETRYABLE_HTTP_STATUS or is_last_attempt:
                    error_body = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(
                        f"Chat model stream request failed with HTTP {exc.code}: {error_body}"
                    ) from exc
            except urllib.error.URLError as exc:
                if is_last_attempt:
                    raise RuntimeError(f"Chat model stream request failed: {exc.reason}") from exc
            except http.client.HTTPException as exc:
                if is_last_attempt:
                    raise RuntimeError("Chat model stream request failed before response") from exc
            self._sleep_before_retry(attempt)
        # Defensive: the loop either returns or raises on the last attempt.
        raise RuntimeError("Chat model stream request failed after retries")

    def _sleep_before_retry(self, attempt: int) -> None:
        if self.retry_backoff_seconds <= 0:
            return
        duration = self.retry_backoff_seconds * attempt
        trace = get_current_latency_trace()
        if trace is not None:
            trace.add_duration("provider_http_retry_backoff_ms", duration * 1000.0)
        time.sleep(duration)

    def _build_request(
        self,
        messages: Sequence[ChatMessage],
        *,
        stream: bool,
        tools: Sequence[ChatToolDefinition] | None = None,
    ) -> urllib.request.Request:
        payload = {
            "model": self.model_name,
            "messages": [message_to_openai_payload(message) for message in messages],
            "temperature": self.temperature,
        }
        if self.max_tokens is not None and self.max_tokens > 0:
            payload["max_tokens"] = self.max_tokens
        if self.extra_body:
            payload.update(self.extra_body)
        if tools:
            payload["tools"] = [tool_definition_to_payload(tool) for tool in tools]
            payload["tool_choice"] = "auto"
        if stream:
            payload["stream"] = True
            if is_deepseek_endpoint(self.base_url):
                payload["stream_options"] = {"include_usage": True}
        return urllib.request.Request(
            self._endpoint_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "api-key": self.api_key,
                "Accept": "text/event-stream" if stream else "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "rfc-rag-agent/chat-model-provider",
            },
            method="POST",
        )

    def _endpoint_url(self) -> str:
        normalized_base_url = self.base_url.rstrip("/")
        if normalized_base_url.endswith("/chat/completions"):
            return normalized_base_url
        if (
            "llmapi.paratera.com" in normalized_base_url
            and not normalized_base_url.endswith("/v1")
        ):
            return f"{normalized_base_url}/v1/chat/completions"
        return f"{normalized_base_url}/chat/completions"

    def _trace_attempt(self, attempt: int) -> None:
        trace = get_current_latency_trace()
        if trace is None:
            return
        trace.set_value("provider_http_last_provider", self.provider_name)
        trace.set_value("provider_http_last_model", self.model_name)
        trace.set_value("provider_http_last_attempt", attempt)
        count = int(trace.values.get("provider_http_attempt_count", 0)) + 1
        trace.set_value("provider_http_attempt_count", count)


def is_deepseek_endpoint(base_url: str) -> bool:
    return "api.deepseek.com" in base_url.casefold()


def request_deepseek_with_curl(
    request: urllib.request.Request,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    data_path = ""
    try:
        with tempfile.NamedTemporaryFile("wb", delete=False) as data_file:
            data_file.write(request.data or b"{}")
            data_path = data_file.name

        headers = dict(request.header_items())
        auth_header = headers.get("Authorization") or headers.get("authorization") or ""
        content_type = (
            headers.get("Content-type")
            or headers.get("Content-Type")
            or "application/json; charset=utf-8"
        )
        curl_executable = shutil.which("curl") or shutil.which("curl.exe")
        if not curl_executable:
            with urlopen_without_proxy(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        curl_args = [
            curl_executable,
            "-sS",
            "-m",
            str(max(1, int(timeout_seconds))),
            "-w",
            "\nHTTP_STATUS:%{http_code}\n",
            "-H",
            f"Content-Type: {content_type}",
            "--data-binary",
            f"@{data_path}",
            request.full_url,
        ]
        if auth_header:
            curl_args[1:1] = ["-H", f"Authorization: {auth_header}"]
        completed = subprocess.run(
            curl_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=max(5, int(timeout_seconds) + 5),
            check=False,
        )
        if completed.returncode != 0:
            raise TimeoutError(completed.stderr.strip() or "DeepSeek curl request failed")
        body, status_code = split_curl_response(completed.stdout)
        if status_code in RETRYABLE_HTTP_STATUS:
            raise TransientHTTPStatusError(
                status_code,
                f"Chat model request failed with HTTP {status_code}",
            )
        if status_code >= 400:
            raise RuntimeError(f"Chat model request failed with HTTP {status_code}")
        return json.loads(body)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("DeepSeek curl request timed out") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Chat model response was not valid JSON") from exc
    finally:
        if data_path:
            try:
                os.remove(data_path)
            except OSError:
                pass


def split_curl_response(output: str) -> tuple[str, int]:
    marker = "\nHTTP_STATUS:"
    if marker not in output:
        raise RuntimeError("DeepSeek curl response did not include HTTP status")
    body, status_text = output.rsplit(marker, 1)
    status_line = status_text.strip().splitlines()[0]
    return body.strip(), int(status_line)


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


def parse_openai_compatible_tool_response(
    response_data: dict[str, Any],
) -> tuple[str, list[ChatToolCall]]:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Chat model response did not include choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("Chat model response choice is not an object")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("Chat model response choice did not include a message")

    content_value = message.get("content")
    content = content_value.strip() if isinstance(content_value, str) else ""
    tool_calls = parse_openai_tool_calls(message.get("tool_calls"))
    if not content and not tool_calls:
        raise RuntimeError("Chat model response included neither content nor tool_calls")
    return content, tool_calls


def parse_openai_tool_calls(value: Any) -> list[ChatToolCall]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RuntimeError("Chat model response tool_calls is not a list")

    parsed: list[ChatToolCall] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise RuntimeError("Chat model response tool_call is not an object")
        function = item.get("function")
        if not isinstance(function, dict):
            raise RuntimeError("Chat model response tool_call did not include function")
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RuntimeError("Chat model response tool_call function name is empty")
        arguments = parse_tool_call_arguments(function.get("arguments"))
        tool_call_id = item.get("id")
        if not isinstance(tool_call_id, str) or not tool_call_id.strip():
            tool_call_id = f"tool-call-{index}"
        parsed.append(
            ChatToolCall(id=tool_call_id, name=name.strip(), arguments=arguments)
        )
    return parsed


def parse_tool_call_arguments(value: Any) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Chat model response tool_call arguments is invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Chat model response tool_call arguments is not an object")
        return parsed
    raise RuntimeError("Chat model response tool_call arguments has unsupported type")


def message_to_openai_payload(message: ChatMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content or None}
    if message.role == "tool":
        payload["tool_call_id"] = message.tool_call_id or ""
    if message.assistant_tool_calls:
        payload["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
            for tc in message.assistant_tool_calls
        ]
    return payload


def tool_definition_to_payload(tool: ChatToolDefinition) -> dict[str, Any]:
    return {
        "type": tool.type,
        "function": {
            "name": tool.function.name,
            "description": tool.function.description,
            "parameters": tool.function.parameters,
        },
    }


def urlopen_without_proxy(
    request: urllib.request.Request,
    timeout: float,
):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(request, timeout=timeout)


def request_json_without_proxy(
    request: urllib.request.Request,
    *,
    timeout: float,
    provider_name: str,
    model_name: str,
) -> dict[str, Any]:
    response = HTTP_JSON_CONNECTION_POOL.request_json(
        request,
        timeout=timeout,
        provider_name=provider_name,
        model_name=model_name,
    )
    return response.payload


def parse_openai_compatible_stream(response) -> Iterator[str]:
    for raw_line in response:
        line = decode_stream_line(raw_line)
        if not line or not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if not data:
            continue
        if data == "[DONE]":
            break
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Chat model stream response included invalid JSON") from exc
        record_stream_usage(payload)
        content = extract_openai_delta_content(payload)
        if content:
            yield content


def record_stream_usage(payload: dict[str, Any]) -> None:
    trace = get_current_latency_trace()
    usage = payload.get("usage")
    if trace is None or not isinstance(usage, dict):
        return
    for usage_field, trace_field in (
        ("prompt_tokens", "provider_prompt_tokens"),
        ("prompt_cache_hit_tokens", "provider_prompt_cache_hit_tokens"),
        ("prompt_cache_miss_tokens", "provider_prompt_cache_miss_tokens"),
    ):
        value = usage.get(usage_field)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            trace.set_value(trace_field, value)


def decode_stream_line(raw_line: bytes | str) -> str:
    if isinstance(raw_line, bytes):
        return raw_line.decode("utf-8", errors="replace").strip()
    return raw_line.strip()


def extract_openai_delta_content(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None
    delta = first_choice.get("delta")
    if not isinstance(delta, dict):
        return None
    content = delta.get("content")
    if not isinstance(content, str) or not content:
        return None
    return content


def split_streaming_text(text: str) -> list[str]:
    chunks: list[str] = []
    current = ""
    for char in text:
        current += char
        if char.isspace() or char in "，。！？；：,.!?;:" or len(current) >= 6:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def create_chat_model_provider(
    provider_name: str | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.2,
    timeout_seconds: float = 30.0,
    max_attempts: int = 3,
    max_tokens: int | None = None,
    extra_body: dict[str, Any] | None = None,
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
            max_attempts=max_attempts,
            max_tokens=max_tokens,
            extra_body=extra_body or {},
        )

    raise ValueError(f"Unsupported chat model provider: {provider_name}")
