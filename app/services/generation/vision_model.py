from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


DEFAULT_VISION_PROMPT = (
    "请用中文描述这张来自堆石混凝土/RAG 知识库 PDF 的图片。"
    "如果它是图表，请概括标题、坐标轴、关键数据点、趋势和结论；"
    "如果它是结构图或流程图，请概括主要部件、关系和工程含义。"
    "只输出可检索的客观描述，不编造图中没有的信息。"
)


class VisionModelProvider(Protocol):
    provider_name: str
    model_name: str

    def describe_image(self, image_path: str | Path, prompt: str | None = None) -> str:
        """Return a text description for one local image."""


@dataclass(frozen=True)
class DeterministicVisionModelProvider:
    model_name: str = "deterministic-vision-v1"
    provider_name: str = "deterministic"

    def describe_image(self, image_path: str | Path, prompt: str | None = None) -> str:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(path)
        prompt_text = (prompt or DEFAULT_VISION_PROMPT).strip()
        return (
            "确定性视觉描述：该图片来自 PDF 图表或示意图，"
            f"文件名为 {path.name}。"
            "它应作为 image_description chunk 入库，并与普通文本 chunk 统一参与检索。"
            f"描述提示词长度={len(prompt_text)}。"
        )


@dataclass(frozen=True)
class OpenAICompatibleVisionModelProvider:
    model_name: str
    api_key: str
    base_url: str
    timeout_seconds: float = 30.0
    provider_name: str = "openai-compatible"

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if not self.api_key.strip():
            raise ValueError("api_key must not be empty")
        if not self.base_url.strip():
            raise ValueError("base_url must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")

    def describe_image(self, image_path: str | Path, prompt: str | None = None) -> str:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(path)
        request = self._build_request(path, prompt or DEFAULT_VISION_PROMPT)
        try:
            with urlopen_without_proxy(request, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise RuntimeError("Vision model request timed out") from exc
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Vision model request failed with HTTP {exc.code}: {error_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Vision model request failed: {exc.reason}") from exc
        return parse_openai_compatible_vision_description(response_data)

    def _build_request(self, image_path: Path, prompt: str) -> urllib.request.Request:
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_to_data_uri(image_path)},
                        },
                    ],
                }
            ],
        }
        return urllib.request.Request(
            self._endpoint_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "api-key": self.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "rfc-rag-agent/vision-model-provider",
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


def image_to_data_uri(image_path: str | Path) -> str:
    path = Path(image_path)
    media_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def parse_openai_compatible_vision_description(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Vision model response did not include choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("Vision model response choice is not an object")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("Vision model response choice did not include a message")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        text_parts = [
            item.get("text", "").strip()
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        description = "\n".join(part for part in text_parts if part)
        if description:
            return description
    raise RuntimeError("Vision model response message content is empty")


def urlopen_without_proxy(
    request: urllib.request.Request,
    timeout: float,
):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(request, timeout=timeout)


def create_vision_model_provider(
    provider_name: str | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
) -> VisionModelProvider:
    provider = (provider_name or "deterministic").strip().casefold()
    if provider in {"", "deterministic", "fake", "local"}:
        return DeterministicVisionModelProvider(
            model_name=(model_name or "deterministic-vision-v1").strip()
            or "deterministic-vision-v1"
        )
    if provider in {
        "openai-compatible",
        "openai",
        "compatible",
        "domestic",
        "paratera",
    }:
        alias = "paratera" if provider == "paratera" else "openai-compatible"
        return OpenAICompatibleVisionModelProvider(
            model_name=(model_name or "").strip(),
            api_key=(api_key or "").strip(),
            base_url=(base_url or "").strip(),
            timeout_seconds=timeout_seconds,
            provider_name=alias,
        )
    raise ValueError(f"Unsupported vision model provider: {provider_name}")
