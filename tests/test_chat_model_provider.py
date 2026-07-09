import io
import json
import urllib.error

import pytest

from app.services.generation.chat_model import (
    ChatMessage,
    ChatToolCall,
    ChatToolDefinition,
    ChatToolFunction,
    DeterministicChatModelProvider,
    OpenAICompatibleChatModelProvider,
    create_chat_model_provider,
    extract_question,
    extract_source_ids,
    latest_user_message,
    parse_openai_compatible_answer,
    parse_openai_compatible_stream,
    parse_openai_compatible_tool_response,
    split_streaming_text,
)


class _ChatFakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(
            {"choices": [{"message": {"content": "Answer with [1]."}}]}
        ).encode("utf-8")


def test_chat_message_rejects_unsupported_role() -> None:
    with pytest.raises(ValueError, match="Unsupported chat role"):
        ChatMessage(role="developer", content="hello")  # type: ignore[arg-type]


def test_chat_message_supports_tool_role_with_tool_call_id() -> None:
    message = ChatMessage(
        role="tool",
        content='{"sources":[{"source_id":"chunk:1"}]}',
        tool_call_id="call_1",
    )

    assert message.role == "tool"
    assert message.tool_call_id == "call_1"


def test_chat_message_rejects_tool_role_without_tool_call_id() -> None:
    with pytest.raises(ValueError, match="tool_call_id"):
        ChatMessage(role="tool", content="hello")


def test_chat_message_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="content must not be empty"):
        ChatMessage(role="user", content="   ")


def test_deterministic_chat_provider_returns_model_metadata() -> None:
    provider = DeterministicChatModelProvider()

    result = provider.generate(
        [
            ChatMessage(role="system", content="Use only provided context [1]."),
            ChatMessage(role="user", content="什么是堆石混凝土？"),
        ]
    )

    assert result.provider == "deterministic"
    assert result.model_name == "rule-based-chat-v1"
    assert "source [1]" in result.answer
    assert "什么是堆石混凝土？" in result.answer


def test_deterministic_chat_provider_requires_messages() -> None:
    provider = DeterministicChatModelProvider()

    with pytest.raises(ValueError, match="messages must not be empty"):
        provider.generate([])


def test_deterministic_chat_provider_requires_user_message() -> None:
    provider = DeterministicChatModelProvider()

    with pytest.raises(ValueError, match="at least one user message"):
        provider.generate([ChatMessage(role="system", content="system prompt")])


def test_deterministic_chat_provider_stream_matches_generate() -> None:
    provider = DeterministicChatModelProvider()
    messages = [
        ChatMessage(role="system", content="Use only provided context [1]."),
        ChatMessage(role="user", content="What is RFC?"),
    ]

    streamed = "".join(provider.stream_generate(messages))

    assert streamed == provider.generate(messages).answer


def test_deterministic_chat_provider_can_simulate_tool_call_then_answer() -> None:
    provider = DeterministicChatModelProvider()
    tools = [
        ChatToolDefinition(
            function=ChatToolFunction(
                name="hybrid_search_knowledge",
                description="Search the local knowledge base.",
                parameters={"type": "object", "properties": {}},
            )
        )
    ]
    messages = [ChatMessage(role="user", content="什么是堆石混凝土？")]

    first = provider.generate_with_tools(messages, tools)

    assert first.content == ""
    assert [call.name for call in first.tool_calls] == ["hybrid_search_knowledge"]
    assert first.tool_calls[0].arguments["query"] == "什么是堆石混凝土？"

    second = provider.generate_with_tools(
        [
            *messages,
            ChatMessage(
                role="tool",
                content='{"sources":[{"source_id":"chunk:1","snippet":"context [1]"}]}',
                tool_call_id=first.tool_calls[0].id,
            ),
        ],
        tools,
    )

    assert second.tool_calls == []
    assert "source [1]" in second.content


def test_deterministic_chat_provider_can_simulate_multi_round_tool_calls() -> None:
    provider = DeterministicChatModelProvider(
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="call_1",
                    name="hybrid_search_knowledge",
                    arguments={"query": "first", "top_k": 3},
                ),
            ),
            (
                ChatToolCall(
                    id="call_2",
                    name="search_knowledge",
                    arguments={"query": "second", "top_k": 3},
                ),
            ),
        )
    )
    tools = [
        ChatToolDefinition(
            function=ChatToolFunction(
                name="hybrid_search_knowledge",
                description="Hybrid search.",
                parameters={"type": "object", "properties": {}},
            )
        ),
        ChatToolDefinition(
            function=ChatToolFunction(
                name="search_knowledge",
                description="Keyword search.",
                parameters={"type": "object", "properties": {}},
            )
        ),
    ]
    user_message = ChatMessage(role="user", content="compare two topics")

    first = provider.generate_with_tools([user_message], tools)
    second = provider.generate_with_tools(
        [
            user_message,
            ChatMessage(role="tool", content="result [1]", tool_call_id="call_1"),
        ],
        tools,
    )
    final = provider.generate_with_tools(
        [
            user_message,
            ChatMessage(role="tool", content="result [1]", tool_call_id="call_1"),
            ChatMessage(role="tool", content="result [2]", tool_call_id="call_2"),
        ],
        tools,
    )

    assert [call.name for call in first.tool_calls] == ["hybrid_search_knowledge"]
    assert [call.name for call in second.tool_calls] == ["search_knowledge"]
    assert final.tool_calls == []
    assert "Deterministic tool-calling answer" in final.content


def test_split_streaming_text_splits_chinese_without_losing_text() -> None:
    text = "当前资料库中没有找到足够可靠的依据。"

    chunks = split_streaming_text(text)

    assert len(chunks) > 1
    assert "".join(chunks) == text


def test_latest_user_message_returns_last_user_message() -> None:
    messages = [
        ChatMessage(role="user", content="first"),
        ChatMessage(role="assistant", content="answer"),
        ChatMessage(role="user", content="second"),
    ]

    assert latest_user_message(messages) == "second"


def test_extract_question_from_rag_user_prompt() -> None:
    user_prompt = "Question:\n什么是堆石混凝土？\n\nContext:\n[1]\nContent"

    assert extract_question(user_prompt) == "什么是堆石混凝土？"


def test_extract_source_ids_preserves_first_seen_order() -> None:
    messages = [
        ChatMessage(role="system", content="Context [2] and [1]"),
        ChatMessage(role="user", content="Use [2]"),
    ]

    assert extract_source_ids(messages) == [2, 1]


def test_create_chat_model_provider_defaults_to_deterministic() -> None:
    provider = create_chat_model_provider()

    assert provider.provider_name == "deterministic"


def test_create_chat_model_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported chat model provider"):
        create_chat_model_provider("unknown")


def test_openai_compatible_provider_keeps_boundary_configuration() -> None:
    provider = create_chat_model_provider(
        "openai-compatible",
        model_name="qwen-test",
        api_key="test-key",
        base_url="https://example.test/v1",
        max_attempts=1,
    )

    assert provider.provider_name == "openai-compatible"
    assert provider.model_name == "qwen-test"
    assert provider.max_attempts == 1


def test_openai_compatible_provider_requires_configuration() -> None:
    with pytest.raises(ValueError, match="api_key must not be empty"):
        OpenAICompatibleChatModelProvider(
            model_name="qwen-test",
            api_key="",
            base_url="https://example.test/v1",
        )


def test_openai_compatible_provider_paratera_root_base_url_uses_v1_endpoint() -> None:
    provider = OpenAICompatibleChatModelProvider(
        model_name="glm-test",
        api_key="test-key",
        base_url="https://llmapi.paratera.com",
    )

    assert provider._endpoint_url() == "https://llmapi.paratera.com/v1/chat/completions"


def test_openai_compatible_provider_posts_chat_request_headers(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(request, *, timeout, provider_name, model_name):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["provider_name"] = provider_name
        captured["model_name"] = model_name
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return {"choices": [{"message": {"content": "Answer with [1]."}}]}

    monkeypatch.setattr("app.services.generation.chat_model.request_json_without_proxy", fake_request_json)
    provider = OpenAICompatibleChatModelProvider(
        model_name="mimo-v2.5-pro",
        api_key="test-key",
        base_url="https://api.xiaomimimo.com/v1",
        timeout_seconds=9,
    )

    result = provider.generate(
        [
            ChatMessage(role="system", content="Use citations."),
            ChatMessage(role="user", content="What is RFC?"),
        ]
    )

    assert result.answer == "Answer with [1]."
    assert captured["url"] == "https://api.xiaomimimo.com/v1/chat/completions"
    assert captured["timeout"] == 9
    assert captured["provider_name"] == "openai-compatible"
    assert captured["model_name"] == "mimo-v2.5-pro"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["headers"]["Api-key"] == "test-key"
    assert captured["headers"]["Accept"] == "application/json"
    assert captured["headers"]["User-agent"] == "rfc-rag-agent/chat-model-provider"
    assert captured["payload"]["model"] == "mimo-v2.5-pro"
    assert "stream" not in captured["payload"]


def test_openai_compatible_provider_accepts_max_tokens_and_extra_body(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(request, *, timeout, provider_name, model_name):
        del timeout, provider_name, model_name
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return {"choices": [{"message": {"content": "{\"ok\": true}"}}]}

    monkeypatch.setattr("app.services.generation.chat_model.request_json_without_proxy", fake_request_json)
    provider = OpenAICompatibleChatModelProvider(
        model_name="glm-test",
        api_key="test-key",
        base_url="https://llmapi.paratera.com",
        max_tokens=512,
        extra_body={"thinking": {"type": "disabled"}, "reasoning_effort": "none"},
    )

    provider.generate([ChatMessage(role="user", content="Return JSON.")])

    assert captured["payload"]["max_tokens"] == 512
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["payload"]["reasoning_effort"] == "none"


def test_openai_compatible_provider_streams_delta_content(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeStreamResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def __iter__(self):
            lines = [
                b"data: {\"choices\":[{\"delta\":{\"role\":\"assistant\"}}]}\n\n",
                b"data: {\"choices\":[{\"delta\":{\"content\":\"Answer \"}}]}\n\n",
                b"data: {\"choices\":[{\"delta\":{\"content\":\"with [1].\"}}]}\n\n",
                b"data: [DONE]\n\n",
            ]
            return iter(lines)

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeStreamResponse()

    monkeypatch.setattr("app.services.generation.chat_model.urlopen_without_proxy", fake_urlopen)
    provider = OpenAICompatibleChatModelProvider(
        model_name="mimo-v2.5-pro",
        api_key="test-key",
        base_url="https://api.xiaomimimo.com/v1",
        timeout_seconds=9,
    )

    chunks = list(
        provider.stream_generate(
            [
                ChatMessage(role="system", content="Use citations."),
                ChatMessage(role="user", content="What is RFC?"),
            ]
        )
    )

    assert chunks == ["Answer ", "with [1]."]
    assert captured["url"] == "https://api.xiaomimimo.com/v1/chat/completions"
    assert captured["timeout"] == 9
    assert captured["headers"]["Accept"] == "text/event-stream"
    assert captured["payload"]["stream"] is True


def test_openai_compatible_provider_posts_tools_and_parses_tool_calls(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(request, *, timeout, provider_name, model_name):
        del timeout, provider_name, model_name
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "hybrid_search_knowledge",
                                    "arguments": "{\"query\":\"RFC\",\"top_k\":3}",
                                },
                            }
                        ],
                    }
                }
            ]
        }

    monkeypatch.setattr("app.services.generation.chat_model.request_json_without_proxy", fake_request_json)
    provider = OpenAICompatibleChatModelProvider(
        model_name="mimo-v2.5-pro",
        api_key="test-key",
        base_url="https://api.xiaomimimo.com/v1",
        timeout_seconds=9,
    )
    tools = [
        ChatToolDefinition(
            function=ChatToolFunction(
                name="hybrid_search_knowledge",
                description="Hybrid search.",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}},
            )
        )
    ]

    result = provider.generate_with_tools(
        [ChatMessage(role="user", content="What is RFC?")],
        tools,
    )

    payload = captured["payload"]
    assert payload["tools"][0]["function"]["name"] == "hybrid_search_knowledge"
    assert payload["tool_choice"] == "auto"
    assert result.content == ""
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "hybrid_search_knowledge"
    assert result.tool_calls[0].arguments == {"query": "RFC", "top_k": 3}


def test_openai_compatible_provider_sends_tool_messages(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(request, *, timeout, provider_name, model_name):
        del timeout, provider_name, model_name
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return {"choices": [{"message": {"content": "Answer with [1]."}}]}

    monkeypatch.setattr("app.services.generation.chat_model.request_json_without_proxy", fake_request_json)
    provider = OpenAICompatibleChatModelProvider(
        model_name="mimo-v2.5-pro",
        api_key="test-key",
        base_url="https://api.xiaomimimo.com/v1",
    )

    result = provider.generate_with_tools(
        [
            ChatMessage(role="user", content="What is RFC?"),
            ChatMessage(role="tool", content='{"sources":[]}', tool_call_id="call_1"),
        ],
        [
            ChatToolDefinition(
                function=ChatToolFunction(
                    name="hybrid_search_knowledge",
                    description="Hybrid search.",
                    parameters={"type": "object", "properties": {}},
                )
            )
        ],
    )

    tool_message = captured["payload"]["messages"][1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call_1"
    assert result.content == "Answer with [1]."
    assert result.tool_calls == []


def test_openai_compatible_provider_uses_curl_for_deepseek_endpoint(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_deepseek_curl(request, timeout_seconds):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return {"choices": [{"message": {"content": "Answer with [1]."}}]}

    monkeypatch.setattr(
        "app.services.generation.chat_model.request_deepseek_with_curl",
        fake_deepseek_curl,
    )
    provider = OpenAICompatibleChatModelProvider(
        model_name="deepseek-v4-flash",
        api_key="test-key",
        base_url="https://api.deepseek.com",
    )

    provider.generate_with_tools(
        [ChatMessage(role="user", content="What is RFC?")],
        [
            ChatToolDefinition(
                function=ChatToolFunction(
                    name="hybrid_search_knowledge",
                    description="Hybrid search.",
                    parameters={"type": "object", "properties": {}},
                )
            )
        ],
    )

    assert "thinking" not in captured["payload"]
    assert captured["payload"]["model"] == "deepseek-v4-flash"


def test_deepseek_request_falls_back_to_urlopen_when_curl_missing(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _ChatFakeResponse()

    monkeypatch.setattr("app.services.generation.chat_model.shutil.which", lambda _: None)
    monkeypatch.setattr(
        "app.services.generation.chat_model.urlopen_without_proxy", fake_urlopen
    )
    provider = OpenAICompatibleChatModelProvider(
        model_name="deepseek-v4-flash",
        api_key="test-key",
        base_url="https://api.deepseek.com",
    )

    result = provider.generate([ChatMessage(role="user", content="What is RFC?")])

    assert captured["payload"]["model"] == "deepseek-v4-flash"
    assert result.answer == "Answer with [1]."


def test_chat_provider_retries_transient_ssl_error(monkeypatch) -> None:
    attempts = {"count": 0}

    def flaky_request_json(request, *, timeout, provider_name, model_name):
        del request, timeout, provider_name, model_name
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise urllib.error.URLError(
                "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol"
            )
        return {"choices": [{"message": {"content": "Answer with [1]."}}]}

    monkeypatch.setattr(
        "app.services.generation.chat_model.request_json_without_proxy", flaky_request_json
    )
    provider = OpenAICompatibleChatModelProvider(
        model_name="mimo-v2.5-pro",
        api_key="test-key",
        base_url="https://api.xiaomimimo.com/v1",
        retry_backoff_seconds=0,
    )

    result = provider.generate(
        [
            ChatMessage(role="system", content="Use citations."),
            ChatMessage(role="user", content="What is RFC?"),
        ]
    )

    assert result.answer == "Answer with [1]."
    assert attempts["count"] == 2


def test_chat_provider_raises_after_exhausting_retries(monkeypatch) -> None:
    attempts = {"count": 0}

    def always_failing_request_json(request, *, timeout, provider_name, model_name):
        del request, timeout, provider_name, model_name
        attempts["count"] += 1
        raise urllib.error.URLError("[SSL: UNEXPECTED_EOF_WHILE_READING]")

    monkeypatch.setattr(
        "app.services.generation.chat_model.request_json_without_proxy", always_failing_request_json
    )
    provider = OpenAICompatibleChatModelProvider(
        model_name="mimo-v2.5-pro",
        api_key="test-key",
        base_url="https://api.xiaomimimo.com/v1",
        max_attempts=3,
        retry_backoff_seconds=0,
    )

    with pytest.raises(RuntimeError, match="Chat model request failed"):
        provider.generate(
            [
                ChatMessage(role="system", content="Use citations."),
                ChatMessage(role="user", content="What is RFC?"),
            ]
        )
    assert attempts["count"] == 3


def test_chat_provider_does_not_retry_client_error(monkeypatch) -> None:
    attempts = {"count": 0}

    def http_error_request_json(request, *, timeout, provider_name, model_name):
        del request, timeout, provider_name, model_name
        attempts["count"] += 1
        raise urllib.error.HTTPError(
            url="https://api.xiaomimimo.com/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b"Unauthorized"),
        )

    monkeypatch.setattr(
        "app.services.generation.chat_model.request_json_without_proxy", http_error_request_json
    )
    provider = OpenAICompatibleChatModelProvider(
        model_name="mimo-v2.5-pro",
        api_key="test-key",
        base_url="https://api.xiaomimimo.com/v1",
        retry_backoff_seconds=0,
    )

    with pytest.raises(RuntimeError, match="HTTP 401"):
        provider.generate(
            [
                ChatMessage(role="system", content="Use citations."),
                ChatMessage(role="user", content="What is RFC?"),
            ]
        )
    assert attempts["count"] == 1


def test_chat_provider_stream_retries_connection_error(monkeypatch) -> None:
    attempts = {"count": 0}

    class FakeStreamResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __iter__(self):
            return iter(
                [
                    b"data: {\"choices\":[{\"delta\":{\"content\":\"Answer \"}}]}\n\n",
                    b"data: {\"choices\":[{\"delta\":{\"content\":\"with [1].\"}}]}\n\n",
                    b"data: [DONE]\n\n",
                ]
            )

    def flaky_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise urllib.error.URLError("[SSL: UNEXPECTED_EOF_WHILE_READING]")
        return FakeStreamResponse()

    monkeypatch.setattr(
        "app.services.generation.chat_model.urlopen_without_proxy", flaky_urlopen
    )
    provider = OpenAICompatibleChatModelProvider(
        model_name="mimo-v2.5-pro",
        api_key="test-key",
        base_url="https://api.xiaomimimo.com/v1",
        retry_backoff_seconds=0,
    )

    chunks = list(
        provider.stream_generate(
            [
                ChatMessage(role="system", content="Use citations."),
                ChatMessage(role="user", content="What is RFC?"),
            ]
        )
    )

    assert chunks == ["Answer ", "with [1]."]
    assert attempts["count"] == 2


def test_parse_openai_compatible_stream_rejects_invalid_json() -> None:
    with pytest.raises(RuntimeError, match="invalid JSON"):
        list(parse_openai_compatible_stream([b"data: {not-json}\n\n"]))


def test_parse_openai_compatible_answer() -> None:
    answer = parse_openai_compatible_answer(
        {"choices": [{"message": {"content": "Answer with [1]."}}]}
    )

    assert answer == "Answer with [1]."


def test_parse_openai_compatible_answer_rejects_invalid_response() -> None:
    with pytest.raises(RuntimeError, match="did not include choices"):
        parse_openai_compatible_answer({})


def test_parse_openai_compatible_tool_response_parses_content_and_tool_calls() -> None:
    content, tool_calls = parse_openai_compatible_tool_response(
        {
            "choices": [
                {
                    "message": {
                        "content": "Need search.",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "search_knowledge",
                                    "arguments": {"query": "RFC", "top_k": 2},
                                },
                            }
                        ],
                    }
                }
            ]
        }
    )

    assert content == "Need search."
    assert tool_calls == [
        ChatToolCall(
            id="call_1",
            name="search_knowledge",
            arguments={"query": "RFC", "top_k": 2},
        )
    ]
