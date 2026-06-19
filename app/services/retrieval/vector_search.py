import math
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.keyword_search import SearchTerm, capped_count, expand_query_terms, normalize_text
from app.services.observability.latency_trace import latency_timer
from app.services.retrieval.query_embedding_cache import QueryEmbeddingCache, get_query_embedding_cache
from app.services.retrieval.vector_cache import VectorIndexCache, get_vector_index_cache


TOPIC_ANCHOR_BOOST = 0.2


@dataclass(frozen=True)
class VectorSearchResult:
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
    chunk_type: str = "text"
    source_image_path: str | None = None


class VectorSearchService:
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        index_cache: VectorIndexCache | None = None,
        query_embedding_cache: QueryEmbeddingCache | None = None,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.index_cache = index_cache or get_vector_index_cache(db, embedding_provider)
        self.query_embedding_cache = query_embedding_cache or get_query_embedding_cache()

    def search(self, query: str, top_k: int = 5) -> list[VectorSearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        with latency_timer("query_embedding_latency_ms"):
            query_embedding = self.query_embedding_cache.get_or_embed(
                self.embedding_provider,
                normalized_query,
            )
        if len(query_embedding) != self.embedding_provider.dimension:
            raise ValueError("embedding provider returned a vector with unexpected dimension")
        if is_zero_vector(query_embedding):
            return []

        with latency_timer("vector_search_latency_ms"):
            matches = self.index_cache.search(query_embedding, top_k=max(top_k * 4, top_k))
        results: list[VectorSearchResult] = []
        for match in matches:
            entry = match.entry
            results.append(
                VectorSearchResult(
                    document_id=entry.document_id,
                    document_title=entry.document_title,
                    source_type=entry.source_type,
                    source_path=entry.source_path,
                    file_name=entry.file_name,
                    chunk_id=entry.chunk_id,
                    chunk_index=entry.chunk_index,
                    content=entry.content,
                    heading_path=entry.heading_path,
                    score=match.score,
                    chunk_type=entry.chunk_type,
                    source_image_path=entry.source_image_path,
                )
            )

        return rank_vector_results(normalized_query, results)[:top_k]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimension")

    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0

    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    similarity = dot_product / (left_norm * right_norm)
    return max(-1.0, min(1.0, similarity))


def is_zero_vector(vector: Sequence[float]) -> bool:
    return all(value == 0 for value in vector)


def rank_vector_results(query: str, results: list[VectorSearchResult]) -> list[VectorSearchResult]:
    terms = expand_query_terms(query)
    normalized_query = normalize_text(query)
    anchor_scores = {
        result.chunk_id: topic_anchor_score(
            query,
            result,
            terms=terms,
            normalized_query=normalized_query,
        )
        for result in results
    }
    max_anchor_score = max(anchor_scores.values(), default=0.0)

    return sorted(
        results,
        key=lambda item: (
            -combined_rank_score(item.score, anchor_scores[item.chunk_id], max_anchor_score),
            -normalized_anchor_score(anchor_scores[item.chunk_id], max_anchor_score),
            item.document_id,
            item.chunk_index,
        ),
    )


def topic_anchor_score(
    query: str,
    result: VectorSearchResult,
    *,
    terms: list[SearchTerm] | None = None,
    normalized_query: str | None = None,
) -> float:
    terms = terms if terms is not None else expand_query_terms(query)
    if not terms:
        return 0.0
    normalized_query = normalize_text(query) if normalized_query is None else normalized_query
    normalized_title = normalize_text(result.document_title)
    normalized_heading = normalize_text(result.heading_path)
    normalized_content = normalize_text(result.content)

    score = 0.0
    for term in terms:
        normalized_term = normalize_text(term.text)
        if not normalized_term:
            continue
        specificity_weight = 1.0 if term.specific else 0.25
        score += capped_count(normalized_title, normalized_term) * term.weight * specificity_weight * 3.0
        score += capped_count(normalized_heading, normalized_term) * term.weight * specificity_weight * 1.5
        score += capped_count(normalized_content, normalized_term) * term.weight * specificity_weight

    if normalized_query:
        score += capped_count(normalized_title, normalized_query) * 4.0
        score += capped_count(normalized_heading, normalized_query) * 2.5
        score += capped_count(normalized_content, normalized_query) * 2.0
    return score


def combined_rank_score(vector_score: float, anchor_score: float, max_anchor_score: float) -> float:
    return vector_score + normalized_anchor_score(anchor_score, max_anchor_score) * TOPIC_ANCHOR_BOOST


def normalized_anchor_score(anchor_score: float, max_anchor_score: float) -> float:
    if anchor_score <= 0 or max_anchor_score <= 0:
        return 0.0
    return min(1.0, anchor_score / max_anchor_score)
