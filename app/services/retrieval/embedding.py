import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
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


def tokenize(text: str) -> list[str]:
    return [match.group(0).casefold() for match in TOKEN_RE.finditer(text or "")]


def normalize_vector(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return [0.0 for _value in vector]
    return [value / norm for value in vector]


def create_embedding_provider(provider_name: str | None = None) -> EmbeddingProvider:
    provider = (provider_name or "deterministic").strip().casefold()
    if provider in {"", "deterministic", "fake", "local"}:
        return DeterministicEmbeddingProvider()
    raise ValueError(f"Unsupported embedding provider: {provider_name}")
