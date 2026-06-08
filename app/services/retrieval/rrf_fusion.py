from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import replace

from sqlalchemy.orm import Session

from app.services.retrieval.context_expansion import ContextExpansionService
from app.services.retrieval.bm25_search import BM25SearchResult, BM25SearchService
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.keyword_search import source_type_rank
from app.services.retrieval.vector_search import VectorSearchResult, VectorSearchService


DEFAULT_RRF_RANK_CONSTANT = 60


@dataclass(frozen=True)
class RRFHybridSearchResult:
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
    bm25_score: float
    vector_score: float
    bm25_rank: int | None
    vector_rank: int | None
    rrf_score: float
    matched_channels: tuple[str, ...]
    provenance: str
    core_content: str = ""
    context_chunk_ids: tuple[int, ...] = ()
    context_window: int = 0


@dataclass
class _FusionCandidate:
    result: BM25SearchResult | VectorSearchResult
    bm25_score: float = 0.0
    vector_score: float = 0.0
    bm25_rank: int | None = None
    vector_rank: int | None = None


class RRFHybridSearchService:
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        rank_constant: int = DEFAULT_RRF_RANK_CONSTANT,
    ) -> None:
        if rank_constant <= 0:
            raise ValueError("rank_constant must be greater than 0")
        self.db = db
        self.embedding_provider = embedding_provider
        self.rank_constant = rank_constant

    def search(
        self,
        query: str,
        top_k: int = 5,
        context_window: int = 0,
        max_context_chars: int = 1800,
    ) -> list[RRFHybridSearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if context_window < 0:
            raise ValueError("context_window must be greater than or equal to 0")
        if max_context_chars <= 0:
            raise ValueError("max_context_chars must be greater than 0")

        fetch_k = max(top_k * 4, top_k)
        bm25_results = BM25SearchService(self.db).search(normalized_query, top_k=fetch_k)
        vector_results = VectorSearchService(self.db, self.embedding_provider).search(
            normalized_query,
            top_k=fetch_k,
        )
        candidates = merge_ranked_results(bm25_results, vector_results)
        fused_results = [
            candidate_to_rrf_result(candidate, rank_constant=self.rank_constant)
            for candidate in candidates.values()
        ]
        sorted_results = sorted(
            fused_results,
            key=lambda item: (
                -item.rrf_score,
                source_type_rank(item.source_type),
                item.document_id,
                item.chunk_index,
            ),
        )[:top_k]
        if context_window <= 0:
            return sorted_results
        return expand_rrf_context(
            self.db,
            sorted_results,
            context_window=context_window,
            max_context_chars=max_context_chars,
        )


def merge_ranked_results(
    bm25_results: Sequence[BM25SearchResult],
    vector_results: Sequence[VectorSearchResult],
) -> dict[int, _FusionCandidate]:
    candidates: dict[int, _FusionCandidate] = {}
    for rank, result in enumerate(bm25_results, start=1):
        candidate = candidates.setdefault(result.chunk_id, _FusionCandidate(result=result))
        candidate.bm25_score = max(candidate.bm25_score, result.score)
        candidate.bm25_rank = min_rank(candidate.bm25_rank, rank)
    for rank, result in enumerate(vector_results, start=1):
        candidate = candidates.setdefault(result.chunk_id, _FusionCandidate(result=result))
        candidate.vector_score = max(candidate.vector_score, result.score)
        candidate.vector_rank = min_rank(candidate.vector_rank, rank)
    return candidates


def candidate_to_rrf_result(candidate: _FusionCandidate, rank_constant: int) -> RRFHybridSearchResult:
    rrf_score = reciprocal_rank_score(candidate.bm25_rank, rank_constant) + reciprocal_rank_score(
        candidate.vector_rank,
        rank_constant,
    )
    result = candidate.result
    matched_channels = tuple(
        channel
        for channel, rank in (
            ("bm25", candidate.bm25_rank),
            ("vector", candidate.vector_rank),
        )
        if rank is not None
    )
    provenance = (
        f"channels={'+'.join(matched_channels)}; "
        f"bm25_rank={candidate.bm25_rank or '-'}; "
        f"vector_rank={candidate.vector_rank or '-'}; "
        f"rrf_score={rrf_score:.6f}"
    )
    return RRFHybridSearchResult(
        document_id=result.document_id,
        document_title=result.document_title,
        source_type=result.source_type,
        source_path=result.source_path,
        file_name=result.file_name,
        chunk_id=result.chunk_id,
        chunk_index=result.chunk_index,
        content=result.content,
        heading_path=result.heading_path,
        score=rrf_score,
        bm25_score=candidate.bm25_score,
        vector_score=candidate.vector_score,
        bm25_rank=candidate.bm25_rank,
        vector_rank=candidate.vector_rank,
        rrf_score=rrf_score,
        matched_channels=matched_channels,
        provenance=provenance,
        core_content=result.content,
        context_chunk_ids=(result.chunk_id,),
        context_window=0,
    )


def reciprocal_rank_score(rank: int | None, rank_constant: int = DEFAULT_RRF_RANK_CONSTANT) -> float:
    if rank is None:
        return 0.0
    return 1.0 / (rank_constant + rank)


def min_rank(current: int | None, candidate: int) -> int:
    if current is None:
        return candidate
    return min(current, candidate)


def expand_rrf_context(
    db: Session,
    results: Sequence[RRFHybridSearchResult],
    context_window: int,
    max_context_chars: int,
) -> list[RRFHybridSearchResult]:
    expanded = ContextExpansionService(db).expand_results(
        results,
        window=context_window,
        max_context_chars=max_context_chars,
    )
    return [
        replace(
            result,
            content=expanded_result.content,
            core_content=expanded_result.core_content,
            context_chunk_ids=expanded_result.context_chunk_ids,
            context_window=expanded_result.context_window,
            provenance=(
                f"{result.provenance}; context_window={expanded_result.context_window}; "
                f"context_chunk_ids={','.join(str(chunk_id) for chunk_id in expanded_result.context_chunk_ids)}"
            ),
        )
        for result, expanded_result in zip(results, expanded, strict=True)
    ]
