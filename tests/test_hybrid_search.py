import time

import pytest

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk
from app.db.repositories import ChunkCreate
from app.db.repositories import DocumentCreate
from app.db.repositories import DocumentRepository
from app.db.session import create_sqlite_engine
from app.core.config import Settings
from app.services.graphrag.graph_store import build_knowledge_graph, save_graph
from app.services.graphrag.schema import GraphEntity, GraphExtractionResult, GraphRelation
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.bm25_search import BM25SearchResult, BM25SearchService
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService
from app.services.retrieval.hybrid_search import normalize_score
from app.services.retrieval.runtime import (
    RetrievalIntentProfile,
    build_retrieval_plan,
    current_retrieval_plan,
    reset_current_retrieval_plan,
    set_current_retrieval_plan,
)
from app.services.retrieval.keyword_search import KeywordSearchResult
from app.services.retrieval.keyword_search import KeywordSearchService
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.reranking import ReRankResult
from app.services.retrieval.vector_search import VectorSearchResult
from app.services.retrieval.vector_index import VectorIndexService


def make_session(tmp_path):
    database_path = tmp_path / "hybrid_search.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_hybrid_documents(db: Session) -> None:
    repository = DocumentRepository(db)
    repository.create_with_chunks(
        DocumentCreate(
            title="Filling Capacity Evaluation of Self-Compacting Concrete",
            source_type="local_file",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="hybrid-filling-hash",
            raw_path="data/raw/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Filling capacity is evaluated by observing self compacting concrete flowability in prepacked rock voids.",
                char_count=101,
                heading_path="Filling",
                start_char=0,
                end_char=101,
            )
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="Thermal control note",
            source_type="metadata_record",
            source_path="thermal.md",
            file_name="thermal.md",
            file_extension=".md",
            content_hash="hybrid-thermal-hash",
            raw_path="data/raw/thermal.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Hydration heat and temperature control are discussed for rock filled concrete dams.",
                char_count=79,
                heading_path="Thermal",
                start_char=0,
                end_char=79,
            )
        ],
    )


def seed_multichannel_documents(db: Session) -> dict[str, int]:
    repository = DocumentRepository(db)
    repository.create_with_chunks(
        DocumentCreate(
            title="RFC Standard Relationship",
            source_type="standard_document",
            source_path="standard.pdf",
            file_name="standard.pdf",
            file_extension=".pdf",
            content_hash="phase57-standard-hash",
            raw_path="data/raw/standard.pdf",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="NB/T 10077 defines compressive strength requirements for rock-filled concrete.",
                char_count=78,
                heading_path="Standard",
                start_char=0,
                end_char=78,
            )
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="RFC Mix Ratio Table",
            source_type="local_file",
            source_path="table.md",
            file_name="table.md",
            file_extension=".md",
            content_hash="phase57-table-hash",
            raw_path="data/raw/table.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="| parameter | value |\n| water binder ratio | 0.32 |\n| aggregate ratio | 0.58 |",
                char_count=78,
                heading_path="Table",
                start_char=0,
                end_char=78,
                chunk_type="table",
            )
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="RFC Failure Figure",
            source_type="local_file",
            source_path="figure.pdf",
            file_name="figure.pdf",
            file_extension=".pdf",
            content_hash="phase57-figure-hash",
            raw_path="data/raw/figure.pdf",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="compression failure morphology image showing cracks in rock-filled concrete",
                char_count=72,
                heading_path="Figure",
                start_char=0,
                end_char=72,
                chunk_type="image_description",
                source_image_path="data/images/1/page1_img1.png",
                caption="Failure morphology curve and crack photo",
            )
        ],
    )
    rows = db.execute(select(Chunk)).scalars().all()
    return {chunk.chunk_type: chunk.id for chunk in rows}


def test_hybrid_search_uses_keyword_evidence_to_rank_expected_match(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()

        service = HybridSearchService(db, provider)
        original = service.settings.hybrid_multichannel_enabled
        try:
            service.settings.hybrid_multichannel_enabled = False
            results = service.search("filling capacity rock-filled concrete", top_k=2)
        finally:
            service.settings.hybrid_multichannel_enabled = original

    assert results
    assert results[0].document_title == "Filling Capacity Evaluation of Self-Compacting Concrete"
    assert results[0].keyword_score > 0
    assert results[0].score >= results[0].keyword_score * 0.7


def test_hybrid_search_returns_keyword_results_when_vector_index_is_missing(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)

        results = HybridSearchService(db, provider).search("filling capacity", top_k=2)

    assert results
    assert results[0].keyword_score > 0
    assert results[0].vector_score == 0
    assert "Filling Capacity" in results[0].document_title


def test_phase63_default_hybrid_uses_bm25_not_heuristic_keyword(tmp_path, monkeypatch) -> None:
    TestingSessionLocal = make_session(tmp_path)
    bm25_calls = 0
    original_bm25_search = BM25SearchService.search

    def counted_bm25_search(self, query: str, top_k: int = 5):
        nonlocal bm25_calls
        bm25_calls += 1
        return original_bm25_search(self, query, top_k=top_k)

    def forbidden_keyword_search(self, query: str, top_k: int = 5):
        raise AssertionError("default Hybrid must not call KeywordSearchService")

    monkeypatch.setattr(BM25SearchService, "search", counted_bm25_search)
    monkeypatch.setattr(KeywordSearchService, "search", forbidden_keyword_search)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        service = HybridSearchService(
            db,
            provider,
            parallel=False,
            reranking_enabled=False,
        )
        original = (
            service.settings.retrieval_candidate_cache_enabled,
            service.settings.rerank_order_cache_enabled,
        )
        try:
            service.settings.retrieval_candidate_cache_enabled = False
            service.settings.rerank_order_cache_enabled = False
            results = service.search("filling capacity", top_k=2)
        finally:
            (
                service.settings.retrieval_candidate_cache_enabled,
                service.settings.rerank_order_cache_enabled,
            ) = original

    assert bm25_calls == 1
    assert results
    assert "bm25" in results[0].channels


def test_hybrid_search_verified_defaults_are_enabled() -> None:
    settings = Settings(_env_file=None)

    assert settings.hybrid_multichannel_enabled is True
    assert settings.hybrid_graph_channel_enabled is True
    assert settings.hybrid_table_text_channel_enabled is True
    assert settings.hybrid_figure_caption_channel_enabled is True
    assert settings.reranking_dynamic_top_k_enabled is True
    assert settings.retrieval_candidate_cache_enabled is True
    assert settings.rerank_order_cache_enabled is True
    assert settings.tool_result_cache_enabled is True


def test_hybrid_multichannel_graph_channel_enters_default_hybrid_kernel(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    graph_path = tmp_path / "domain_graph.json"

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        chunk_ids = seed_multichannel_documents(db)
        graph = build_knowledge_graph(
            [
                GraphExtractionResult(
                    chunk_id=chunk_ids["text"],
                    document_id=1,
                    document_title="RFC Standard Relationship",
                    entities=(
                        GraphEntity(name="NB/T 10077", type="Standard"),
                        GraphEntity(name="compressive strength", type="Parameter"),
                    ),
                    relations=(
                        GraphRelation(
                            subject="NB/T 10077",
                            predicate="standard_defines",
                            object="compressive strength",
                            source_chunk_id=chunk_ids["text"],
                        ),
                    ),
                )
            ]
        )
        save_graph(graph, graph_path)
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            service = HybridSearchService(db, provider, parallel=False, reranking_enabled=False)
            original = (
                service.settings.hybrid_multichannel_enabled,
                service.settings.hybrid_graph_channel_enabled,
                service.settings.graphrag_graph_path,
            )
            try:
                service.settings.hybrid_multichannel_enabled = True
                service.settings.hybrid_graph_channel_enabled = True
                service.settings.graphrag_graph_path = str(graph_path)
                results = service.search("Which standard defines compressive strength?", top_k=3)
            finally:
                (
                    service.settings.hybrid_multichannel_enabled,
                    service.settings.hybrid_graph_channel_enabled,
                    service.settings.graphrag_graph_path,
                ) = original
        finally:
            reset_current_latency_trace(token)

    assert any("graph" in result.channels for result in results)
    assert trace.values["lexical_search_backend"] == "bm25"
    assert trace.values["retrieval_eligible_channels"] == ["bm25", "vector", "graph"]
    assert trace.values["graph_search_available"] is True
    assert trace.values["retrieval_channel_candidate_counts"]["graph"] >= 1


def test_hybrid_multichannel_table_and_figure_caption_channels_are_gated(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_multichannel_documents(db)
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            service = HybridSearchService(db, provider, parallel=False, reranking_enabled=False)
            original = (
                service.settings.hybrid_multichannel_enabled,
                service.settings.hybrid_table_text_channel_enabled,
                service.settings.hybrid_figure_caption_channel_enabled,
            )
            try:
                service.settings.hybrid_multichannel_enabled = True
                service.settings.hybrid_table_text_channel_enabled = True
                service.settings.hybrid_figure_caption_channel_enabled = True
                table_results = service.search("Which table parameter gives water binder ratio?", top_k=3)
                figure_results = service.search("Show figure caption for failure morphology cracks", top_k=3)
            finally:
                (
                    service.settings.hybrid_multichannel_enabled,
                    service.settings.hybrid_table_text_channel_enabled,
                    service.settings.hybrid_figure_caption_channel_enabled,
                ) = original
        finally:
            reset_current_latency_trace(token)

    assert any("table_text" in result.channels for result in table_results)
    assert any("figure_caption" in result.channels for result in figure_results)
    assert trace.values["retrieval_channel_candidate_counts"]["figure_caption"] >= 1


def test_phase63_runtime_plan_overrides_legacy_term_gates(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        service = HybridSearchService(db, provider, parallel=False, reranking_enabled=False)
        original = service.settings.retrieval_runtime_enabled
        service.settings.retrieval_runtime_enabled = True
        plan = build_retrieval_plan(
            RetrievalIntentProfile(
                relationship_intent=0.96,
                relationship_type="causal",
                graph_search_mode="local",
                relationship_explicitness="explicit",
                visual_intent=0.99,
                visual_explicitness="negative",
                source="llm",
            ),
            "why did this happen",
            service.settings,
        )
        token = set_current_retrieval_plan(plan)
        try:
            channel_plan = service._channel_plan("why did this happen and show an image")
            cache_identity = service._retrieval_cache_identity(
                "why did this happen and show an image",
                fetch_k=15,
                channel_plan=channel_plan,
            )
        finally:
            reset_current_retrieval_plan(token)
            service.settings.retrieval_runtime_enabled = original

    assert channel_plan["eligible_channels"] == ("bm25", "vector", "graph")
    assert channel_plan["channel_requirements"]["graph"] == "required"
    assert channel_plan["channel_requirements"]["figure_caption"] == "disabled"
    assert cache_identity["retrieval_plan_digest"] != "legacy"
    assert cache_identity["retrieval_pipeline_schema"] == "hybrid-phase63-gap-closure-bm25-pgvector-v1"
    assert cache_identity["graph_weight"] == service.settings.hybrid_graph_channel_weight


def test_phase63_legacy_channel_gates_remain_default(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        service = HybridSearchService(db, provider, parallel=False, reranking_enabled=False)
        original = service.settings.retrieval_runtime_enabled
        service.settings.retrieval_runtime_enabled = False
        try:
            channel_plan = service._channel_plan("why did this happen and show an image")
        finally:
            service.settings.retrieval_runtime_enabled = original

    assert "graph" not in channel_plan["eligible_channels"]
    assert "figure_caption" in channel_plan["eligible_channels"]
    assert channel_plan["runtime_mode"] == "legacy"


def test_phase63_direct_hybrid_default_switch_builds_scoped_fallback_plan(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        service = HybridSearchService(db, provider, parallel=False, reranking_enabled=False)
        original = (
            service.settings.retrieval_runtime_enabled,
            service.settings.retrieval_runtime_default_enabled,
        )
        trace = LatencyTrace()
        latency_token = set_current_latency_trace(trace)
        service.settings.retrieval_runtime_enabled = True
        service.settings.retrieval_runtime_default_enabled = True
        try:
            service.search("堆石混凝土与填充性能有什么关系", top_k=2)
        finally:
            (
                service.settings.retrieval_runtime_enabled,
                service.settings.retrieval_runtime_default_enabled,
            ) = original
            reset_current_latency_trace(latency_token)

    assert "graph" in trace.values["retrieval_eligible_channels"]
    assert current_retrieval_plan() is None


def test_phase63_runtime_graph_channel_preserves_relation_provenance(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    graph_path = tmp_path / "phase63-runtime-graph.json"
    rerank_inputs: list[str] = []

    class CapturingReRankingProvider:
        provider_name = "phase63-capturing-reranker"
        model_name = "phase63-capturing-reranker-v1"

        def rerank(self, query, candidates, top_k=5):
            rerank_inputs.extend(candidates)
            return [
                ReRankResult(
                    index=index,
                    score=1.0 - index * 0.1,
                    content=candidates[index],
                )
                for index in range(min(len(candidates), top_k))
            ]

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        chunk_ids = seed_multichannel_documents(db)
        graph = build_knowledge_graph(
            [
                GraphExtractionResult(
                    chunk_id=chunk_ids["text"],
                    document_id=1,
                    document_title="RFC Standard Relationship",
                    entities=(
                        GraphEntity(name="NB/T 10077", type="Standard"),
                        GraphEntity(name="compressive strength", type="Parameter"),
                    ),
                    relations=(
                        GraphRelation(
                            subject="NB/T 10077",
                            predicate="standard_defines",
                            object="compressive strength",
                            source_chunk_id=chunk_ids["text"],
                        ),
                    ),
                )
            ]
        )
        save_graph(graph, graph_path)
        service = HybridSearchService(
            db,
            provider,
            parallel=False,
            reranking_enabled=True,
            reranking_provider=CapturingReRankingProvider(),
            reranking_recall_k=3,
        )
        original = (
            service.settings.retrieval_runtime_enabled,
            service.settings.graphrag_graph_path,
            service.settings.rerank_order_cache_enabled,
        )
        service.settings.retrieval_runtime_enabled = True
        service.settings.graphrag_graph_path = str(graph_path)
        # This test verifies the exact text passed to the provider. A shared
        # rerank cache would legitimately bypass that provider call.
        service.settings.rerank_order_cache_enabled = False
        trace = LatencyTrace()
        latency_token = set_current_latency_trace(trace)
        plan = build_retrieval_plan(
            RetrievalIntentProfile(
                relationship_intent=0.96,
                relationship_type="standard_reference",
                graph_search_mode="local",
                relationship_explicitness="explicit",
                source="llm",
            ),
            "NB/T 10077 compressive strength details",
            service.settings,
        )
        token = set_current_retrieval_plan(plan)
        try:
            results = service.search(
                "NB/T 10077 compressive strength details",
                top_k=2,
            )
        finally:
            reset_current_retrieval_plan(token)
            reset_current_latency_trace(latency_token)
            (
                service.settings.retrieval_runtime_enabled,
                service.settings.graphrag_graph_path,
                service.settings.rerank_order_cache_enabled,
            ) = original

    graph_result = next(result for result in results if "graph" in result.channels)
    assert graph_result.matched_node_ids
    assert graph_result.graph_hop_count is not None
    assert graph_result.relation_types == ("standard_defines",)
    assert trace.values["graph_selected_count"] >= 1
    assert graph_result.chunk_id in trace.values["graph_selected_chunk_ids"]
    assert trace.values["graph_relation_type_preview"] == ["standard_defines"]
    assert trace.values["graph_fingerprint"] != "disabled"
    assert all(isinstance(item, str) for item in rerank_inputs)
    assert any("Graph relation types: standard_defines" in item for item in rerank_inputs)


def test_hybrid_parallel_results_match_serial_results(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()

        parallel_results = HybridSearchService(db, provider).search("filling capacity", top_k=2)
        serial_results = HybridSearchService(db, provider, parallel=False).search("filling capacity", top_k=2)

    assert parallel_results == serial_results


def test_hybrid_search_runs_keyword_and_vector_in_parallel(tmp_path, monkeypatch) -> None:
    TestingSessionLocal = make_session(tmp_path)
    events: list[tuple[str, str, float]] = []

    class SlowKeywordSearchService:
        def __init__(self, db) -> None:
            self.db = db

        def search(self, query: str, top_k: int = 5) -> list[KeywordSearchResult]:
            events.append(("keyword", "start", time.perf_counter()))
            time.sleep(0.2)
            events.append(("keyword", "end", time.perf_counter()))
            return [
                KeywordSearchResult(
                    document_id=1,
                    document_title="Parallel keyword",
                    source_type="local_file",
                    source_path="keyword.md",
                    file_name="keyword.md",
                    chunk_id=1,
                    chunk_index=0,
                    content="filling capacity",
                    heading_path="Keyword",
                    score=1.0,
                )
            ]

    class SlowVectorSearchService:
        def __init__(self, db, embedding_provider) -> None:
            self.db = db
            self.embedding_provider = embedding_provider

        def search(self, query: str, top_k: int = 5) -> list[VectorSearchResult]:
            events.append(("vector", "start", time.perf_counter()))
            time.sleep(0.2)
            events.append(("vector", "end", time.perf_counter()))
            return [
                VectorSearchResult(
                    document_id=1,
                    document_title="Parallel keyword",
                    source_type="local_file",
                    source_path="keyword.md",
                    file_name="keyword.md",
                    chunk_id=1,
                    chunk_index=0,
                    content="filling capacity",
                    heading_path="Keyword",
                    score=1.0,
                )
            ]

    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.BM25SearchService",
        SlowKeywordSearchService,
    )
    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.VectorSearchService",
        SlowVectorSearchService,
    )

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        started = time.perf_counter()
        service = HybridSearchService(db, provider, reranking_enabled=False)
        original = (
            service.settings.hybrid_multichannel_enabled,
            service.settings.retrieval_candidate_cache_enabled,
            service.settings.rerank_order_cache_enabled,
            service.settings.tool_result_cache_enabled,
        )
        try:
            service.settings.hybrid_multichannel_enabled = False
            service.settings.retrieval_candidate_cache_enabled = False
            service.settings.rerank_order_cache_enabled = False
            service.settings.tool_result_cache_enabled = False
            results = service.search(
                "filling capacity",
                top_k=1,
            )
        finally:
            (
                service.settings.hybrid_multichannel_enabled,
                service.settings.retrieval_candidate_cache_enabled,
                service.settings.rerank_order_cache_enabled,
                service.settings.tool_result_cache_enabled,
            ) = original
        elapsed = time.perf_counter() - started

    keyword_start = next(timestamp for channel, event, timestamp in events if channel == "keyword" and event == "start")
    keyword_end = next(timestamp for channel, event, timestamp in events if channel == "keyword" and event == "end")
    vector_start = next(timestamp for channel, event, timestamp in events if channel == "vector" and event == "start")

    assert results[0].chunk_id == 1
    assert vector_start < keyword_end
    assert keyword_start < vector_start or vector_start < keyword_end
    assert elapsed < 0.35


def test_hybrid_search_uses_reranking_provider_by_default(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    class ReverseReRankingProvider:
        provider_name = "test"
        model_name = "reverse"

        def rerank(self, query, candidates, top_k=5):
            return [
                ReRankResult(index=index, score=float(index), content=candidates[index])
                for index in reversed(range(len(candidates)))
            ][:top_k]

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()

        service = HybridSearchService(
            db,
            provider,
            reranking_provider=ReverseReRankingProvider(),
            reranking_enabled=True,
        )
        original = service.settings.reranking_dynamic_top_k_enabled
        try:
            service.settings.reranking_dynamic_top_k_enabled = False
            results = service.search("concrete", top_k=1)
        finally:
            service.settings.reranking_dynamic_top_k_enabled = original

    assert len(results) == 1
    assert results[0].document_title == "Thermal control note"


def test_hybrid_search_dynamic_top_k_uses_rerank_score_threshold(monkeypatch, tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.get_configured_layered_cache",
        lambda _layer: None,
    )

    class ScoredReRankingProvider:
        provider_name = "test"
        model_name = "scored"

        def rerank(self, query, candidates, top_k=5):
            scores = [1.0, 0.8, 0.1]
            return [
                ReRankResult(index=index, score=scores[index], content=candidates[index])
                for index in range(min(top_k, len(candidates), len(scores)))
            ]

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            service = HybridSearchService(
                db,
                provider,
                reranking_provider=ScoredReRankingProvider(),
                reranking_enabled=True,
            )
            original_dynamic = (
                service.settings.reranking_dynamic_top_k_enabled,
                service.settings.reranking_dynamic_min_results,
                service.settings.reranking_dynamic_max_results,
                service.settings.reranking_dynamic_relative_score_threshold,
            )
            try:
                service.settings.reranking_dynamic_top_k_enabled = True
                service.settings.reranking_dynamic_min_results = 1
                service.settings.reranking_dynamic_max_results = 3
                service.settings.reranking_dynamic_relative_score_threshold = 0.75
                results = service.search("concrete", top_k=1)
            finally:
                (
                    service.settings.reranking_dynamic_top_k_enabled,
                    service.settings.reranking_dynamic_min_results,
                    service.settings.reranking_dynamic_max_results,
                    service.settings.reranking_dynamic_relative_score_threshold,
                ) = original_dynamic
        finally:
            reset_current_latency_trace(token)

    assert len(results) == 2
    assert [row["score"] for row in trace.values["rerank_score_preview"]][:2] == [1.0, 0.8]
    assert trace.values["retrieval_dynamic_top_k_enabled"] is True
    assert trace.values["retrieval_selected_count"] == 2
    assert trace.values["retrieval_selection_reason"] == "rerank_scored"


def test_hybrid_search_dynamic_top_k_keeps_minimum_then_filters_tail(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    class FiveScoreReRankingProvider:
        provider_name = "test"
        model_name = "five-score"

        def rerank(self, query, candidates, top_k=5):
            scores = [1.0, 0.9, 0.8, 0.7, 0.2]
            return [
                ReRankResult(index=index, score=scores[index], content=candidates[index])
                for index in range(min(top_k, len(candidates), len(scores)))
            ]

    def fake_keyword_search(self, query, top_k=5):
        return [
            KeywordSearchResult(
                document_id=index + 1,
                document_title=f"Doc {index + 1}",
                source_type="local_file",
                source_path=f"doc-{index + 1}.md",
                file_name=f"doc-{index + 1}.md",
                chunk_id=index + 1,
                chunk_index=0,
                content=f"concrete candidate {index + 1}",
                heading_path="Candidate",
                score=float(top_k - index),
            )
            for index in range(5)
        ]

    def fake_vector_search(self, query, top_k=5):
        return []

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            service = HybridSearchService(
                db,
                provider,
                reranking_provider=FiveScoreReRankingProvider(),
                reranking_enabled=True,
                parallel=False,
            )
            import app.services.retrieval.hybrid_search as hybrid_module

            original_keyword = hybrid_module.BM25SearchService.search
            original_vector = hybrid_module.VectorSearchService.search
            original_dynamic = (
                service.settings.reranking_dynamic_top_k_enabled,
                service.settings.reranking_dynamic_min_results,
                service.settings.reranking_dynamic_max_results,
                service.settings.reranking_dynamic_relative_score_threshold,
            )
            original_runtime = service.settings.retrieval_runtime_enabled
            plan = build_retrieval_plan(
                RetrievalIntentProfile(
                    table_intent=0.95,
                    table_explicitness="explicit",
                    required_evidence_types=("text", "table"),
                ),
                "concrete table",
                service.settings,
            )
            plan_token = set_current_retrieval_plan(plan)
            hybrid_module.BM25SearchService.search = fake_keyword_search
            hybrid_module.VectorSearchService.search = fake_vector_search
            try:
                service.settings.retrieval_runtime_enabled = True
                service.settings.reranking_dynamic_top_k_enabled = True
                service.settings.reranking_dynamic_min_results = 4
                service.settings.reranking_dynamic_max_results = 5
                service.settings.reranking_dynamic_relative_score_threshold = 0.65
                results = service.search("concrete", top_k=1)
            finally:
                hybrid_module.BM25SearchService.search = original_keyword
                hybrid_module.VectorSearchService.search = original_vector
                service.settings.retrieval_runtime_enabled = original_runtime
                reset_current_retrieval_plan(plan_token)
                (
                    service.settings.reranking_dynamic_top_k_enabled,
                    service.settings.reranking_dynamic_min_results,
                    service.settings.reranking_dynamic_max_results,
                    service.settings.reranking_dynamic_relative_score_threshold,
                ) = original_dynamic
        finally:
            reset_current_latency_trace(token)

    assert [result.chunk_id for result in results] == [1, 2, 3, 4]
    assert trace.values["retrieval_selected_count"] == 4


def test_hybrid_search_uses_fusion_fail_soft_when_reranker_fails_without_fallback(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    class FailingReRankingProvider:
        provider_name = "test"
        model_name = "failing"

        def rerank(self, query, candidates, top_k=5):
            raise RuntimeError("reranker unavailable")

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            service = HybridSearchService(
                db,
                provider,
                reranking_provider=FailingReRankingProvider(),
                reranking_enabled=True,
            )
            service.reranking_fallback_provider = None
            results = service.search("concrete", top_k=1)
        finally:
            reset_current_latency_trace(token)

    assert trace.values["reranking_fallback"] is True
    assert trace.values["reranking_fallback_used"] is False
    assert trace.values["reranking_fallback_error"] == "not_configured"
    assert results
    assert trace.values["reranking_degraded"] is True
    assert trace.values["reranking_degradation_level"] == "fusion_fail_soft"
    assert trace.values["retrieval_selection_reason"] == "reranker_unavailable_fusion_dynamic"


def test_hybrid_search_quality_default_fetches_75_candidates(monkeypatch, tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    observed_top_k: list[int] = []
    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.get_configured_layered_cache",
        lambda _layer: None,
    )

    class NoOpReRankingProvider:
        provider_name = "test"
        model_name = "noop"

        def rerank(self, query, candidates, top_k=5):
            return [
                ReRankResult(index=index, score=float(len(candidates) - index), content=candidates[index])
                for index in range(min(top_k, len(candidates)))
            ]

    def fake_keyword_search(self, query, top_k=5):
        observed_top_k.append(top_k)
        return []

    def fake_vector_search(self, query, top_k=5):
        observed_top_k.append(top_k)
        return []

    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.BM25SearchService.search",
        fake_keyword_search,
    )
    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.VectorSearchService.search",
        fake_vector_search,
    )

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        HybridSearchService(
            db,
            provider,
            reranking_provider=NoOpReRankingProvider(),
            reranking_enabled=True,
            reranking_recall_k=75,
            parallel=False,
        ).search("filling capacity", top_k=8)

    assert observed_top_k == [75, 75]


def test_hybrid_search_limits_merged_candidates_before_reranking(monkeypatch, tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    observed_rerank_candidate_counts: list[int] = []
    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.get_configured_layered_cache",
        lambda _layer: None,
    )

    class RecordingReRankingProvider:
        provider_name = "test"
        model_name = "recording"

        def rerank(self, query, candidates, top_k=5):
            observed_rerank_candidate_counts.append(len(candidates))
            return [
                ReRankResult(index=index, score=float(len(candidates) - index), content=candidates[index])
                for index in range(min(top_k, len(candidates)))
            ]

    def fake_keyword_search(self, query, top_k=5):
        return [
            KeywordSearchResult(
                document_id=index + 1,
                document_title=f"Keyword Doc {index + 1}",
                source_type="local_file",
                source_path=f"keyword-{index + 1}.md",
                file_name=f"keyword-{index + 1}.md",
                chunk_id=index + 1,
                chunk_index=0,
                content=f"keyword concrete candidate {index + 1}",
                heading_path="Candidate",
                score=float(top_k - index),
            )
            for index in range(top_k)
        ]

    def fake_vector_search(self, query, top_k=5):
        return [
            VectorSearchResult(
                document_id=1000 + index,
                document_title=f"Vector Doc {index + 1}",
                source_type="local_file",
                source_path=f"vector-{index + 1}.md",
                file_name=f"vector-{index + 1}.md",
                chunk_id=1000 + index,
                chunk_index=0,
                content=f"vector concrete candidate {index + 1}",
                heading_path="Candidate",
                score=1.0 - (index / max(top_k, 1)),
                chunk_type="text",
            )
            for index in range(top_k)
        ]

    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.BM25SearchService.search",
        fake_keyword_search,
    )
    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.VectorSearchService.search",
        fake_vector_search,
    )

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            HybridSearchService(
                db,
                provider,
                reranking_provider=RecordingReRankingProvider(),
                reranking_enabled=True,
                reranking_recall_k=75,
                parallel=False,
                ).search("filling capacity", top_k=8)
        finally:
            reset_current_latency_trace(token)

    assert observed_rerank_candidate_counts == [75]
    assert trace.values["retrieval_candidate_count"] == 150
    assert trace.values["reranking_candidate_count"] == 75


def test_hybrid_search_falls_open_when_default_reranker_factory_fails(monkeypatch, tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    def fail_create_reranking_provider(*args, **kwargs):
        raise RuntimeError("remote reranker unavailable")

    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.create_reranking_provider",
        fail_create_reranking_provider,
    )

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()

        service = HybridSearchService(db, provider, reranking_enabled=True)
        results = service.search("filling capacity", top_k=1)

    assert service.reranking_provider is None
    assert len(results) == 1


def test_hybrid_search_completes_with_fusion_when_primary_reranker_fails(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    class FailingReRankingProvider:
        provider_name = "test"
        model_name = "failing"

        def rerank(self, query, candidates, top_k=5):
            raise RuntimeError("Reranking model request failed: [SSL: UNEXPECTED_EOF_WHILE_READING]")

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()

        service = HybridSearchService(
            db,
            provider,
            reranking_provider=FailingReRankingProvider(),
            reranking_enabled=True,
        )
        service.reranking_fallback_provider = None
        results = service.search("filling capacity", top_k=1)

    assert results



def test_hybrid_search_uses_secondary_reranker_when_primary_fails(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    class FailingReRankingProvider:
        provider_name = "remote-bge-lora"
        model_name = "rfc-domain-bge-lora"

        def rerank(self, query, candidates, top_k=5):
            raise RuntimeError("GPU reranker unavailable")

    class SecondaryReRankingProvider:
        provider_name = "paratera"
        model_name = "GLM-Rerank"

        def rerank(self, query, candidates, top_k=5):
            return [
                ReRankResult(index=index, score=float(index), content=candidates[index])
                for index in reversed(range(len(candidates)))
            ][:top_k]

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            service = HybridSearchService(
                db,
                provider,
                reranking_provider=FailingReRankingProvider(),
                reranking_fallback_provider=SecondaryReRankingProvider(),
                reranking_enabled=True,
            )
            original = service.settings.reranking_dynamic_top_k_enabled
            try:
                service.settings.reranking_dynamic_top_k_enabled = False
                results = service.search("concrete", top_k=1)
            finally:
                service.settings.reranking_dynamic_top_k_enabled = original
        finally:
            reset_current_latency_trace(token)

    assert len(results) == 1
    assert results[0].document_title == "Thermal control note"
    assert trace.values["reranking_fallback"] is True
    assert trace.values["reranking_fallback_used"] is True
    assert trace.values["reranking_fallback_provider"] == "paratera"
    assert trace.values["reranking_fallback_model"] == "GLM-Rerank"
    assert trace.values["reranking_fallback_error"] == ""


def test_hybrid_search_uses_fusion_fail_soft_when_secondary_reranker_fails(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    class FailingReRankingProvider:
        provider_name = "remote-bge-lora"
        model_name = "rfc-domain-bge-lora"

        def rerank(self, query, candidates, top_k=5):
            raise RuntimeError("reranker unavailable")

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            results = HybridSearchService(
                db,
                provider,
                reranking_provider=FailingReRankingProvider(),
                reranking_fallback_provider=FailingReRankingProvider(),
                reranking_enabled=True,
            ).search("filling capacity", top_k=1)
        finally:
            reset_current_latency_trace(token)

    assert trace.values["reranking_fallback"] is True
    assert trace.values["reranking_fallback_used"] is False
    assert trace.values["reranking_fallback_error"] == "runtime_error"
    assert results
    assert trace.values["reranking_degraded"] is True
    assert trace.values["reranking_degradation_level"] == "fusion_fail_soft"


def test_hybrid_search_uses_fusion_dynamic_k_when_secondary_scores_are_degenerate(
    tmp_path,
) -> None:
    TestingSessionLocal = make_session(tmp_path)

    class FailingReRankingProvider:
        provider_name = "remote-bge-lora"
        model_name = "rfc-domain-bge-lora"

        def rerank(self, query, candidates, top_k=5):
            raise RuntimeError("primary reranker unavailable")

    class DegenerateSecondaryReRankingProvider:
        provider_name = "paratera"
        model_name = "GLM-Rerank"

        def rerank(self, query, candidates, top_k=5):
            ordered_indexes = list(reversed(range(min(top_k, len(candidates)))))
            return [
                ReRankResult(index=index, score=1.0, content=candidates[index])
                for index in ordered_indexes
            ]

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            results = HybridSearchService(
                db,
                provider,
                reranking_provider=FailingReRankingProvider(),
                reranking_fallback_provider=DegenerateSecondaryReRankingProvider(),
                reranking_enabled=True,
            ).search("concrete", top_k=2)
        finally:
            reset_current_latency_trace(token)

    assert len(results) == 2
    assert trace.values["reranking_fallback"] is True
    assert trace.values["reranking_fallback_used"] is True
    assert trace.values["reranking_fallback_error"] == ""
    assert trace.values["reranking_fallback_score_quality"] == "degenerate_fusion_dynamic"
    assert trace.values["reranking_fallback_degenerate_scores"] is True
    assert trace.values["retrieval_selection_reason"] == "rerank_fallback_degenerate_fusion_dynamic"
    assert trace.values["retrieval_dynamic_top_k_enabled"] is True


def test_hybrid_search_uses_fusion_dynamic_k_when_primary_glm_scores_are_degenerate(
    monkeypatch, tmp_path,
) -> None:
    monkeypatch.setattr("app.services.retrieval.hybrid_search.get_configured_layered_cache", lambda _layer: None)
    TestingSessionLocal = make_session(tmp_path)

    class DegeneratePrimaryGlmReRankingProvider:
        provider_name = "paratera"
        model_name = "GLM-Rerank"

        def rerank(self, query, candidates, top_k=5):
            del query
            return [
                ReRankResult(index=index, score=1.0, content=candidates[index])
                for index in range(min(top_k, len(candidates)))
            ]

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            results = HybridSearchService(
                db,
                provider,
                reranking_provider=DegeneratePrimaryGlmReRankingProvider(),
                reranking_fallback_provider=None,
                reranking_enabled=True,
            ).search("concrete", top_k=2)
        finally:
            reset_current_latency_trace(token)

    assert len(results) == 2
    assert trace.values["reranking_score_quality"] == "degenerate_fusion_dynamic"
    assert trace.values["reranking_degenerate_scores"] is True
    assert trace.values["retrieval_selection_reason"] == "rerank_degenerate_fusion_dynamic"
    assert trace.values["retrieval_dynamic_top_k_enabled"] is True


def test_hybrid_search_records_reranker_trace_and_fallback(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    class FailingReRankingProvider:
        provider_name = "remote-bge-lora"
        model_name = "bge-reranker-base-rfc-lora"

        def rerank(self, query, candidates, top_k=5):
            raise RuntimeError("Reranking model request failed: HTTP 500")

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()
        trace = LatencyTrace()
        token = set_current_latency_trace(trace)
        try:
            service = HybridSearchService(
                db,
                provider,
                reranking_provider=FailingReRankingProvider(),
                reranking_enabled=True,
            )
            service.reranking_fallback_provider = None
            results = service.search("filling capacity", top_k=1)
        finally:
            reset_current_latency_trace(token)

    assert trace.values["reranking_provider"] == "remote-bge-lora"
    assert trace.values["reranking_model"] == "bge-reranker-base-rfc-lora"
    assert trace.values["reranking_fallback"] is True
    assert trace.values["reranking_fallback_count"] == 1
    assert trace.values["reranking_error"] == "runtime_error"
    assert results
    assert trace.values["reranking_degraded"] is True
    assert trace.values["reranking_error_type"] == "fallback_not_configured"


def test_hybrid_search_can_disable_reranking(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    class ReverseReRankingProvider:
        provider_name = "test"
        model_name = "reverse"

        def rerank(self, query, candidates, top_k=5):
            raise AssertionError("reranker should not be called when disabled")

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()

        results = HybridSearchService(
            db,
            provider,
            reranking_provider=ReverseReRankingProvider(),
            reranking_enabled=False,
        ).search("filling capacity", top_k=1)

    assert results[0].document_title == "Filling Capacity Evaluation of Self-Compacting Concrete"


def test_hybrid_optional_channels_parallel_matches_serial_baseline(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    graph_path = tmp_path / "domain_graph.json"

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        chunk_ids = seed_multichannel_documents(db)
        graph = build_knowledge_graph(
            [
                GraphExtractionResult(
                    chunk_id=chunk_ids["text"],
                    document_id=1,
                    document_title="RFC Standard Relationship",
                    entities=(
                        GraphEntity(name="NB/T 10077", type="Standard"),
                        GraphEntity(name="rock-filled concrete", type="Parameter"),
                    ),
                    relations=(
                        GraphRelation(
                            subject="NB/T 10077",
                            predicate="standard_defines",
                            object="rock-filled concrete",
                            source_chunk_id=chunk_ids["text"],
                        ),
                    ),
                )
            ]
        )
        save_graph(graph, graph_path)
        VectorIndexService(db, provider).build_index()
        service = HybridSearchService(db, provider, reranking_enabled=False)
        original_graph_path = service.settings.graphrag_graph_path
        try:
            service.settings.graphrag_graph_path = str(graph_path)
            query = "standard relationship table figure failure rock-filled concrete"
            plan = service._channel_plan(query)
            serial = {
                "graph": service._graph_channel_results(query),
                "table_text": service._chunk_type_channel_results(
                    query,
                    chunk_type="table",
                    top_k=12,
                ),
                "figure_caption": service._chunk_type_channel_results(
                    query,
                    chunk_type="image_description",
                    top_k=12,
                ),
            }
            parallel = service._optional_channel_results(query, 12, plan)
        finally:
            service.settings.graphrag_graph_path = original_graph_path

    assert {
        channel: [result.chunk_id for result in rows]
        for channel, rows in parallel.items()
    } == {
        channel: [result.chunk_id for result in rows]
        for channel, rows in serial.items()
    }


def test_hybrid_search_rejects_invalid_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        service = HybridSearchService(db, provider)

        try:
            service.search("   ")
        except ValueError as exc:
            assert "query" in str(exc)
        else:
            raise AssertionError("Expected ValueError for empty query")

        try:
            service.search("filling", top_k=0)
        except ValueError as exc:
            assert "top_k" in str(exc)
        else:
            raise AssertionError("Expected ValueError for invalid top_k")


def test_normalize_score_handles_zero_and_caps_to_one() -> None:
    assert normalize_score(0.0, 10.0) == 0.0
    assert normalize_score(5.0, 0.0) == 0.0
    assert normalize_score(12.0, 10.0) == 1.0
    assert normalize_score(5.0, 10.0) == 0.5
