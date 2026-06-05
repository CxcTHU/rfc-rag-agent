import pytest

from app.services.generation.chat_model import (
    ChatMessage,
    DeterministicChatModelProvider,
    OpenAICompatibleChatModelProvider,
    create_chat_model_provider,
    extract_question,
    extract_source_ids,
    latest_user_message,
    parse_openai_compatible_answer,
)


def test_chat_message_rejects_unsupported_role() -> None:
    with pytest.raises(ValueError, match="Unsupported chat role"):
        ChatMessage(role="tool", content="hello")  # type: ignore[arg-type]


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
    )

    assert provider.provider_name == "openai-compatible"
    assert provider.model_name == "qwen-test"


def test_openai_compatible_provider_requires_configuration() -> None:
    with pytest.raises(ValueError, match="api_key must not be empty"):
        OpenAICompatibleChatModelProvider(
            model_name="qwen-test",
            api_key="",
            base_url="https://example.test/v1",
        )


def test_parse_openai_compatible_answer() -> None:
    answer = parse_openai_compatible_answer(
        {"choices": [{"message": {"content": "Answer with [1]."}}]}
    )

    assert answer == "Answer with [1]."


def test_parse_openai_compatible_answer_rejects_invalid_response() -> None:
    with pytest.raises(RuntimeError, match="did not include choices"):
        parse_openai_compatible_answer({})
