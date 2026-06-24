import time

from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate
from app.db.repositories import DocumentCreate
from app.db.repositories import DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService
from app.services.retrieval.hybrid_search import normalize_score
from app.services.retrieval.keyword_search import KeywordSearchResult
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


def test_hybrid_search_uses_keyword_evidence_to_rank_expected_match(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()

        results = HybridSearchService(db, provider).search("filling capacity rock-filled concrete", top_k=2)

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
        "app.services.retrieval.hybrid_search.KeywordSearchService",
        SlowKeywordSearchService,
    )
    monkeypatch.setattr(
        "app.services.retrieval.hybrid_search.VectorSearchService",
        SlowVectorSearchService,
    )

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        started = time.perf_counter()
        results = HybridSearchService(db, provider, reranking_enabled=False).search(
            "filling capacity",
            top_k=1,
        )
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

        results = HybridSearchService(
            db,
            provider,
            reranking_provider=ReverseReRankingProvider(),
            reranking_enabled=True,
        ).search("concrete", top_k=1)

    assert len(results) == 1
    assert results[0].document_title == "Thermal control note"


def test_hybrid_search_quality_default_fetches_75_candidates(monkeypatch, tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    observed_top_k: list[int] = []

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
        "app.services.retrieval.hybrid_search.KeywordSearchService.search",
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


def test_hybrid_search_falls_back_when_reranker_fails(tmp_path) -> None:
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

        results = HybridSearchService(
            db,
            provider,
            reranking_provider=FailingReRankingProvider(),
            reranking_enabled=True,
        ).search("filling capacity", top_k=1)

    # A transient reranker failure must degrade to the fusion order, not crash.
    assert len(results) == 1


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
            results = HybridSearchService(
                db,
                provider,
                reranking_provider=FailingReRankingProvider(),
                reranking_enabled=True,
            ).search("filling capacity", top_k=1)
        finally:
            reset_current_latency_trace(token)

    assert len(results) == 1
    assert trace.values["reranking_provider"] == "remote-bge-lora"
    assert trace.values["reranking_model"] == "bge-reranker-base-rfc-lora"
    assert trace.values["reranking_fallback"] is True
    assert trace.values["reranking_fallback_count"] == 1
    assert trace.values["reranking_error"] == "runtime_error"


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
