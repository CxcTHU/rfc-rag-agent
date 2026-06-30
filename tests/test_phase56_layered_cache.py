from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base, Chunk
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.agent.tools import AgentToolbox
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService
from app.services.retrieval.reranking import ReRankResult
from app.services.retrieval.vector_index import VectorIndexService

import pytest


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value.encode("utf-8")


def make_session(tmp_path):
    database_path = tmp_path / "phase56_cache.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def seed_documents(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Phase 56 filling capacity guide",
            source_type="local_file",
            source_path="phase56-filling.md",
            file_name="phase56-filling.md",
            file_extension=".md",
            content_hash="phase56-filling",
            raw_path="data/raw/phase56-filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Rock-filled concrete filling capacity depends on self-compacting "
                    "concrete flowability in rock voids."
                ),
                char_count=104,
                heading_path="Filling",
                start_char=0,
                end_char=104,
            )
        ],
    )


def enable_layered_cache(monkeypatch, fake_redis: FakeRedis, *layers: str) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://phase56-test")
    monkeypatch.setenv("LAYERED_CACHE_NAMESPACE", "phase56-test")
    monkeypatch.setenv("RETRIEVAL_CANDIDATE_CACHE_ENABLED", str("retrieval" in layers).lower())
    monkeypatch.setenv("RERANK_ORDER_CACHE_ENABLED", str("rerank" in layers).lower())
    monkeypatch.setenv("TOOL_RESULT_CACHE_ENABLED", str("tool" in layers).lower())
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.cache.layered_cache.get_redis_client",
        lambda settings=None: fake_redis,
    )


def test_phase56_retrieval_candidate_cache_skips_second_keyword_vector_run(
    monkeypatch,
    tmp_path,
) -> None:
    fake_redis = FakeRedis()
    enable_layered_cache(monkeypatch, fake_redis, "retrieval")
    TestingSessionLocal = make_session(tmp_path)
    keyword_calls = 0
    vector_calls = 0

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_documents(db)
        VectorIndexService(db, provider).build_index()

        original_keyword_search = (
            __import__("app.services.retrieval.hybrid_search", fromlist=["KeywordSearchService"])
            .KeywordSearchService.search
        )
        original_vector_search = (
            __import__("app.services.retrieval.hybrid_search", fromlist=["VectorSearchService"])
            .VectorSearchService.search
        )

        def counted_keyword_search(self, query: str, top_k: int = 5):
            nonlocal keyword_calls
            keyword_calls += 1
            return original_keyword_search(self, query, top_k)

        def counted_vector_search(self, query: str, top_k: int = 5):
            nonlocal vector_calls
            vector_calls += 1
            return original_vector_search(self, query, top_k)

        monkeypatch.setattr(
            "app.services.retrieval.hybrid_search.KeywordSearchService.search",
            counted_keyword_search,
        )
        monkeypatch.setattr(
            "app.services.retrieval.hybrid_search.VectorSearchService.search",
            counted_vector_search,
        )

        first = HybridSearchService(db, provider, parallel=False, reranking_enabled=False).search(
            "filling capacity rock-filled concrete",
            top_k=1,
        )
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            second = HybridSearchService(db, provider, parallel=False, reranking_enabled=False).search(
                "filling capacity rock-filled concrete",
                top_k=1,
            )
        finally:
            reset_current_latency_trace(token)

    assert first[0].chunk_id == second[0].chunk_id
    assert keyword_calls == 1
    assert vector_calls == 1
    assert trace.values["retrieval_cache_hit"] is True


def test_phase56_rerank_order_cache_separates_provider_identity(monkeypatch, tmp_path) -> None:
    fake_redis = FakeRedis()
    enable_layered_cache(monkeypatch, fake_redis, "rerank")
    TestingSessionLocal = make_session(tmp_path)

    class CountingReranker:
        def __init__(self, provider_name: str) -> None:
            self.provider_name = provider_name
            self.model_name = "model-a"
            self.calls = 0

        def rerank(self, query, candidates, top_k=5):
            self.calls += 1
            return [
                ReRankResult(index=index, score=float(len(candidates) - index), content=candidates[index])
                for index in range(min(top_k, len(candidates)))
            ]

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_documents(db)
        VectorIndexService(db, provider).build_index()
        bge = CountingReranker("remote-bge-lora")
        glm = CountingReranker("paratera")

        HybridSearchService(db, provider, reranking_provider=bge, reranking_enabled=True).search(
            "filling capacity",
            top_k=1,
        )
        HybridSearchService(db, provider, reranking_provider=bge, reranking_enabled=True).search(
            "filling capacity",
            top_k=1,
        )
        HybridSearchService(db, provider, reranking_provider=glm, reranking_enabled=True).search(
            "filling capacity",
            top_k=1,
        )

    assert bge.calls == 1
    assert glm.calls == 1


def test_phase56_tool_result_cache_bypasses_second_tool_execution(monkeypatch, tmp_path) -> None:
    fake_redis = FakeRedis()
    enable_layered_cache(monkeypatch, fake_redis, "tool")
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_documents(db)
        VectorIndexService(db, provider).build_index()
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        first = toolbox.hybrid_search_knowledge("filling capacity", top_k=1)
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            second = toolbox.hybrid_search_knowledge("filling capacity", top_k=1)
        finally:
            reset_current_latency_trace(token)

    assert first.sources[0].chunk_id == second.sources[0].chunk_id
    assert second.call.output_summary.startswith("cache hit")
    assert trace.values["tool_result_cache_hit"] is True


def test_phase56_tool_result_cache_preserves_dynamic_hybrid_result_count(monkeypatch, tmp_path) -> None:
    fake_redis = FakeRedis()
    enable_layered_cache(monkeypatch, fake_redis, "tool")
    monkeypatch.setenv("RERANKING_DYNAMIC_TOP_K_ENABLED", "true")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        document = DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Dynamic hybrid evidence",
                source_type="local_file",
                source_path="dynamic.md",
                file_name="dynamic.md",
                file_extension=".md",
                content_hash="phase56-dynamic-hybrid",
                raw_path="data/raw/dynamic.md",
            ),
            [
                ChunkCreate(
                    chunk_index=index,
                    content=f"Dynamic hybrid evidence chunk {index}",
                    char_count=31,
                    heading_path="Dynamic",
                    start_char=index * 31,
                    end_char=(index + 1) * 31,
                )
                for index in range(12)
            ],
        )
        chunks = list(db.execute(select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.id)).scalars())
        calls = {"count": 0}

        def fake_search(self, query: str, top_k: int = 5):
            calls["count"] += 1
            return [
                HybridSearchResult(
                    document_id=document.id,
                    document_title=document.title,
                    source_type=document.source_type,
                    source_path=document.source_path,
                    file_name=document.file_name,
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    heading_path=chunk.heading_path,
                    score=1.0 - index * 0.01,
                    keyword_score=1.0,
                    vector_score=1.0,
                    channels=("hybrid",),
                )
                for index, chunk in enumerate(chunks)
            ]

        monkeypatch.setattr(
            "app.services.agent.tools.HybridSearchService.search",
            fake_search,
        )
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        first = toolbox.hybrid_search_knowledge("dynamic evidence", top_k=8)
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            second = toolbox.hybrid_search_knowledge("dynamic evidence", top_k=8)
        finally:
            reset_current_latency_trace(token)

    assert calls["count"] == 1
    assert len(first.search_results) == 12
    assert len(second.search_results) == 12
    assert second.call.output_summary == "cache hit; returned 12 hybrid_search_knowledge results"
    assert trace.values["tool_result_cache_hit"] is True
    assert trace.values["retrieval_selected_count"] == 12


def test_phase56_tool_result_cache_uses_structured_identity_over_llm_canonical_text(
    monkeypatch,
    tmp_path,
) -> None:
    fake_redis = FakeRedis()
    enable_layered_cache(monkeypatch, fake_redis, "tool")
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_documents(db)
        VectorIndexService(db, provider).build_index()
        calls = {"count": 0}
        real_search = HybridSearchService.search

        def counted_search(self, query: str, top_k: int = 5):
            calls["count"] += 1
            return real_search(self, query=query, top_k=top_k)

        monkeypatch.setattr(
            "app.services.agent.tools.HybridSearchService.search",
            counted_search,
        )
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        first_trace = LatencyTrace()
        first_trace.set_value("evidence_cache_reuse_allowed", True)
        first_trace.set_value("evidence_canonical_query", "drawbacks of rock-filled concrete")
        first_trace.set_value("evidence_entity_key", "rock-filled concrete")
        first_trace.set_value("evidence_intent_key", "drawbacks_or_limitations")
        first_token = set_current_latency_trace(first_trace)
        try:
            first = toolbox.hybrid_search_knowledge("filling capacity", top_k=1)
        finally:
            reset_current_latency_trace(first_token)

        second_trace = LatencyTrace()
        second_trace.set_value("evidence_cache_reuse_allowed", True)
        second_trace.set_value("evidence_canonical_query", "堆石混凝土 缺点 劣势 不足")
        second_trace.set_value("evidence_entity_key", "rock-filled concrete")
        second_trace.set_value("evidence_intent_key", "drawbacks_or_limitations")
        second_token = set_current_latency_trace(second_trace)
        try:
            second = toolbox.hybrid_search_knowledge("another wording", top_k=1)
        finally:
            reset_current_latency_trace(second_token)

    assert calls["count"] == 1
    assert first.search_results
    assert second.search_results
    assert second.call.output_summary.startswith("cache hit")
    assert second_trace.values["tool_result_cache_hit"] is True


def test_phase56_layered_cache_fail_open_when_redis_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://phase56-test")
    monkeypatch.setenv("RETRIEVAL_CANDIDATE_CACHE_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.cache.layered_cache.get_redis_client",
        lambda settings=None: None,
    )
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_documents(db)
        VectorIndexService(db, provider).build_index()
        results = HybridSearchService(db, provider, reranking_enabled=False).search(
            "filling capacity",
            top_k=1,
        )

    assert results
