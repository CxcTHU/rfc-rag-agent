from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.services.retrieval.embedding import EmbeddingProvider
from app.core.config import get_settings
from app.services.retrieval.keyword_search import KeywordSearchResult
from app.services.retrieval.keyword_search import KeywordSearchService
from app.services.retrieval.keyword_search import source_type_rank
from app.services.retrieval.reranking import ReRankingProvider, create_reranking_provider
from app.services.retrieval.vector_search import VectorSearchResult
from app.services.retrieval.vector_search import VectorSearchService


@dataclass(frozen=True)
class HybridSearchResult:
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    content: str
    heading_path: str | None
    score: float
    keyword_score: float
    vector_score: float


@dataclass
class _HybridCandidate:
    result: KeywordSearchResult | VectorSearchResult
    keyword_score: float = 0.0
    vector_score: float = 0.0


class HybridSearchService:
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        keyword_weight: float = 0.7,
        vector_weight: float = 0.3,
        both_match_bonus: float = 0.15,
        parallel: bool = True,
        reranking_provider: ReRankingProvider | None = None,
        reranking_enabled: bool | None = None,
        reranking_recall_k: int | None = None,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.keyword_weight = keyword_weight
        self.vector_weight = vector_weight
        self.both_match_bonus = both_match_bonus
        self.parallel = parallel
        settings = get_settings()
        self.reranking_enabled = settings.reranking_enabled if reranking_enabled is None else reranking_enabled
        self.reranking_recall_k = reranking_recall_k or settings.reranking_recall_k
        self.reranking_provider = reranking_provider
        if self.reranking_enabled and self.reranking_provider is None:
            self.reranking_provider = create_reranking_provider(
                provider_name=settings.reranking_provider,
                model_name=settings.reranking_model_name,
                api_key=settings.reranking_api_key,
                base_url=settings.reranking_base_url,
                timeout_seconds=settings.reranking_timeout_seconds,
            )

    def search(self, query: str, top_k: int = 5) -> list[HybridSearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        fetch_k = max(top_k * 3, top_k)
        if self.reranking_enabled and self.reranking_provider is not None:
            fetch_k = max(fetch_k, top_k * 5, self.reranking_recall_k)
        if self.parallel:
            keyword_results, vector_results = self._search_parallel(normalized_query, fetch_k)
        else:
            keyword_results, vector_results = self._search_serial(normalized_query, fetch_k)

        candidates: dict[int, _HybridCandidate] = {}
        add_results(candidates, keyword_results, "keyword", max_result_score(keyword_results))
        add_results(candidates, vector_results, "vector", max_result_score(vector_results))

        hybrid_results = [candidate_to_result(candidate, self) for candidate in candidates.values()]
        sorted_results = sorted(
            hybrid_results,
            key=lambda item: (
                -item.score,
                source_type_rank(item.source_type),
                item.document_id,
                item.chunk_index,
            ),
        )
        return self._rerank_results(normalized_query, sorted_results, top_k=top_k)

    def _search_serial(
        self,
        query: str,
        fetch_k: int,
    ) -> tuple[list[KeywordSearchResult], list[VectorSearchResult]]:
        keyword_results = KeywordSearchService(self.db).search(query, top_k=fetch_k)
        vector_results = VectorSearchService(self.db, self.embedding_provider).search(
            query,
            top_k=fetch_k,
        )
        return keyword_results, vector_results

    def _search_parallel(
        self,
        query: str,
        fetch_k: int,
    ) -> tuple[list[KeywordSearchResult], list[VectorSearchResult]]:
        bind = self.db.get_bind()
        ThreadSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=bind)

        def run_keyword() -> list[KeywordSearchResult]:
            with ThreadSessionLocal() as db:
                return KeywordSearchService(db).search(query, top_k=fetch_k)

        def run_vector() -> list[VectorSearchResult]:
            with ThreadSessionLocal() as db:
                return VectorSearchService(db, self.embedding_provider).search(
                    query,
                    top_k=fetch_k,
                )

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="hybrid-search") as executor:
            keyword_future = executor.submit(run_keyword)
            vector_future = executor.submit(run_vector)
            return keyword_future.result(), vector_future.result()

    def _rerank_results(
        self,
        query: str,
        results: list[HybridSearchResult],
        *,
        top_k: int,
    ) -> list[HybridSearchResult]:
        if not self.reranking_enabled or self.reranking_provider is None or not results:
            return results[:top_k]
        try:
            reranked = self.reranking_provider.rerank(
                query=query,
                candidates=[result.content for result in results],
                top_k=top_k,
            )
        except RuntimeError:
            # Reranking is a quality enhancement, not a hard requirement. If the
            # rerank service has a transient failure, fall back to the fusion
            # order instead of failing the whole query.
            return results[:top_k]
        return [results[item.index] for item in reranked]


def add_results(
    candidates: dict[int, _HybridCandidate],
    results: list[KeywordSearchResult] | list[VectorSearchResult],
    channel: str,
    max_score: float,
) -> None:
    for result in results:
        candidate = candidates.setdefault(result.chunk_id, _HybridCandidate(result=result))
        normalized_score = normalize_score(result.score, max_score)
        if channel == "keyword":
            candidate.keyword_score = max(candidate.keyword_score, normalized_score)
        elif channel == "vector":
            candidate.vector_score = max(candidate.vector_score, normalized_score)
        else:
            raise ValueError(f"Unsupported hybrid channel: {channel}")


def candidate_to_result(candidate: _HybridCandidate, service: HybridSearchService) -> HybridSearchResult:
    bonus = service.both_match_bonus if candidate.keyword_score > 0 and candidate.vector_score > 0 else 0.0
    combined_score = (
        candidate.keyword_score * service.keyword_weight
        + candidate.vector_score * service.vector_weight
        + bonus
    )
    result = candidate.result
    return HybridSearchResult(
        document_id=result.document_id,
        document_title=result.document_title,
        source_type=result.source_type,
        source_path=result.source_path,
        file_name=result.file_name,
        chunk_id=result.chunk_id,
        chunk_index=result.chunk_index,
        content=result.content,
        heading_path=result.heading_path,
        score=combined_score,
        keyword_score=candidate.keyword_score,
        vector_score=candidate.vector_score,
    )


def max_result_score(results: list[KeywordSearchResult] | list[VectorSearchResult]) -> float:
    return max((result.score for result in results), default=0.0)


def normalize_score(score: float, max_score: float) -> float:
    if score <= 0 or max_score <= 0:
        return 0.0
    return min(1.0, score / max_score)
