from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.keyword_search import KeywordSearchResult
from app.services.retrieval.keyword_search import KeywordSearchService
from app.services.retrieval.keyword_search import source_type_rank
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
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.keyword_weight = keyword_weight
        self.vector_weight = vector_weight
        self.both_match_bonus = both_match_bonus

    def search(self, query: str, top_k: int = 5) -> list[HybridSearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        fetch_k = max(top_k * 3, top_k)
        keyword_results = KeywordSearchService(self.db).search(normalized_query, top_k=fetch_k)
        vector_results = VectorSearchService(self.db, self.embedding_provider).search(
            normalized_query,
            top_k=fetch_k,
        )

        candidates: dict[int, _HybridCandidate] = {}
        add_results(candidates, keyword_results, "keyword", max_result_score(keyword_results))
        add_results(candidates, vector_results, "vector", max_result_score(vector_results))

        hybrid_results = [candidate_to_result(candidate, self) for candidate in candidates.values()]
        return sorted(
            hybrid_results,
            key=lambda item: (
                -item.score,
                source_type_rank(item.source_type),
                item.document_id,
                item.chunk_index,
            ),
        )[:top_k]


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
