import io
import json
import urllib.error

from app.services.retrieval.reranking import (
    DeterministicReRankingProvider,
    OpenAICompatibleReRankingProvider,
    create_reranking_provider,
    parse_openai_compatible_rerank_response,
    tokenize,
)


class _RerankFakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(
            {"results": [{"index": 0, "relevance_score": 0.9, "document": {"text": "first"}}]}
        ).encode("utf-8")


def test_deterministic_reranker_orders_by_query_overlap() -> None:
    provider = DeterministicReRankingProvider()

    results = provider.rerank(
        query="filling capacity concrete",
        candidates=[
            "Thermal control and hydration heat.",
            "Filling capacity depends on concrete flowability.",
        ],
        top_k=2,
    )

    assert [result.index for result in results] == [1, 0]
    assert results[0].score > results[1].score


def test_reranker_tokenize_filters_common_english_stopwords() -> None:
    assert tokenize("What is RCC and which standards did Jin Feng edit?") == [
        "rcc",
        "standards",
        "jin",
        "feng",
        "edit",
    ]


def test_deterministic_reranker_rejects_invalid_inputs() -> None:
    provider = DeterministicReRankingProvider()

    try:
        provider.rerank("   ", ["candidate"], top_k=1)
    except ValueError as exc:
        assert "query" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty query")

    try:
        provider.rerank("query", ["candidate"], top_k=0)
    except ValueError as exc:
        assert "top_k" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid top_k")


def test_parse_openai_compatible_rerank_response() -> None:
    payload = {
        "results": [
            {"index": 1, "relevance_score": 0.91, "document": {"text": "second"}},
            {"index": 0, "relevance_score": 0.20, "document": {"text": "first"}},
        ]
    }

    results = parse_openai_compatible_rerank_response(payload, ["first", "second"], top_k=1)

    assert len(results) == 1
    assert results[0].index == 1
    assert results[0].score == 0.91
    assert results[0].content == "second"


def test_parse_openai_compatible_rerank_response_supports_scores_array() -> None:
    payload = {"scores": [0.12, 0.94, 0.50]}

    results = parse_openai_compatible_rerank_response(
        payload,
        ["first", "second", "third"],
        top_k=2,
    )

    assert [result.index for result in results] == [1, 2]
    assert [result.content for result in results] == ["second", "third"]


def test_reranker_retries_transient_ssl_error(monkeypatch) -> None:
    attempts = {"count": 0}

    def flaky_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise urllib.error.URLError("[SSL: UNEXPECTED_EOF_WHILE_READING]")
        return _RerankFakeResponse()

    monkeypatch.setattr(
        "app.services.retrieval.reranking.urlopen_without_proxy", flaky_urlopen
    )
    provider = OpenAICompatibleReRankingProvider(
        model_name="BAAI/bge-reranker-v2-m3",
        api_key="test-key",
        base_url="https://api.siliconflow.cn/v1",
        retry_backoff_seconds=0,
    )

    results = provider.rerank("filling capacity", ["first", "second"], top_k=1)

    assert results[0].index == 0
    assert attempts["count"] == 2


def test_reranker_does_not_retry_client_error(monkeypatch) -> None:
    attempts = {"count": 0}

    def http_error_urlopen(request, timeout):
        attempts["count"] += 1
        raise urllib.error.HTTPError(
            url="https://api.siliconflow.cn/v1/rerank",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b"Unauthorized"),
        )

    monkeypatch.setattr(
        "app.services.retrieval.reranking.urlopen_without_proxy", http_error_urlopen
    )
    provider = OpenAICompatibleReRankingProvider(
        model_name="BAAI/bge-reranker-v2-m3",
        api_key="test-key",
        base_url="https://api.siliconflow.cn/v1",
        retry_backoff_seconds=0,
    )

    raised = False
    try:
        provider.rerank("filling capacity", ["first", "second"], top_k=1)
    except RuntimeError as exc:
        raised = "HTTP 401" in str(exc)
    assert raised
    assert attempts["count"] == 1


def test_create_reranking_provider_supports_none_and_openai_compatible() -> None:
    assert create_reranking_provider("none") is None

    provider = create_reranking_provider(
        "openai-compatible",
        model_name="rerank-model",
        api_key="test-key",
        base_url="https://example.test",
    )

    assert isinstance(provider, OpenAICompatibleReRankingProvider)
    assert provider.model_name == "rerank-model"


def test_create_reranking_provider_supports_paratera_with_subpath() -> None:
    provider = create_reranking_provider(
        "paratera",
        model_name="GLM-Rerank",
        api_key="test-key",
        base_url="https://llmapi.paratera.com/v1/p002",
    )

    assert isinstance(provider, OpenAICompatibleReRankingProvider)
    # The /v1/p002 subpath must be preserved when appending /rerank.
    assert provider._endpoint_url() == "https://llmapi.paratera.com/v1/p002/rerank"


def test_openai_compatible_reranker_allows_private_service_without_api_key(monkeypatch) -> None:
    seen = {}

    def fake_urlopen(request, timeout):
        seen["headers"] = dict(request.header_items())
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return _RerankFakeResponse()

    monkeypatch.setattr(
        "app.services.retrieval.reranking.urlopen_without_proxy", fake_urlopen
    )
    provider = OpenAICompatibleReRankingProvider(
        model_name="bge-reranker-base-rfc-lora",
        api_key="",
        base_url="http://127.0.0.1:8091/v1",
        retry_backoff_seconds=0,
    )

    provider.rerank("query", ["doc"], top_k=1)

    assert seen["body"]["model"] == "bge-reranker-base-rfc-lora"
    assert seen["body"]["documents"] == ["doc"]
    assert "Authorization" not in seen["headers"]
    assert "Api-key" not in seen["headers"]


def test_create_reranking_provider_supports_remote_bge_lora_alias() -> None:
    provider = create_reranking_provider("remote-bge-lora")

    assert isinstance(provider, OpenAICompatibleReRankingProvider)
    assert provider.provider_name == "remote-bge-lora"
    assert provider.model_name == "rfc-domain-bge-lora"
    assert provider.base_url == "http://127.0.0.1:8091"
