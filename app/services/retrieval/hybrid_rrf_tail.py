from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService
from app.services.retrieval.rrf_fusion import RRFHybridSearchResult, RRFHybridSearchService


SearchResult = HybridSearchResult | RRFHybridSearchResult


class HybridRrfTailSearchService:
    """Preserve hybrid head ranking and use BM25+RRF to fill tail recall slots."""

    def __init__(
        self,
        db,
        embedding_provider: EmbeddingProvider,
        stable_head_k: int = 3,
        hybrid_service: HybridSearchService | None = None,
        rrf_service: RRFHybridSearchService | None = None,
    ) -> None:
        if stable_head_k <= 0:
            raise ValueError("stable_head_k must be greater than 0")
        self.stable_head_k = stable_head_k
        self.hybrid_service = hybrid_service or HybridSearchService(
            db=db,
            embedding_provider=embedding_provider,
            reranking_enabled=True,
        )
        self.rrf_service = rrf_service or RRFHybridSearchService(
            db=db,
            embedding_provider=embedding_provider,
        )

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        hybrid_results = self.hybrid_service.search(query, top_k=top_k)
        selected: list[SearchResult] = list(hybrid_results[: min(self.stable_head_k, top_k)])
        seen_chunk_ids = {result.chunk_id for result in selected}

        for result in self.rrf_service.search(query, top_k=top_k):
            if len(selected) >= top_k:
                break
            if result.chunk_id in seen_chunk_ids:
                continue
            selected.append(result)
            seen_chunk_ids.add(result.chunk_id)

        for result in hybrid_results:
            if len(selected) >= top_k:
                break
            if result.chunk_id in seen_chunk_ids:
                continue
            selected.append(result)
            seen_chunk_ids.add(result.chunk_id)
        return selected
