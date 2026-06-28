from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable

from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.services.retrieval.embedding import EmbeddingProvider
from app.core.config import get_settings
from app.services.cache.layered_cache import (
    base_cache_identity,
    candidate_chunk_hash,
    get_configured_layered_cache,
    hydrate_chunk_rows,
    normalized_query_identity,
)
from app.services.observability.latency_trace import (
    get_current_latency_trace,
    latency_timer,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.keyword_search import KeywordSearchResult
from app.services.retrieval.keyword_search import KeywordSearchService
from app.services.retrieval.keyword_search import source_type_rank
from app.services.retrieval.reranking import ReRankResult, ReRankingProvider, create_reranking_provider
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
    chunk_type: str = "text"
    source_image_path: str | None = None
    caption: str | None = None
    page_number: int | None = None


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
        reranking_fallback_provider: ReRankingProvider | None = None,
        progress_callback: Callable[[str], None] | None = None,
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
        self.reranking_fallback_provider = reranking_fallback_provider
        self.progress_callback = progress_callback
        self.settings = settings
        if self.reranking_enabled and self.reranking_provider is None:
            try:
                self.reranking_provider = create_reranking_provider(
                    provider_name=settings.reranking_provider,
                    model_name=settings.reranking_model_name,
                    api_key=settings.reranking_api_key,
                    base_url=settings.reranking_base_url,
                    timeout_seconds=settings.reranking_timeout_seconds,
                )
            except Exception:
                self.reranking_provider = None
        if (
            self.reranking_enabled
            and settings.reranking_fallback_enabled
            and self.reranking_fallback_provider is None
        ):
            fallback_api_key = settings.reranking_fallback_api_key
            if (
                not fallback_api_key
                and settings.reranking_fallback_provider.strip().casefold() == "paratera"
            ):
                fallback_api_key = settings.embedding_api_key
            try:
                self.reranking_fallback_provider = create_reranking_provider(
                    provider_name=settings.reranking_fallback_provider,
                    model_name=settings.reranking_fallback_model_name,
                    api_key=fallback_api_key,
                    base_url=settings.reranking_fallback_base_url,
                    timeout_seconds=settings.reranking_fallback_timeout_seconds,
                )
            except Exception:
                self.reranking_fallback_provider = None

    def search(self, query: str, top_k: int = 5) -> list[HybridSearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        fetch_k = max(top_k * 3, top_k)
        if self.reranking_enabled and self.reranking_provider is not None:
            fetch_k = max(fetch_k, top_k * 5, self.reranking_recall_k)
        sorted_results = self._lookup_retrieval_cache(normalized_query, fetch_k=fetch_k)
        if sorted_results is None:
            if self.parallel:
                self._progress("正在并行检索关键词和向量候选证据")
                keyword_results, vector_results = self._search_parallel(normalized_query, fetch_k)
            else:
                self._progress("正在检索关键词和向量候选证据")
                keyword_results, vector_results = self._search_serial(normalized_query, fetch_k)

            self._progress("已获得候选证据，正在合并排序")
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
            self._store_retrieval_cache(normalized_query, sorted_results, fetch_k=fetch_k)
        trace_retrieval_candidates(normalized_query, sorted_results, fetch_k=fetch_k)
        return self._rerank_results(normalized_query, sorted_results, top_k=top_k)

    def _retrieval_cache_identity(self, query: str, *, fetch_k: int) -> dict[str, object]:
        identity = base_cache_identity(self.db)
        identity.update(
            {
                "layer": "retrieval",
                "query": normalized_query_identity(query),
                "fetch_k": fetch_k,
                "keyword_weight": self.keyword_weight,
                "vector_weight": self.vector_weight,
                "both_match_bonus": self.both_match_bonus,
                "embedding_provider": self.embedding_provider.provider_name,
                "embedding_model": self.embedding_provider.model_name,
                "embedding_dimension": self.embedding_provider.dimension,
                "pgvector_enabled": get_settings().pgvector_search_enabled,
            }
        )
        return identity

    def _lookup_retrieval_cache(
        self,
        query: str,
        *,
        fetch_k: int,
    ) -> list[HybridSearchResult] | None:
        cache = get_configured_layered_cache("retrieval")
        if cache is None:
            return None
        lookup = cache.lookup(self._retrieval_cache_identity(query, fetch_k=fetch_k))
        if not lookup.hit or lookup.payload is None:
            return None
        payload = lookup.payload.get("payload", {})
        rows = payload.get("rows")
        if not isinstance(rows, list):
            return None
        row_by_chunk_id: dict[int, dict[str, object]] = {}
        chunk_ids: list[int] = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("chunk_id"), int):
                return None
            chunk_id = int(row["chunk_id"])
            row_by_chunk_id[chunk_id] = row
            chunk_ids.append(chunk_id)
        hydrated = hydrate_chunk_rows(self.db, chunk_ids)
        if len(hydrated) != len(chunk_ids):
            return None
        results: list[HybridSearchResult] = []
        for chunk, document in hydrated:
            cached = row_by_chunk_id[chunk.id]
            results.append(
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
                    score=float(cached.get("score", 0.0)),
                    keyword_score=float(cached.get("keyword_score", 0.0)),
                    vector_score=float(cached.get("vector_score", 0.0)),
                    chunk_type=chunk.chunk_type,
                    source_image_path=chunk.source_image_path,
                    caption=chunk.caption,
                    page_number=chunk.page_number,
                )
            )
        return results

    def _store_retrieval_cache(
        self,
        query: str,
        results: list[HybridSearchResult],
        *,
        fetch_k: int,
    ) -> None:
        cache = get_configured_layered_cache("retrieval")
        if cache is None:
            return
        payload = {
            "rows": [
                {
                    "chunk_id": result.chunk_id,
                    "score": round(float(result.score), 8),
                    "keyword_score": round(float(result.keyword_score), 8),
                    "vector_score": round(float(result.vector_score), 8),
                    "chunk_type": result.chunk_type,
                    "source_type": result.source_type,
                }
                for result in results
            ]
        }
        cache.store(self._retrieval_cache_identity(query, fetch_k=fetch_k), payload)

    def _search_serial(
        self,
        query: str,
        fetch_k: int,
    ) -> tuple[list[KeywordSearchResult], list[VectorSearchResult]]:
        keyword_results = KeywordSearchService(self.db).search(query, top_k=fetch_k)
        vector_results = self._vector_search_service(self.db).search(
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

        trace = get_current_latency_trace()

        def run_vector() -> list[VectorSearchResult]:
            token = set_current_latency_trace(trace)
            with ThreadSessionLocal() as db:
                try:
                    return self._vector_search_service(db).search(
                        query,
                        top_k=fetch_k,
                    )
                finally:
                    reset_current_latency_trace(token)

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
            selected = results[:top_k]
            trace_selected_results(
                query=query,
                candidates=results,
                selected=selected,
                requested_top_k=top_k,
                dynamic=False,
                reason="reranking_disabled",
            )
            return selected
        trace = get_current_latency_trace()
        if trace is not None:
            trace.set_value("reranking_provider", self.reranking_provider.provider_name)
            trace.set_value("reranking_model", self.reranking_provider.model_name)
            trace.set_value("reranking_fallback", False)
            trace.set_value("reranking_error", "")
        cached_results = self._lookup_rerank_cache(
            query,
            results,
            top_k=top_k,
            provider_name=self.reranking_provider.provider_name,
            model_name=self.reranking_provider.model_name,
            fallback=False,
        )
        if cached_results is not None:
            trace_selected_results(
                query=query,
                candidates=results,
                selected=cached_results,
                requested_top_k=top_k,
                dynamic=self.settings.reranking_dynamic_top_k_enabled,
                reason="rerank_cache_hit",
            )
            return cached_results
        try:
            self._progress("正在重排候选证据")
            with latency_timer("rerank_latency_ms"):
                reranked = self.reranking_provider.rerank(
                    query=query,
                    candidates=[result.content for result in results],
                    top_k=rerank_request_top_k(results, top_k, self.settings),
                )
        except Exception:
            # Reranking is a quality enhancement, not a hard requirement. If the
            # primary reranker has a transient failure, try the configured
            # secondary reranker before falling back to the fusion order.
            if trace is not None:
                trace.set_value("reranking_fallback", True)
                fallback_count = int(trace.values.get("reranking_fallback_count", 0)) + 1
                trace.set_value("reranking_fallback_count", fallback_count)
                trace.set_value("reranking_error", "runtime_error")
            fallback_reranked = self._rerank_with_fallback_provider(
                query,
                results,
                top_k=top_k,
            )
            if fallback_reranked is not None:
                return fallback_reranked
            selected = results[:top_k]
            trace_selected_results(
                query=query,
                candidates=results,
                selected=selected,
                requested_top_k=top_k,
                dynamic=False,
                reason="rerank_failed_fusion_order",
            )
            return selected
        reranked_results = select_reranked_results(
            results,
            reranked,
            requested_top_k=top_k,
            settings=self.settings,
        )
        trace_selected_results(
            query=query,
            candidates=results,
            selected=reranked_results,
            requested_top_k=top_k,
            dynamic=self.settings.reranking_dynamic_top_k_enabled,
            reason="rerank_scored",
            reranked=reranked,
        )
        self._store_rerank_cache(
            query,
            results,
            reranked_results,
            top_k=top_k,
            provider_name=self.reranking_provider.provider_name,
            model_name=self.reranking_provider.model_name,
            fallback=False,
        )
        return reranked_results

    def _rerank_with_fallback_provider(
        self,
        query: str,
        results: list[HybridSearchResult],
        *,
        top_k: int,
    ) -> list[HybridSearchResult] | None:
        if self.reranking_fallback_provider is None:
            return None
        trace = get_current_latency_trace()
        if trace is not None:
            trace.set_value(
                "reranking_fallback_provider",
                self.reranking_fallback_provider.provider_name,
            )
            trace.set_value(
                "reranking_fallback_model",
                self.reranking_fallback_provider.model_name,
            )
            trace.set_value("reranking_fallback_used", False)
            trace.set_value("reranking_fallback_error", "")
        cached_results = self._lookup_rerank_cache(
            query,
            results,
            top_k=top_k,
            provider_name=self.reranking_fallback_provider.provider_name,
            model_name=self.reranking_fallback_provider.model_name,
            fallback=True,
        )
        if cached_results is not None:
            if trace is not None:
                trace.set_value("reranking_fallback_used", True)
            trace_selected_results(
                query=query,
                candidates=results,
                selected=cached_results,
                requested_top_k=top_k,
                dynamic=self.settings.reranking_dynamic_top_k_enabled,
                reason="rerank_fallback_cache_hit",
            )
            return cached_results
        try:
            with latency_timer("rerank_fallback_latency_ms"):
                reranked = self.reranking_fallback_provider.rerank(
                    query=query,
                    candidates=[result.content for result in results],
                    top_k=rerank_request_top_k(results, top_k, self.settings),
                )
        except Exception:
            if trace is not None:
                trace.set_value("reranking_fallback_error", "runtime_error")
            return None
        if trace is not None:
            trace.set_value("reranking_fallback_used", True)
        reranked_results = select_reranked_results(
            results,
            reranked,
            requested_top_k=top_k,
            settings=self.settings,
        )
        trace_selected_results(
            query=query,
            candidates=results,
            selected=reranked_results,
            requested_top_k=top_k,
            dynamic=self.settings.reranking_dynamic_top_k_enabled,
            reason="rerank_fallback_scored",
            reranked=reranked,
        )
        self._store_rerank_cache(
            query,
            results,
            reranked_results,
            top_k=top_k,
            provider_name=self.reranking_fallback_provider.provider_name,
            model_name=self.reranking_fallback_provider.model_name,
            fallback=True,
        )
        return reranked_results

    def _rerank_cache_identity(
        self,
        query: str,
        results: list[HybridSearchResult],
        *,
        top_k: int,
        provider_name: str,
        model_name: str,
        fallback: bool,
    ) -> dict[str, object]:
        candidate_ids = [result.chunk_id for result in results]
        identity = base_cache_identity(self.db)
        identity.update(
            {
                "layer": "rerank",
                "query": normalized_query_identity(query),
                "top_k": top_k,
                "recall_k": self.reranking_recall_k,
                "dynamic_top_k": self.settings.reranking_dynamic_top_k_enabled,
                "dynamic_min_results": self.settings.reranking_dynamic_min_results,
                "dynamic_max_results": self.settings.reranking_dynamic_max_results,
                "dynamic_relative_score_threshold": (
                    self.settings.reranking_dynamic_relative_score_threshold
                ),
                "provider": provider_name,
                "model": model_name,
                "fallback": fallback,
                "candidate_hash": candidate_chunk_hash(candidate_ids),
                "candidate_count": len(candidate_ids),
            }
        )
        return identity

    def _lookup_rerank_cache(
        self,
        query: str,
        results: list[HybridSearchResult],
        *,
        top_k: int,
        provider_name: str,
        model_name: str,
        fallback: bool,
    ) -> list[HybridSearchResult] | None:
        cache = get_configured_layered_cache("rerank")
        if cache is None:
            return None
        lookup = cache.lookup(
            self._rerank_cache_identity(
                query,
                results,
                top_k=top_k,
                provider_name=provider_name,
                model_name=model_name,
                fallback=fallback,
            )
        )
        if not lookup.hit or lookup.payload is None:
            return None
        payload = lookup.payload.get("payload", {})
        chunk_ids = payload.get("chunk_ids")
        if not isinstance(chunk_ids, list) or not all(isinstance(chunk_id, int) for chunk_id in chunk_ids):
            return None
        by_chunk_id = {result.chunk_id: result for result in results}
        if any(chunk_id not in by_chunk_id for chunk_id in chunk_ids):
            return None
        selected = [by_chunk_id[chunk_id] for chunk_id in chunk_ids]
        if not self.settings.reranking_dynamic_top_k_enabled:
            return selected[:top_k]
        return selected

    def _store_rerank_cache(
        self,
        query: str,
        results: list[HybridSearchResult],
        reranked_results: list[HybridSearchResult],
        *,
        top_k: int,
        provider_name: str,
        model_name: str,
        fallback: bool,
    ) -> None:
        cache = get_configured_layered_cache("rerank")
        if cache is None:
            return
        cache.store(
            self._rerank_cache_identity(
                query,
                results,
                top_k=top_k,
                provider_name=provider_name,
                model_name=model_name,
                fallback=fallback,
            ),
            {"chunk_ids": [result.chunk_id for result in reranked_results]},
        )

    def _progress(self, summary: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(summary)

    def _vector_search_service(self, db: Session) -> VectorSearchService:
        try:
            return VectorSearchService(
                db,
                self.embedding_provider,
                progress_callback=self.progress_callback,
            )
        except TypeError:
            return VectorSearchService(db, self.embedding_provider)


def rerank_request_top_k(
    results: list[HybridSearchResult],
    requested_top_k: int,
    settings: object,
) -> int:
    if not getattr(settings, "reranking_dynamic_top_k_enabled", False):
        return min(requested_top_k, len(results))
    configured_max = int(getattr(settings, "reranking_dynamic_max_results", requested_top_k))
    request_count = max(requested_top_k, configured_max)
    return min(max(1, request_count), len(results))


def select_reranked_results(
    results: list[HybridSearchResult],
    reranked: list[ReRankResult],
    *,
    requested_top_k: int,
    settings: object,
) -> list[HybridSearchResult]:
    if not reranked:
        return []
    ordered = [results[item.index] for item in reranked]
    if not getattr(settings, "reranking_dynamic_top_k_enabled", False):
        return ordered[:requested_top_k]

    max_results = max(1, int(getattr(settings, "reranking_dynamic_max_results", requested_top_k)))
    max_results = min(max_results, len(ordered))
    min_results = max(1, int(getattr(settings, "reranking_dynamic_min_results", 1)))
    min_results = min(min_results, max_results)
    threshold_ratio = float(getattr(settings, "reranking_dynamic_relative_score_threshold", 0.0))
    threshold_ratio = min(max(threshold_ratio, 0.0), 1.0)
    best_score = max((float(item.score) for item in reranked), default=0.0)
    threshold = best_score * threshold_ratio

    selected: list[HybridSearchResult] = []
    for position, item in enumerate(reranked[:max_results]):
        if not 0 <= item.index < len(results):
            continue
        if position < min_results or float(item.score) >= threshold:
            selected.append(results[item.index])
    return selected


def trace_retrieval_candidates(
    query: str,
    results: list[HybridSearchResult],
    *,
    fetch_k: int,
) -> None:
    trace = get_current_latency_trace()
    if trace is None:
        return
    trace.set_value("retrieval_query", query)
    trace.set_value("retrieval_fetch_k", fetch_k)
    trace.set_value("retrieval_candidate_count", len(results))
    trace.set_value("retrieval_candidate_chunk_ids", [result.chunk_id for result in results[:20]])
    trace.set_value(
        "retrieval_candidate_preview",
        [
            {
                "chunk_id": result.chunk_id,
                "source_type": result.source_type,
                "score": round(float(result.score), 6),
                "keyword_score": round(float(result.keyword_score), 6),
                "vector_score": round(float(result.vector_score), 6),
                "title": result.document_title[:80],
            }
            for result in results[:8]
        ],
    )


def trace_selected_results(
    *,
    query: str,
    candidates: list[HybridSearchResult],
    selected: list[HybridSearchResult],
    requested_top_k: int,
    dynamic: bool,
    reason: str,
    reranked: list[ReRankResult] | None = None,
) -> None:
    trace = get_current_latency_trace()
    if trace is None:
        return
    trace.set_value("retrieval_query", query)
    trace.set_value("retrieval_requested_top_k", requested_top_k)
    trace.set_value("retrieval_dynamic_top_k_enabled", dynamic)
    trace.set_value("retrieval_selected_count", len(selected))
    trace.set_value("retrieval_selection_reason", reason)
    trace.set_value("retrieval_selected_chunk_ids", [result.chunk_id for result in selected])
    trace.set_value(
        "retrieval_selected_preview",
        [
            {
                "chunk_id": result.chunk_id,
                "source_type": result.source_type,
                "score": round(float(result.score), 6),
                "title": result.document_title[:80],
            }
            for result in selected[:12]
        ],
    )
    if reranked is not None:
        score_by_index = {item.index: float(item.score) for item in reranked}
        trace.set_value(
            "rerank_score_preview",
            [
                {
                    "chunk_id": candidates[item.index].chunk_id,
                    "score": round(float(item.score), 6),
                }
                for item in reranked[:12]
                if 0 <= item.index < len(candidates)
            ],
        )
        trace.set_value(
            "retrieval_selected_rerank_scores",
            [
                round(score_by_index.get(candidates.index(result), 0.0), 6)
                for result in selected
                if result in candidates
            ],
        )


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
        chunk_type=result.chunk_type,
        source_image_path=result.source_image_path,
        caption=getattr(result, "caption", None),
        page_number=getattr(result, "page_number", None),
    )


def max_result_score(results: list[KeywordSearchResult] | list[VectorSearchResult]) -> float:
    return max((result.score for result in results), default=0.0)


def normalize_score(score: float, max_score: float) -> float:
    if score <= 0 or max_score <= 0:
        return 0.0
    return min(1.0, score / max_score)
