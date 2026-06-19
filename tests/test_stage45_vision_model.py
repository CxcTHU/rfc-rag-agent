import json
import struct
import zlib

import pytest

from app.services.generation.vision_model import (
    DeterministicVisionModelProvider,
    OpenAICompatibleVisionModelProvider,
    create_vision_model_provider,
    image_to_data_uri,
    parse_openai_compatible_vision_description,
)


class FakeVisionResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": "图中展示了堆石混凝土强度随龄期增长的趋势。"
                        }
                    }
                ]
            }
        ).encode("utf-8")


def test_deterministic_vision_provider_returns_stable_description(tmp_path) -> None:
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(make_png_bytes(120, 120, (10, 20, 30)))
    provider = DeterministicVisionModelProvider()

    description = provider.describe_image(image_path)

    assert "确定性视觉描述" in description
    assert "figure.png" in description
    assert "image_description chunk" in description


def test_image_to_data_uri_encodes_png(tmp_path) -> None:
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(make_png_bytes(1, 1, (255, 0, 0)))

    data_uri = image_to_data_uri(image_path)

    assert data_uri.startswith("data:image/png;base64,")
    assert len(data_uri.split(",", 1)[1]) > 0


def test_openai_compatible_vision_provider_posts_multimodal_payload(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(make_png_bytes(2, 2, (0, 255, 0)))
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeVisionResponse()

    monkeypatch.setattr("app.services.generation.vision_model.urlopen_without_proxy", fake_urlopen)
    provider = OpenAICompatibleVisionModelProvider(
        model_name="vision-test",
        api_key="test-key",
        base_url="https://models.example/v1",
        timeout_seconds=9,
    )

    description = provider.describe_image(image_path, prompt="请描述图表。")

    assert description == "图中展示了堆石混凝土强度随龄期增长的趋势。"
    assert captured["url"] == "https://models.example/v1/chat/completions"
    assert captured["timeout"] == 9
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    content = captured["payload"]["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "请描述图表。"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_create_vision_model_provider_supports_deterministic_and_paratera_alias() -> None:
    deterministic = create_vision_model_provider()
    paratera = create_vision_model_provider(
        "paratera",
        model_name="glm-4v-test",
        api_key="test-key",
        base_url="https://llmapi.example/v1",
    )

    assert deterministic.provider_name == "deterministic"
    assert paratera.provider_name == "paratera"
    assert paratera.model_name == "glm-4v-test"


def test_paratera_root_base_url_uses_v1_chat_completions_endpoint() -> None:
    provider = OpenAICompatibleVisionModelProvider(
        model_name="GLM-4.6V",
        api_key="test-key",
        base_url="https://llmapi.paratera.com",
        provider_name="paratera",
    )

    assert provider._endpoint_url() == "https://llmapi.paratera.com/v1/chat/completions"


def test_create_vision_model_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported vision model provider"):
        create_vision_model_provider("unknown")


def test_parse_openai_compatible_vision_description_supports_text_parts() -> None:
    description = parse_openai_compatible_vision_description(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "第一段。"},
                            {"type": "text", "text": "第二段。"},
                        ]
                    }
                }
            ]
        }
    )

    assert description == "第一段。\n第二段。"


def make_png_bytes(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw))
        + png_chunk(b"IEND", b"")
    )


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)
