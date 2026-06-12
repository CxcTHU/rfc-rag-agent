import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import Protocol


TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimension: int

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector for each input text."""

    def embed_query(self, query: str) -> list[float]:
        """Return one embedding vector for a user query."""


@dataclass(frozen=True)
class DeterministicEmbeddingProvider:
    """Small local embedding provider for tests and offline development."""

    dimension: int = 64
    provider_name: str = "deterministic"
    model_name: str = "hash-token-v1"

    def __post_init__(self) -> None:
        if self.dimension <= 0:
            raise ValueError("dimension must be greater than 0")

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._embed(query)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        return normalize_vector(vector)


@dataclass(frozen=True)
class OpenAICompatibleEmbeddingProvider:
    model_name: str
    api_key: str
    base_url: str
    dimension: int
    timeout_seconds: float = 30.0
    provider_name: str = "openai-compatible"

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if not self.api_key.strip():
            raise ValueError("api_key must not be empty")
        if not self.base_url.strip():
            raise ValueError("base_url must not be empty")
        if self.dimension <= 0:
            raise ValueError("dimension must be greater than 0")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = {
            "model": self.model_name,
            "input": list(texts),
        }
        request = urllib.request.Request(
            self._endpoint_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "api-key": self.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "rfc-rag-agent/embedding-provider",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Embedding model request failed with HTTP {exc.code}: {error_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Embedding model request failed: {exc.reason}") from exc

        embeddings = parse_openai_compatible_embeddings(response_data)
        if len(embeddings) != len(texts):
            raise RuntimeError(
                "Embedding model response did not match the number of input texts"
            )
        for embedding in embeddings:
            if len(embedding) != self.dimension:
                raise RuntimeError(
                    "Embedding model response vector dimension did not match configuration"
                )
        return embeddings

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]

    def _endpoint_url(self) -> str:
        normalized_base_url = self.base_url.rstrip("/")
        if normalized_base_url.endswith("/embeddings"):
            return normalized_base_url
        return f"{normalized_base_url}/embeddings"


def tokenize(text: str) -> list[str]:
    return [match.group(0).casefold() for match in TOKEN_RE.finditer(text or "")]


def normalize_vector(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return [0.0 for _value in vector]
    return [value / norm for value in vector]


def parse_openai_compatible_embeddings(response_data: dict[str, Any]) -> list[list[float]]:
    data = response_data.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("Embedding model response did not include data")

    ordered_items: list[tuple[int, dict[str, Any]]] = []
    for fallback_index, item in enumerate(data):
        if not isinstance(item, dict):
            raise RuntimeError("Embedding model response data item is not an object")
        raw_index = item.get("index", fallback_index)
        if not isinstance(raw_index, int):
            raise RuntimeError("Embedding model response index is not an integer")
        ordered_items.append((raw_index, item))

    embeddings: list[list[float]] = []
    for _index, item in sorted(ordered_items, key=lambda pair: pair[0]):
        raw_embedding = item.get("embedding")
        if not isinstance(raw_embedding, list) or not raw_embedding:
            raise RuntimeError("Embedding model response data item did not include embedding")
        embedding: list[float] = []
        for value in raw_embedding:
            if not isinstance(value, (int, float)):
                raise RuntimeError("Embedding vector contains a non-numeric value")
            embedding.append(float(value))
        embeddings.append(embedding)
    return embeddings


def create_embedding_provider(
    provider_name: str | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    dimension: int | None = None,
    timeout_seconds: float = 30.0,
) -> EmbeddingProvider:
    provider = (provider_name or "deterministic").strip().casefold()
    if provider in {"", "deterministic", "fake", "local"}:
        return DeterministicEmbeddingProvider()
    if provider in {"openai-compatible", "openai", "compatible", "domestic", "jina"}:
        if dimension is None:
            raise ValueError("dimension must be configured for OpenAI-compatible embeddings")
        return OpenAICompatibleEmbeddingProvider(
            model_name=(model_name or "").strip(),
            api_key=(api_key or "").strip(),
            base_url=(base_url or "").strip(),
            dimension=dimension,
            timeout_seconds=timeout_seconds,
            provider_name="jina" if provider == "jina" else "openai-compatible",
        )
    raise ValueError(f"Unsupported embedding provider: {provider_name}")
