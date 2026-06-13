from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")

# Transient HTTP statuses worth retrying. 4xx client errors (bad key, bad
# request) are excluded because retrying them only wastes quota.
RETRYABLE_HTTP_STATUS = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class ReRankResult:
    index: int
    score: float
    content: str


class ReRankingProvider(Protocol):
    provider_name: str
    model_name: str

    def rerank(
        self,
        query: str,
        candidates: Sequence[str],
        top_k: int = 5,
    ) -> list[ReRankResult]:
        """Score and re-order candidates by relevance to query."""


@dataclass(frozen=True)
class DeterministicReRankingProvider:
    model_name: str = "keyword-overlap-reranker-v1"
    provider_name: str = "deterministic"

    def rerank(
        self,
        query: str,
        candidates: Sequence[str],
        top_k: int = 5,
    ) -> list[ReRankResult]:
        validate_rerank_inputs(query, candidates, top_k)
        query_terms = tokenize(query)
        scored = [
            ReRankResult(
                index=index,
                score=deterministic_rerank_score(query_terms, candidate),
                content=candidate,
            )
            for index, candidate in enumerate(candidates)
        ]
        return sorted(scored, key=lambda item: (-item.score, item.index))[:top_k]


@dataclass(frozen=True)
class OpenAICompatibleReRankingProvider:
    model_name: str
    api_key: str
    base_url: str
    timeout_seconds: float = 30.0
    provider_name: str = "openai-compatible"
    max_attempts: int = 3
    retry_backoff_seconds: float = 0.5

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if not self.api_key.strip():
            raise ValueError("api_key must not be empty")
        if not self.base_url.strip():
            raise ValueError("base_url must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be greater than 0")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be greater than or equal to 0")

    def rerank(
        self,
        query: str,
        candidates: Sequence[str],
        top_k: int = 5,
    ) -> list[ReRankResult]:
        validate_rerank_inputs(query, candidates, top_k)
        payload = {
            "model": self.model_name,
            "query": query.strip(),
            "documents": list(candidates),
            "top_n": min(top_k, len(candidates)),
        }
        request = urllib.request.Request(
            self._endpoint_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "api-key": self.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "rfc-rag-agent/reranking-provider",
            },
            method="POST",
        )
        response_data = self._request_with_retry(request)
        return parse_openai_compatible_rerank_response(response_data, candidates, top_k)

    def _request_with_retry(self, request: urllib.request.Request) -> dict[str, Any]:
        """Send the request, retrying transient network failures.

        Transient TLS/connection drops, timeouts, and 429/5xx responses are
        retried with a short backoff. Other 4xx responses fail immediately
        because retrying them cannot help.
        """

        for attempt in range(1, self.max_attempts + 1):
            is_last_attempt = attempt >= self.max_attempts
            try:
                with urlopen_without_proxy(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except TimeoutError as exc:
                if is_last_attempt:
                    raise RuntimeError("Reranking model request timed out") from exc
            except urllib.error.HTTPError as exc:
                if exc.code not in RETRYABLE_HTTP_STATUS or is_last_attempt:
                    error_body = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(
                        f"Reranking model request failed with HTTP {exc.code}: {sanitize_error(error_body)}"
                    ) from exc
            except urllib.error.URLError as exc:
                if is_last_attempt:
                    raise RuntimeError(f"Reranking model request failed: {exc.reason}") from exc
            self._sleep_before_retry(attempt)
        # Defensive: the loop either returns or raises on the last attempt.
        raise RuntimeError("Reranking model request failed after retries")

    def _sleep_before_retry(self, attempt: int) -> None:
        if self.retry_backoff_seconds <= 0:
            return
        time.sleep(self.retry_backoff_seconds * attempt)

    def _endpoint_url(self) -> str:
        normalized_base_url = self.base_url.rstrip("/")
        if normalized_base_url.endswith("/rerank"):
            return normalized_base_url
        return f"{normalized_base_url}/rerank"


def create_reranking_provider(
    provider_name: str | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
) -> ReRankingProvider | None:
    provider = (provider_name or "deterministic").strip().casefold()
    if provider in {"none", "off", "disabled", "false"}:
        return None
    if provider in {"", "deterministic", "fake", "local"}:
        return DeterministicReRankingProvider(
            model_name=(model_name or "keyword-overlap-reranker-v1").strip()
            or "keyword-overlap-reranker-v1"
        )
    if provider in {
        "openai-compatible",
        "openai",
        "compatible",
        "domestic",
        "jina",
        "cohere",
        "siliconflow",
        "paratera",
    }:
        return OpenAICompatibleReRankingProvider(
            model_name=(model_name or "").strip(),
            api_key=(api_key or "").strip(),
            base_url=(base_url or "").strip(),
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"Unsupported reranking provider: {provider_name}")


def validate_rerank_inputs(query: str, candidates: Sequence[str], top_k: int) -> None:
    if not query.strip():
        raise ValueError("query must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")
    if any(not candidate.strip() for candidate in candidates):
        raise ValueError("candidates must not contain empty content")


def tokenize(text: str) -> list[str]:
    return [match.group(0).casefold() for match in TOKEN_RE.finditer(text or "")]


def deterministic_rerank_score(query_terms: Sequence[str], candidate: str) -> float:
    if not query_terms:
        return 0.0
    normalized_candidate = candidate.casefold()
    matched_weight = 0.0
    for term in query_terms:
        if term in normalized_candidate:
            matched_weight += 1.0 if len(term) > 1 else 0.5
    coverage = matched_weight / max(1.0, float(len(query_terms)))
    density = matched_weight / max(1.0, float(len(tokenize(candidate))))
    return coverage + density


def parse_openai_compatible_rerank_response(
    response_data: dict[str, Any],
    candidates: Sequence[str],
    top_k: int,
) -> list[ReRankResult]:
    raw_results = response_data.get("results")
    if not isinstance(raw_results, list):
        raise RuntimeError("Reranking model response did not include results")

    parsed: list[ReRankResult] = []
    for item in raw_results:
        if not isinstance(item, dict):
            raise RuntimeError("Reranking model result is not an object")
        index = parse_result_index(item)
        if index < 0 or index >= len(candidates):
            raise RuntimeError("Reranking model result index is out of range")
        parsed.append(
            ReRankResult(
                index=index,
                score=parse_result_score(item),
                content=parse_result_content(item, candidates[index]),
            )
        )
    return sorted(parsed, key=lambda item: (-item.score, item.index))[:top_k]


def urlopen_without_proxy(
    request: urllib.request.Request,
    timeout: float,
):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(request, timeout=timeout)


def parse_result_index(item: dict[str, Any]) -> int:
    raw_index = item.get("index")
    if raw_index is None:
        raw_index = item.get("document", {}).get("index") if isinstance(item.get("document"), dict) else None
    if not isinstance(raw_index, int):
        raise RuntimeError("Reranking model result index is not an integer")
    return raw_index


def parse_result_score(item: dict[str, Any]) -> float:
    raw_score = item.get("relevance_score", item.get("score"))
    if not isinstance(raw_score, (int, float)):
        raise RuntimeError("Reranking model result score is not numeric")
    return float(raw_score)


def parse_result_content(item: dict[str, Any], fallback: str) -> str:
    document = item.get("document")
    if isinstance(document, dict):
        text = document.get("text")
        if isinstance(text, str) and text.strip():
            return text
    return fallback


def sanitize_error(message: str) -> str:
    return message.replace("\n", " ")[:500]
