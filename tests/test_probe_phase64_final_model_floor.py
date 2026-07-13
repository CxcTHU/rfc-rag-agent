import json
from types import SimpleNamespace

from app.services.generation.chat_model import ChatMessage
import scripts.probe_phase64_final_model_floor as floor_probe
from scripts.probe_phase64_final_model_floor import measure_final_model_floor


class _StreamingProvider:
    provider_name = "test-provider"
    model_name = "test-model"

    def stream_generate(self, messages):
        assert messages[0].content == "fixed safe probe"
        yield "first"
        yield "private answer must not persist"


def test_floor_probe_never_returns_streamed_text() -> None:
    result = measure_final_model_floor(
        _StreamingProvider(),
        [ChatMessage(role="user", content="fixed safe probe")],
    )

    assert result["ok"] is True
    assert result["first_content_delta_ms"] >= 0.0
    assert result["elapsed_ms"] >= result["first_content_delta_ms"]
    assert set(result) == {"ok", "first_content_delta_ms", "elapsed_ms"}
    assert "private answer" not in json.dumps(result)


def test_phase64_floor_probe_uses_the_same_non_thinking_final_wrapper(monkeypatch) -> None:
    base_provider = object()
    wrapped_provider = object()
    settings = SimpleNamespace(
        chat_model_provider="openai-compatible",
        chat_model_name="test-model",
        chat_model_api_key="test-key",
        chat_model_base_url="https://example.test/v1",
        chat_model_temperature=0.0,
        chat_model_timeout_seconds=10.0,
        agent_final_max_tokens=1200,
    )
    monkeypatch.setattr(
        floor_probe,
        "create_chat_model_provider",
        lambda **_kwargs: base_provider,
    )
    monkeypatch.setattr(
        floor_probe,
        "phase64_final_answer_provider",
        lambda provider, received_settings: (
            wrapped_provider
            if provider is base_provider and received_settings is settings
            else None
        ),
    )

    provider = floor_probe.build_floor_provider(
        settings,
        phase64_non_thinking=True,
    )

    assert provider is wrapped_provider
