from __future__ import annotations

import json
from collections.abc import Sequence
from types import SimpleNamespace

from app.core.config import Settings
from app.schemas.agent import AgentQueryResponse
from app.services.cache.semantic_cache import (
    RedisSemanticCache,
    encode_float32_vector,
    get_configured_semantic_cache,
    parse_ft_search_payload,
    semantic_cache_request_is_eligible,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.query_embedding_cache import clear_query_embedding_cache
from tests.test_agent_api import make_test_client


class CountingEmbeddingProvider:
    def __init__(self, *, dimension: int = 8) -> None:
        self.delegate = DeterministicEmbeddingProvider(dimension=dimension)
        self.provider_name = self.delegate.provider_name
        self.model_name = self.delegate.model_name
        self.dimension = self.delegate.dimension
        self.query_calls = 0

    def embed_query(self, query: str) -> list[float]:
        self.query_calls += 1
        return self.delegate.embed_query(query)

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return self.delegate.embed_texts(texts)


class FakeRedis:
    def __init__(self) -> None:
        self.index_created = False
        self.hashes: dict[str, dict[str, object]] = {}
        self.ttl: dict[str, int] = {}
        self.search_distance = 0.03
        self.fail_search = False

    def execute_command(self, *args):
        command = args[0]
        if command == "FT.INFO":
            if not self.index_created:
                raise RuntimeError("missing index")
            return []
        if command == "FT.CREATE":
            self.index_created = True
            return b"OK"
        if command == "FT.SEARCH":
            if self.fail_search:
                raise RuntimeError("search unavailable")
            if not self.hashes:
                return [0]
            payload = next(iter(self.hashes.values()))["payload"]
            return [1, b"semcache:key", [b"payload", payload, b"distance", str(self.search_distance).encode()]]
        raise AssertionError(f"unexpected redis command: {args}")

    def hset(self, key: str, *, mapping: dict[str, object]) -> int:
        self.hashes[key] = mapping
        return len(mapping)

    def expire(self, key: str, ttl_seconds: int) -> bool:
        self.ttl[key] = ttl_seconds
        return True


def response_fixture() -> AgentQueryResponse:
    return AgentQueryResponse.model_validate(
        {
            "question": "What affects filling capacity?",
            "answer": "Filling capacity is affected by aggregate voids. [1]",
            "tool_calls": [
                {
                    "tool_name": "answer_with_citations",
                    "input_summary": "question=...",
                    "output_summary": "sources=1",
                    "succeeded": True,
                    "error": None,
                }
            ],
            "search_results": [],
            "sources": [
                {
                    "source_id": "chunk:1",
                    "title": "Fixture",
                    "source_type": "local_file",
                    "status": None,
                    "trust_level": None,
                    "fulltext_permission": None,
                    "document_id": 1,
                    "chunk_id": 1,
                    "chunk_index": 0,
                    "url": None,
                    "doi": None,
                    "content": None,
                    "score": None,
                    "chunk_type": "text",
                }
            ],
            "citations": [1],
            "refused": False,
            "refusal_reason": None,
            "reasoning_summary": "fixture",
            "mode": "langgraph_agent",
            "workflow_steps": [],
            "iteration_count": 2,
            "invalid_citations": [],
            "refusal_category": None,
            "latency_trace": {},
        }
    )


def test_semantic_cache_stores_minimal_answer_payload_and_hits() -> None:
    clear_query_embedding_cache()
    redis_client = FakeRedis()
    provider = CountingEmbeddingProvider()
    cache = RedisSemanticCache(redis_client, similarity_threshold=0.92, ttl_seconds=60)

    stored = cache.store(
        query="  What affects   filling capacity? ",
        mode="langgraph_agent",
        embedding_provider=provider,
        response=response_fixture(),
    )
    lookup = cache.lookup(
        query="What affects filling capacity?",
        mode="langgraph_agent",
        embedding_provider=provider,
    )

    assert stored is True
    assert lookup.hit is True
    assert lookup.response is not None
    assert lookup.response.answer.startswith("Filling capacity")
    assert lookup.response.tool_calls == []
    assert lookup.response.search_results == []
    assert lookup.response.sources[0].source_id == "chunk:1"
    assert lookup.response.latency_trace["semantic_cache_hit"] is True
    payload = json.loads(next(iter(redis_client.hashes.values()))["payload"])
    assert set(payload) == {
        "query",
        "answer",
        "sources",
        "citations",
        "mode",
        "embedding_provider",
        "embedding_model",
        "embedding_dimension",
        "cache_context",
        "created_at",
    }
    assert provider.query_calls <= 1


def test_semantic_cache_miss_when_embedding_identity_differs() -> None:
    clear_query_embedding_cache()
    redis_client = FakeRedis()
    provider = CountingEmbeddingProvider(dimension=8)
    cache = RedisSemanticCache(redis_client, similarity_threshold=0.92, ttl_seconds=60)
    cache.store(
        query="What affects filling capacity?",
        mode="langgraph_agent",
        embedding_provider=provider,
        response=response_fixture(),
    )
    other_provider = CountingEmbeddingProvider(dimension=16)

    lookup = cache.lookup(
        query="What affects filling capacity?",
        mode="langgraph_agent",
        embedding_provider=other_provider,
    )

    assert lookup.hit is False
    assert lookup.response is None
    assert lookup.reason == "embedding_identity_mismatch"


def test_semantic_cache_miss_when_similarity_is_below_threshold() -> None:
    clear_query_embedding_cache()
    redis_client = FakeRedis()
    provider = CountingEmbeddingProvider()
    cache = RedisSemanticCache(redis_client, similarity_threshold=0.92)
    cache.store(
        query="filling capacity",
        mode="langgraph_agent",
        embedding_provider=provider,
        response=response_fixture(),
    )
    redis_client.search_distance = 0.2

    lookup = cache.lookup(
        query="nearby question",
        mode="langgraph_agent",
        embedding_provider=provider,
    )

    assert lookup.hit is False
    assert lookup.response is None
    assert lookup.reason == "below_threshold"
    assert lookup.similarity == 0.8


def test_semantic_cache_skips_gracefully_when_redis_search_fails() -> None:
    clear_query_embedding_cache()
    redis_client = FakeRedis()
    redis_client.fail_search = True
    provider = CountingEmbeddingProvider()
    cache = RedisSemanticCache(redis_client)

    lookup = cache.lookup(
        query="filling capacity",
        mode="langgraph_agent",
        embedding_provider=provider,
    )

    assert lookup.hit is False
    assert lookup.response is None
    assert lookup.reason.startswith("redis_skip:")


def test_semantic_cache_config_and_request_eligibility(monkeypatch) -> None:
    assert get_configured_semantic_cache(settings=Settings(semantic_cache_enabled=False)) is None
    assert semantic_cache_request_is_eligible(
        conversation_id=None,
        history=[],
        source_id=None,
        image_path=None,
    )
    assert not semantic_cache_request_is_eligible(
        conversation_id=1,
        history=[],
        source_id=None,
        image_path=None,
    )
    assert semantic_cache_request_is_eligible(
        conversation_id=1,
        history=["user: repeated question", "assistant: previous answer"],
        source_id=None,
        image_path=None,
        query="repeated question",
        conversation_messages=[
            SimpleNamespace(role="user", content="repeated question"),
            SimpleNamespace(role="assistant", content="previous answer"),
        ],
    )
    assert not semantic_cache_request_is_eligible(
        conversation_id=1,
        history=["user: different question", "assistant: previous answer"],
        source_id=None,
        image_path=None,
        query="new question",
        conversation_messages=[
            SimpleNamespace(role="user", content="different question"),
            SimpleNamespace(role="assistant", content="previous answer"),
        ],
    )
    assert semantic_cache_request_is_eligible(
        conversation_id=1,
        history=["user: 堆石混凝土的性能", "assistant: previous answer"],
        source_id=None,
        image_path=None,
        query="堆石混凝土的性能有哪些？",
        conversation_messages=[
            SimpleNamespace(role="user", content="堆石混凝土的性能"),
            SimpleNamespace(role="assistant", content="previous answer"),
        ],
    )
    assert not semantic_cache_request_is_eligible(
        conversation_id=1,
        history=["user: 堆石混凝土的性能", "assistant: previous answer"],
        source_id=None,
        image_path=None,
        query="它有哪些？",
        conversation_messages=[
            SimpleNamespace(role="user", content="堆石混凝土的性能"),
            SimpleNamespace(role="assistant", content="previous answer"),
        ],
    )
    assert not semantic_cache_request_is_eligible(
        conversation_id=None,
        history=["previous"],
        source_id=None,
        image_path=None,
    )


def test_parse_ft_search_payload_and_vector_encoding() -> None:
    payload, distance = parse_ft_search_payload(
        [1, b"semcache:key", [b"payload", b"{\"answer\":\"ok\"}", b"distance", b"0.05"]]
    )

    assert payload == "{\"answer\":\"ok\"}"
    assert distance == 0.05
    assert len(encode_float32_vector([0.1, 0.2, 0.3])) == 12


def test_agent_query_returns_semantic_cache_hit_without_running_agent(
    monkeypatch,
    tmp_path,
) -> None:
    from app.api import agent as agent_api

    class FakeLookup:
        response = AgentQueryResponse.model_validate(
            {
                "question": "cached question",
                "answer": "cached answer [1]",
                "tool_calls": [],
                "search_results": [],
                "sources": [],
                "citations": [1],
                "refused": False,
                "refusal_reason": None,
                "reasoning_summary": "semantic_cache_hit: reused cached agent answer",
                "mode": "langgraph_agent",
                "workflow_steps": [],
                "iteration_count": 0,
                "invalid_citations": [],
                "refusal_category": None,
                "latency_trace": {
                    "semantic_cache_hit": True,
                    "semantic_cache_similarity": 0.97,
                },
            }
        )

    class FakeSemanticCache:
        def __init__(self) -> None:
            self.lookup_calls = 0
            self.store_calls = 0

        def lookup(self, **_kwargs):
            self.lookup_calls += 1
            return FakeLookup()

        def store(self, **_kwargs):
            self.store_calls += 1
            return True

    fake_cache = FakeSemanticCache()
    monkeypatch.setattr(agent_api, "get_configured_semantic_cache", lambda: fake_cache)

    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity?",
                "mode": "langgraph_agent",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["answer"] == "cached answer [1]"
    assert payload["tool_calls"] == []
    assert payload["latency_trace"]["semantic_cache_hit"] is True
    assert payload["latency_trace"]["semantic_cache_similarity"] == 0.97
    assert fake_cache.lookup_calls == 1
    assert fake_cache.store_calls == 0


def test_agent_stream_returns_semantic_cache_hit_without_running_agent(
    monkeypatch,
    tmp_path,
) -> None:
    from app.api import agent as agent_api

    class FakeLookup:
        response = AgentQueryResponse.model_validate(
            {
                "question": "cached question",
                "answer": "cached stream answer [1]",
                "tool_calls": [],
                "search_results": [],
                "sources": [],
                "citations": [1],
                "refused": False,
                "refusal_reason": None,
                "reasoning_summary": "semantic_cache_hit: reused cached agent answer",
                "mode": "tool_calling_agent",
                "workflow_steps": [],
                "iteration_count": 0,
                "invalid_citations": [],
                "refusal_category": None,
                "latency_trace": {
                    "semantic_cache_hit": True,
                    "semantic_cache_similarity": 0.99,
                },
            }
        )

    class FakeSemanticCache:
        def __init__(self) -> None:
            self.lookup_calls = 0
            self.store_calls = 0

        def lookup(self, **_kwargs):
            self.lookup_calls += 1
            return FakeLookup()

        def store(self, **_kwargs):
            self.store_calls += 1
            return True

    def fail_stream_agent(*_args, **_kwargs):
        raise AssertionError("stream cache hit should not run the agent")

    fake_cache = FakeSemanticCache()
    monkeypatch.setattr(agent_api, "get_configured_semantic_cache", lambda: fake_cache)
    monkeypatch.setattr(agent_api, "stream_non_chitchat_agent_response", fail_stream_agent)

    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query/stream",
            json={
                "question": "What affects filling capacity?",
                "mode": "tool_calling_agent",
            },
        )

    assert response.status_code == 200
    assert "cached stream answer" in response.text
    assert '"semantic_cache_hit":true' in response.text
    assert '"semantic_cache_similarity":0.99' in response.text
    assert fake_cache.lookup_calls == 1
    assert fake_cache.store_calls == 0
