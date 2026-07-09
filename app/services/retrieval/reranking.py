from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.generation.http_pool import HTTP_JSON_CONNECTION_POOL
from app.services.observability.latency_trace import get_current_latency_trace


TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")
ENGLISH_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "according",
    "be",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "or",
    "the",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}

# Transient HTTP statuses worth retrying. 4xx client errors (bad key, bad
# request) are excluded because retrying them only wastes quota.
RETRYABLE_HTTP_STATUS = frozenset({429, 500, 502, 503, 504})
_RERANKER_UNAVAILABLE_UNTIL: dict[str, float] = {}
_RERANKER_UNAVAILABLE_LOCK = threading.Lock()


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
    health_check_enabled: bool = False
    health_check_timeout_seconds: float = 2.0
    unavailable_ttl_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if not self.base_url.strip():
            raise ValueError("base_url must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be greater than 0")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be greater than or equal to 0")
        if self.health_check_timeout_seconds <= 0:
            raise ValueError("health_check_timeout_seconds must be greater than 0")
        if self.unavailable_ttl_seconds < 0:
            raise ValueError("unavailable_ttl_seconds must be greater than or equal to 0")

    def rerank(
        self,
        query: str,
        candidates: Sequence[str],
        top_k: int = 5,
    ) -> list[ReRankResult]:
        validate_rerank_inputs(query, candidates, top_k)
        self._ensure_available_for_request()
        payload = {
            "model": self.model_name,
            "query": query.strip(),
            "documents": list(candidates),
            "top_n": min(top_k, len(candidates)),
        }
        request = urllib.request.Request(
            self._endpoint_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        response_data = self._request_with_retry(request)
        return parse_openai_compatible_rerank_response(response_data, candidates, top_k)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "rfc-rag-agent/reranking-provider",
        }
        if self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["api-key"] = self.api_key
        return headers

    def _request_with_retry(self, request: urllib.request.Request) -> dict[str, Any]:
        """Send the request, retrying transient network failures.

        Transient TLS/connection drops, timeouts, and 429/5xx responses are
        retried with a short backoff. Other 4xx responses fail immediately
        because retrying them cannot help.
        """

        for attempt in range(1, self.max_attempts + 1):
            is_last_attempt = attempt >= self.max_attempts
            self._trace_attempt(attempt)
            try:
                response_data = request_json_without_proxy(
                    request,
                    timeout=self.timeout_seconds,
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                )
                return response_data
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

    def _ensure_available_for_request(self) -> None:
        if not self.health_check_enabled:
            return
        cache_key = self._availability_cache_key()
        now = time.monotonic()
        with _RERANKER_UNAVAILABLE_LOCK:
            unavailable_until = _RERANKER_UNAVAILABLE_UNTIL.get(cache_key, 0.0)
        trace = get_current_latency_trace()
        if unavailable_until > now:
            if trace is not None:
                trace.set_value("reranking_primary_health_status", "cached_unavailable")
                trace.set_value("reranking_primary_health_cache_hit", True)
            raise RuntimeError("Reranking primary service unavailable: cached health check failure")
        started = time.perf_counter()
        if trace is not None:
            trace.set_value("reranking_primary_health_cache_hit", False)
            trace.set_value("reranking_primary_health_status", "checking")
        try:
            request = urllib.request.Request(
                self._health_url(),
                headers={"Accept": "application/json", "User-Agent": "rfc-rag-agent/reranking-health"},
                method="GET",
            )
            with urlopen_without_proxy(request, timeout=self.health_check_timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if status >= 400:
                    raise RuntimeError(f"health endpoint returned HTTP {status}")
                response.read(512)
        except Exception as exc:
            self._mark_unavailable(cache_key)
            if trace is not None:
                trace.set_value("reranking_primary_health_status", "unavailable")
                trace.set_value("reranking_primary_health_error", type(exc).__name__)
            raise RuntimeError("Reranking primary service unavailable: health check failed") from exc
        finally:
            if trace is not None:
                trace.add_duration(
                    "reranking_primary_health_latency_ms",
                    (time.perf_counter() - started) * 1000.0,
                )
        if trace is not None:
            trace.set_value("reranking_primary_health_status", "ok")
            trace.set_value("reranking_primary_health_error", "")

    def _mark_unavailable(self, cache_key: str) -> None:
        if self.unavailable_ttl_seconds <= 0:
            return
        with _RERANKER_UNAVAILABLE_LOCK:
            _RERANKER_UNAVAILABLE_UNTIL[cache_key] = time.monotonic() + self.unavailable_ttl_seconds

    def _availability_cache_key(self) -> str:
        return f"{self.provider_name}|{self.model_name}|{self._health_url()}"

    def _health_url(self) -> str:
        normalized_base_url = self.base_url.rstrip("/")
        if normalized_base_url.endswith("/rerank"):
            normalized_base_url = normalized_base_url[: -len("/rerank")]
        if normalized_base_url.endswith("/v1"):
            normalized_base_url = normalized_base_url[: -len("/v1")]
        return f"{normalized_base_url}/health"

    def _sleep_before_retry(self, attempt: int) -> None:
        if self.retry_backoff_seconds <= 0:
            return
        duration = self.retry_backoff_seconds * attempt
        trace = get_current_latency_trace()
        if trace is not None:
            trace.add_duration("provider_http_retry_backoff_ms", duration * 1000.0)
        time.sleep(duration)

    def _trace_attempt(self, attempt: int) -> None:
        trace = get_current_latency_trace()
        if trace is None:
            return
        trace.set_value("provider_http_last_provider", self.provider_name)
        trace.set_value("provider_http_last_model", self.model_name)
        trace.set_value("provider_http_last_attempt", attempt)
        count = int(trace.values.get("provider_http_attempt_count", 0)) + 1
        trace.set_value("provider_http_attempt_count", count)

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
    health_check_enabled: bool | None = None,
    health_check_timeout_seconds: float = 2.0,
    unavailable_ttl_seconds: float = 30.0,
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
        "zhipu",
        "glm",
        "bigmodel",
        "remote-bge-lora",
        "bge-lora",
        "rfc-bge-lora",
        "rfc-domain-bge-lora",
    }:
        default_model = "rfc-domain-bge-lora" if provider in {
            "remote-bge-lora",
            "bge-lora",
            "rfc-bge-lora",
            "rfc-domain-bge-lora",
        } else ""
        default_base_url = "http://127.0.0.1:8091" if provider in {
            "remote-bge-lora",
            "bge-lora",
            "rfc-bge-lora",
            "rfc-domain-bge-lora",
        } else ""
        is_remote_bge = provider in {
            "remote-bge-lora",
            "bge-lora",
            "rfc-bge-lora",
            "rfc-domain-bge-lora",
        }
        if provider in {"zhipu", "glm", "bigmodel"}:
            default_base_url = "https://open.bigmodel.cn/api/paas/v4"
        resolved_api_key = (api_key or "").strip()
        if not resolved_api_key and provider == "paratera":
            resolved_api_key = (
                os.getenv("RERANKING_FALLBACK_API_KEY", "").strip()
                or os.getenv("EMBEDDING_API_KEY", "").strip()
                or os.getenv("PARATERA_API_KEY", "").strip()
            )
        if not resolved_api_key and provider in {"zhipu", "glm", "bigmodel"}:
            resolved_api_key = (
                os.getenv("RERANKING_FALLBACK_API_KEY", "").strip()
                or os.getenv("ZHIPU_API_KEY", "").strip()
                or os.getenv("GLM_API_KEY", "").strip()
                or os.getenv("BIGMODEL_API_KEY", "").strip()
            )
        return OpenAICompatibleReRankingProvider(
            model_name=(model_name or default_model).strip(),
            api_key=resolved_api_key,
            base_url=(base_url or default_base_url).strip(),
            timeout_seconds=timeout_seconds,
            provider_name=provider,
            health_check_enabled=is_remote_bge if health_check_enabled is None else health_check_enabled,
            health_check_timeout_seconds=health_check_timeout_seconds,
            unavailable_ttl_seconds=unavailable_ttl_seconds,
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
    tokens = [match.group(0).casefold() for match in TOKEN_RE.finditer(text or "")]
    return [token for token in tokens if token not in ENGLISH_STOPWORDS]


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
    if raw_results is None and isinstance(response_data.get("scores"), list):
        raw_results = [
            {"index": index, "score": score}
            for index, score in enumerate(response_data["scores"])
        ]
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
