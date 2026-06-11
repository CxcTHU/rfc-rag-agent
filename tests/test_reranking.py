from app.services.retrieval.reranking import (
    DeterministicReRankingProvider,
    OpenAICompatibleReRankingProvider,
    create_reranking_provider,
    parse_openai_compatible_rerank_response,
)


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
