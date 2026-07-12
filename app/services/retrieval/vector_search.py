import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.keyword_search import SearchTerm, capped_count, expand_query_terms, normalize_text
from app.services.observability.latency_trace import get_current_latency_trace, latency_timer
from app.services.retrieval.pgvector_search import PgVectorSearchOutcome, PgVectorSearchService
from app.services.retrieval.query_embedding_cache import QueryEmbeddingCache, get_query_embedding_cache
from app.services.retrieval.vector_cache import VectorIndexCache, VectorIndexMatch, get_vector_index_cache


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
    caption: str | None = None
    page_number: int | None = None


class VectorSearchService:
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        index_cache: VectorIndexCache | None = None,
        query_embedding_cache: QueryEmbeddingCache | None = None,
        pgvector_search: PgVectorSearchService | None = None,
        settings: Settings | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.settings = settings or get_settings()
        self.index_cache = index_cache or get_vector_index_cache(db, embedding_provider)
        self.query_embedding_cache = query_embedding_cache or get_query_embedding_cache()
        self.pgvector_search = pgvector_search or PgVectorSearchService(db, embedding_provider, self.settings)
        self.progress_callback = progress_callback

    def search(self, query: str, top_k: int = 5) -> list[VectorSearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        self._progress("正在生成或读取问题向量")
        with latency_timer("query_embedding_latency_ms"):
            query_embedding = self.query_embedding_cache.get_or_embed(
                self.embedding_provider,
                normalized_query,
            )
        if len(query_embedding) != self.embedding_provider.dimension:
            raise ValueError("embedding provider returned a vector with unexpected dimension")
        if is_zero_vector(query_embedding):
            return []

        self._progress("正在执行向量相似度检索")
        with latency_timer("vector_search_latency_ms"):
            matches = self._search_with_preferred_backend(query_embedding, top_k=max(top_k * 4, top_k))
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
                    caption=entry.caption,
                    page_number=entry.page_number,
                )
            )

        return rank_vector_results(normalized_query, results)[:top_k]

    def _progress(self, summary: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(summary)

    def _search_with_preferred_backend(
        self,
        query_embedding: Sequence[float],
        top_k: int,
    ) -> list[VectorIndexMatch]:
        raw_outcome = self.pgvector_search.search(query_embedding, top_k=top_k)
        outcome = normalize_pgvector_outcome(raw_outcome, self.pgvector_search)
        if outcome.matches is not None:
            set_vector_search_backend(
                "pgvector_hnsw",
                degraded=False,
                fallback_reason="",
                policy=self.settings.vector_backend_policy,
            )
            return outcome.matches

        matches = self.index_cache.search(query_embedding, top_k=top_k)
        set_vector_search_backend(
            "faiss_fail_open",
            degraded=True,
            fallback_reason=outcome.reason,
            policy=self.settings.vector_backend_policy,
        )
        return matches


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


def normalize_pgvector_outcome(
    outcome: object,
    service: object,
) -> PgVectorSearchOutcome:
    if isinstance(outcome, PgVectorSearchOutcome):
        return outcome
    if isinstance(outcome, list):
        return PgVectorSearchOutcome(matches=outcome, enabled=True)
    reason = str(getattr(service, "reason", "unavailable") or "unavailable")
    return PgVectorSearchOutcome(matches=None, enabled=False, reason=reason)


def set_vector_search_backend(
    backend: str,
    *,
    degraded: bool,
    fallback_reason: str,
    policy: str,
) -> None:
    trace = get_current_latency_trace()
    if trace is not None:
        trace.set_value("vector_search_backend", backend)
        trace.set_value("vector_search_degraded", degraded)
        trace.set_value("vector_search_fallback_reason", fallback_reason)
        trace.set_value("vector_backend_policy", policy)
