from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from contextvars import ContextVar, Token
import hashlib
import json
from pathlib import Path
import re
import time

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.db.models import Chunk, Document
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
    active_agent_cache_scope,
    get_current_latency_trace,
    latency_timer,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.bm25_search import BM25SearchResult
from app.services.retrieval.bm25_search import BM25SearchService
from app.services.retrieval.keyword_search import source_type_rank
from app.services.retrieval.reranking import ReRankResult, ReRankingProvider, create_reranking_provider
from app.services.retrieval.runtime import (
    RetrievalPlan,
    build_retrieval_plan,
    current_retrieval_plan,
    deterministic_intent_profile,
    reset_current_retrieval_plan,
    retrieval_plan_digest,
    set_current_retrieval_plan,
)
from app.services.retrieval.vector_search import VectorSearchResult
from app.services.retrieval.vector_search import VectorSearchService

_CURRENT_HYDE_VECTOR_QUERY: ContextVar[str] = ContextVar(
    "current_hyde_vector_query",
    default="",
)


GRAPH_QUERY_TERMS = (
    "reference",
    "references",
    "referenced",
    "relationship",
    "relationships",
    "standard",
    "standards",
    "defines",
    "defined",
    "applies",
    "applicable",
    "range",
    "ranges",
    "relation",
    "关联",
    "关系",
    "引用",
    "参考",
    "标准",
    "规范",
    "定义",
    "适用",
    "范围",
    "规定",
)
TABLE_QUERY_TERMS = (
    "table",
    "tabulated",
    "row",
    "column",
    "parameter",
    "parameters",
    "ratio",
    "mix",
    "numeric",
    "range",
    "data",
    "表",
    "表格",
    "参数",
    "配合比",
    "试验数据",
    "数值",
    "范围",
    "行",
    "列",
)
FIGURE_CAPTION_QUERY_TERMS = (
    "figure",
    "image",
    "photo",
    "diagram",
    "chart",
    "curve",
    "microscopy",
    "crack",
    "failure",
    "morphology",
    "图",
    "图片",
    "照片",
    "曲线",
    "图表",
    "示意",
    "裂缝",
    "破坏",
    "形态",
)


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
    channels: tuple[str, ...] = ()
    matched_node_ids: tuple[str, ...] = ()
    graph_hop_count: int | None = None
    relation_types: tuple[str, ...] = ()
    relation_evidence: tuple[str, ...] = ()


@dataclass
class _HybridCandidate:
    result: BM25SearchResult | VectorSearchResult
    keyword_score: float = 0.0
    vector_score: float = 0.0
    channel_scores: dict[str, float] | None = None
    channel_ranks: dict[str, int] | None = None
    matched_node_ids: tuple[str, ...] = ()
    graph_hop_count: int | None = None
    relation_types: tuple[str, ...] = ()
    relation_evidence: tuple[str, ...] = ()


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
                    health_check_enabled=(
                        settings.reranking_health_check_enabled
                        and settings.reranking_provider.strip().casefold()
                        in {
                            "remote-bge-lora",
                            "bge-lora",
                            "rfc-bge-lora",
                            "rfc-domain-bge-lora",
                        }
                    ),
                    health_check_timeout_seconds=settings.reranking_health_check_timeout_seconds,
                    unavailable_ttl_seconds=settings.reranking_unavailable_ttl_seconds,
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

        if (
            self.settings.retrieval_runtime_enabled
            and self.settings.retrieval_runtime_default_enabled
            and current_retrieval_plan() is None
        ):
            default_plan = build_retrieval_plan(
                deterministic_intent_profile(normalized_query),
                normalized_query,
                self.settings,
            )
            token = set_current_retrieval_plan(default_plan)
            try:
                trace = get_current_latency_trace()
                if trace is not None:
                    for key, value in default_plan.diagnostics().items():
                        trace.set_value(key, value)
                    trace.set_value("retrieval_plan_fallback", True)
                    trace.set_value(
                        "retrieval_plan_fallback_reason",
                        "direct_hybrid_default_deterministic",
                    )
                return self.search(normalized_query, top_k=top_k)
            finally:
                reset_current_retrieval_plan(token)

        fetch_k = max(top_k * 3, top_k)
        if self.reranking_enabled and self.reranking_provider is not None:
            fetch_k = max(fetch_k, top_k * 5, self.reranking_recall_k)
        channel_plan = self._channel_plan(normalized_query)
        trace = get_current_latency_trace()
        if trace is not None:
            trace.set_value("lexical_search_backend", "bm25")
        sorted_results = self._lookup_retrieval_cache(
            normalized_query,
            fetch_k=fetch_k,
            channel_plan=channel_plan,
        )
        if sorted_results is None:
            if self.parallel and not channel_plan["multichannel_enabled"]:
                self._progress("正在并行检索关键词和向量候选证据")
                keyword_results, vector_results = self._search_parallel(normalized_query, fetch_k)
            else:
                self._progress("正在检索关键词和向量候选证据")
                keyword_results, vector_results = self._search_serial(normalized_query, fetch_k)

            self._progress("已获得候选证据，正在合并排序")
            if channel_plan["multichannel_enabled"]:
                channel_results: dict[str, list[BM25SearchResult] | list[VectorSearchResult] | list[HybridSearchResult]] = {
                    "bm25": keyword_results,
                    "vector": vector_results,
                }
                channel_results.update(self._optional_channel_results(normalized_query, fetch_k, channel_plan))
                sorted_results = self._fuse_multichannel_results(channel_results)
            else:
                candidates: dict[int, _HybridCandidate] = {}
                add_results(candidates, keyword_results, "bm25", max_result_score(keyword_results))
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
                trace_channel_counts(
                    enabled=["bm25", "vector"],
                    eligible=["bm25", "vector"],
                    counts={"bm25": len(keyword_results), "vector": len(vector_results)},
                )
            self._store_retrieval_cache(
                normalized_query,
                sorted_results,
                fetch_k=fetch_k,
                channel_plan=channel_plan,
            )
        trace_retrieval_candidates(normalized_query, sorted_results, fetch_k=fetch_k)
        selected = self._rerank_results(normalized_query, sorted_results, top_k=top_k)
        trace_required_channel_satisfaction(
            selected=selected,
            channel_plan=channel_plan,
        )
        trace_graph_selection(selected)
        return selected

    def _retrieval_cache_identity(
        self,
        query: str,
        *,
        fetch_k: int,
        channel_plan: dict[str, object] | None = None,
    ) -> dict[str, object]:
        channel_plan = channel_plan or self._channel_plan(query)
        identity = base_cache_identity(self.db)
        identity.update(
            {
                "layer": "retrieval",
                "agent_cache_scope": active_agent_cache_scope(),
                "query": normalized_query_identity(query),
                "fetch_k": fetch_k,
                "hybrid_multichannel_enabled": channel_plan["multichannel_enabled"],
                "enabled_channels": channel_plan["enabled_channels"],
                "eligible_channels": channel_plan["eligible_channels"],
                "channel_fusion": "rrf-v1" if channel_plan["multichannel_enabled"] else "weighted-score-v1",
                "channel_rank_constant": self.settings.hybrid_channel_rank_constant,
                "graph_path": self.settings.graphrag_graph_path if "graph" in channel_plan["eligible_channels"] else "",
                "graph_fingerprint": self._graph_fingerprint(channel_plan),
                "retrieval_runtime_mode": channel_plan.get("runtime_mode", "legacy"),
                "retrieval_plan_digest": channel_plan.get("retrieval_plan_digest", "legacy"),
                "retrieval_pipeline_schema": (
                    "hybrid-phase63-gap-closure-bm25-pgvector-v1"
                    if channel_plan.get("runtime_mode") == "phase63"
                    else "hybrid-legacy-v1"
                ),
                "channel_requirements": channel_plan.get("channel_requirements", {}),
                "graph_max_hops": channel_plan.get("graph_max_hops", 2),
                "graph_max_matches": channel_plan.get("graph_max_matches", 0),
                "keyword_weight": self.keyword_weight,
                "vector_weight": self.vector_weight,
                "both_match_bonus": self.both_match_bonus,
                "graph_weight": self.settings.hybrid_graph_channel_weight,
                "table_text_weight": self.settings.hybrid_table_text_channel_weight,
                "figure_caption_weight": self.settings.hybrid_figure_caption_channel_weight,
                "embedding_provider": self.embedding_provider.provider_name,
                "embedding_model": self.embedding_provider.model_name,
                "embedding_dimension": self.embedding_provider.dimension,
                "pgvector_enabled": get_settings().pgvector_search_enabled,
                "hyde_vector_query_hash": hyde_vector_query_hash(),
            }
        )
        return identity

    def _lookup_retrieval_cache(
        self,
        query: str,
        *,
        fetch_k: int,
        channel_plan: dict[str, object] | None = None,
    ) -> list[HybridSearchResult] | None:
        cache = get_configured_layered_cache("retrieval")
        trace = get_current_latency_trace()
        if cache is None:
            if trace is not None:
                trace.set_value("retrieval_cache_hit", False)
                trace.set_value("retrieval_cache_backend", "disabled")
                trace.set_value("retrieval_cache_reason", "disabled")
            return None
        started = time.perf_counter()
        lookup = cache.lookup(
            self._retrieval_cache_identity(query, fetch_k=fetch_k, channel_plan=channel_plan)
        )
        if not lookup.hit or lookup.payload is None:
            if trace is not None:
                trace.set_value("retrieval_cache_hit", False)
                trace.set_value("retrieval_cache_backend", lookup.backend)
                trace.set_value("retrieval_cache_reason", lookup.reason)
                trace.add_duration("retrieval_cache_lookup_latency_ms", (time.perf_counter() - started) * 1000.0)
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
        hydrate_started = time.perf_counter()
        hydrated = hydrate_chunk_rows(self.db, chunk_ids)
        hydrate_ms = (time.perf_counter() - hydrate_started) * 1000.0
        if len(hydrated) != len(chunk_ids):
            if trace is not None:
                trace.set_value("retrieval_cache_hit", False)
                trace.set_value("retrieval_cache_backend", lookup.backend)
                trace.set_value("retrieval_cache_reason", "hydrate_miss")
                trace.add_duration("retrieval_cache_hydrate_latency_ms", hydrate_ms)
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
                    channels=tuple(str(item) for item in cached.get("channels", []) if isinstance(item, str)),
                    matched_node_ids=tuple(
                        str(item) for item in cached.get("matched_node_ids", []) if isinstance(item, str)
                    ),
                    graph_hop_count=(
                        int(cached["graph_hop_count"])
                        if isinstance(cached.get("graph_hop_count"), int)
                        else None
                    ),
                    relation_types=tuple(
                        str(item) for item in cached.get("relation_types", []) if isinstance(item, str)
                    ),
                    relation_evidence=tuple(
                        str(item) for item in cached.get("relation_evidence", []) if isinstance(item, str)
                    ),
                )
            )
        if isinstance(payload.get("channel_counts"), dict):
            trace_channel_counts(
                enabled=payload.get("enabled_channels", []),
                eligible=payload.get("eligible_channels", []),
                counts=payload.get("channel_counts", {}),
            )
        if trace is not None:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            trace.set_value("retrieval_cache_hit", True)
            trace.set_value("retrieval_cache_backend", lookup.backend)
            trace.set_value("retrieval_cache_reason", lookup.reason)
            trace.set_value("retrieval_cache_row_count", len(results))
            trace.add_duration("retrieval_cache_lookup_latency_ms", elapsed_ms)
            trace.add_duration("retrieval_cache_hydrate_latency_ms", hydrate_ms)
        return results

    def _store_retrieval_cache(
        self,
        query: str,
        results: list[HybridSearchResult],
        *,
        fetch_k: int,
        channel_plan: dict[str, object] | None = None,
    ) -> None:
        cache = get_configured_layered_cache("retrieval")
        if cache is None:
            return
        channel_counts = channel_candidate_counts(results)
        payload = {
            "enabled_channels": list(channel_plan.get("enabled_channels", [])) if channel_plan else [],
            "eligible_channels": list(channel_plan.get("eligible_channels", [])) if channel_plan else [],
            "channel_counts": channel_counts,
            "rows": [
                {
                    "chunk_id": result.chunk_id,
                    "score": float(result.score),
                    "keyword_score": float(result.keyword_score),
                    "vector_score": float(result.vector_score),
                    "chunk_type": result.chunk_type,
                    "source_type": result.source_type,
                    "channels": list(result.channels),
                    "matched_node_ids": list(result.matched_node_ids),
                    "graph_hop_count": result.graph_hop_count,
                    "relation_types": list(result.relation_types),
                    "relation_evidence": list(result.relation_evidence),
                }
                for result in results
            ]
        }
        cache.store(
            self._retrieval_cache_identity(query, fetch_k=fetch_k, channel_plan=channel_plan),
            payload,
        )

    def _channel_plan(self, query: str) -> dict[str, object]:
        enabled = ["bm25", "vector"]
        if self.settings.hybrid_graph_channel_enabled:
            enabled.append("graph")
        if self.settings.hybrid_table_text_channel_enabled:
            enabled.append("table_text")
        if self.settings.hybrid_figure_caption_channel_enabled:
            enabled.append("figure_caption")
        plan = current_retrieval_plan() if self.settings.retrieval_runtime_enabled else None
        requirements = {
            "graph": plan.graph_requirement if plan else "legacy",
            "table_text": plan.table_text_requirement if plan else "legacy",
            "figure_caption": plan.figure_caption_requirement if plan else "legacy",
        }
        eligible = ["bm25", "vector"]
        if plan is not None:
            for channel in ("graph", "table_text", "figure_caption"):
                if channel in enabled and requirements[channel] in {"preferred", "required"}:
                    eligible.append(channel)
        else:
            if "graph" in enabled and query_matches_terms(query, GRAPH_QUERY_TERMS):
                eligible.append("graph")
            if "table_text" in enabled and query_matches_terms(query, TABLE_QUERY_TERMS):
                eligible.append("table_text")
            if "figure_caption" in enabled and query_matches_terms(query, FIGURE_CAPTION_QUERY_TERMS):
                eligible.append("figure_caption")
        return {
            "multichannel_enabled": bool(self.settings.hybrid_multichannel_enabled),
            "enabled_channels": tuple(enabled),
            "eligible_channels": tuple(eligible),
            "channel_requirements": requirements,
            "runtime_mode": "phase63" if plan is not None else "legacy",
            "retrieval_plan_digest": retrieval_plan_digest(plan),
            "graph_max_hops": plan.graph_max_hops if plan else 2,
            "graph_max_matches": (
                plan.graph_max_matches if plan else int(self.settings.hybrid_graph_max_matches)
            ),
            "relationship_type": plan.relationship_type if plan else "none",
        }

    def _graph_fingerprint(self, channel_plan: dict[str, object]) -> str:
        if "graph" not in channel_plan.get("eligible_channels", ()):
            return "disabled"
        from app.services.graphrag.retriever import graph_content_fingerprint

        fingerprint = graph_content_fingerprint(
            Path(self.settings.graphrag_graph_path)
        )
        trace = get_current_latency_trace()
        if trace is not None:
            trace.set_value("graph_fingerprint", fingerprint)
        return fingerprint

    def _optional_channel_results(
        self,
        query: str,
        fetch_k: int,
        channel_plan: dict[str, object],
    ) -> dict[str, list[HybridSearchResult]]:
        results: dict[str, list[HybridSearchResult]] = {}
        eligible = set(channel_plan["eligible_channels"])
        channel_order = [
            channel
            for channel in ("graph", "table_text", "figure_caption")
            if channel in eligible
        ]
        if channel_order:
            bind = self.db.get_bind()
            ThreadSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=bind)
            trace = get_current_latency_trace()

            def run_channel(channel: str) -> list[HybridSearchResult]:
                token = set_current_latency_trace(trace)
                with ThreadSessionLocal() as db:
                    try:
                        if channel == "graph":
                            return self._graph_channel_results(
                                query,
                                db=db,
                                channel_plan=channel_plan,
                            )
                        if channel == "table_text":
                            return self._chunk_type_channel_results(
                                query,
                                chunk_type="table",
                                top_k=fetch_k,
                                db=db,
                            )
                        if channel == "figure_caption":
                            return self._chunk_type_channel_results(
                                query,
                                chunk_type="image_description",
                                top_k=fetch_k,
                                db=db,
                            )
                        return []
                    finally:
                        reset_current_latency_trace(token)

            with ThreadPoolExecutor(
                max_workers=len(channel_order),
                thread_name_prefix="hybrid-channel",
            ) as executor:
                future_by_channel = {
                    channel: executor.submit(run_channel, channel)
                    for channel in channel_order
                }
                for channel in channel_order:
                    results[channel] = future_by_channel[channel].result()
        trace_channel_counts(
            enabled=channel_plan["enabled_channels"],
            eligible=channel_plan["eligible_channels"],
            counts={channel: len(rows) for channel, rows in results.items()},
        )
        return results

    def _graph_channel_results(
        self,
        query: str,
        *,
        db: Session | None = None,
        channel_plan: dict[str, object] | None = None,
    ) -> list[HybridSearchResult]:
        active_db = db or self.db
        active_plan = channel_plan or self._channel_plan(query)
        from app.services.graphrag.graph_search import graph_results_from_matches
        from app.services.graphrag.retriever import GraphRetriever

        with latency_timer("graph_channel_latency_ms"):
            outcome = GraphRetriever(
                graph_path=Path(self.settings.graphrag_graph_path)
            ).retrieve(
                query,
                max_hops=int(active_plan.get("graph_max_hops", 2)),
                max_matches=int(
                    active_plan.get(
                        "graph_max_matches",
                        self.settings.hybrid_graph_max_matches,
                    )
                ),
                # Intent labels such as ``causal`` or ``standard_reference``
                # describe the question, not necessarily the graph's exact
                # edge predicate vocabulary. Preserve all local relations for
                # provenance-aware reranking instead of exact-filtering here.
                relation_focus=None,
            )
        return graph_results_from_matches(active_db, outcome.candidates)

    def _chunk_type_channel_results(
        self,
        query: str,
        *,
        chunk_type: str,
        top_k: int,
        db: Session | None = None,
    ) -> list[HybridSearchResult]:
        active_db = db or self.db
        terms = query_channel_terms(query)
        if not terms:
            return []
        latency_field = (
            "figure_channel_latency_ms"
            if chunk_type == "image_description"
            else "table_channel_latency_ms"
        )
        conditions = [Chunk.content.ilike(f"%{term}%") for term in terms[:8]]
        if chunk_type == "image_description":
            conditions.extend(Chunk.caption.ilike(f"%{term}%") for term in terms[:8])
        statement = (
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.chunk_type == chunk_type)
            .where(or_(*conditions))
            .order_by(Chunk.id.asc())
            .limit(max(top_k * 4, top_k))
        )
        with latency_timer(latency_field):
            rows = active_db.execute(statement).all()
        scored: list[HybridSearchResult] = []
        for chunk, document in rows:
            score = chunk_text_match_score(" ".join([chunk.content or "", chunk.caption or ""]), terms)
            if score <= 0:
                continue
            scored.append(
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
                    score=float(score),
                    keyword_score=0.0,
                    vector_score=0.0,
                    chunk_type=chunk.chunk_type,
                    source_image_path=chunk.source_image_path,
                    caption=chunk.caption,
                    page_number=chunk.page_number,
                )
            )
        return sorted(scored, key=lambda item: (-item.score, item.document_id, item.chunk_index))[:top_k]

    def _fuse_multichannel_results(
        self,
        channel_results: dict[str, list[BM25SearchResult] | list[VectorSearchResult] | list[HybridSearchResult]],
    ) -> list[HybridSearchResult]:
        fused: dict[int, _HybridCandidate] = {}
        weights = {
            "bm25": self.keyword_weight,
            "vector": self.vector_weight,
            "graph": self.settings.hybrid_graph_channel_weight,
            "table_text": self.settings.hybrid_table_text_channel_weight,
            "figure_caption": self.settings.hybrid_figure_caption_channel_weight,
        }
        rank_constant = max(1, int(self.settings.hybrid_channel_rank_constant))
        counts: dict[str, int] = {}
        for channel, results in channel_results.items():
            counts[channel] = len(results)
            for rank, result in enumerate(results, start=1):
                candidate = fused.setdefault(result.chunk_id, _HybridCandidate(result=result))
                if candidate.channel_scores is None:
                    candidate.channel_scores = {}
                if candidate.channel_ranks is None:
                    candidate.channel_ranks = {}
                rrf_score = float(weights.get(channel, 1.0)) / float(rank_constant + rank)
                candidate.channel_scores[channel] = max(candidate.channel_scores.get(channel, 0.0), rrf_score)
                candidate.channel_ranks[channel] = min(candidate.channel_ranks.get(channel, rank), rank)
                if channel == "graph":
                    candidate.matched_node_ids = tuple(
                        getattr(result, "matched_node_ids", ())
                    )
                    candidate.graph_hop_count = getattr(
                        result,
                        "graph_hop_count",
                        None,
                    )
                    candidate.relation_types = tuple(
                        getattr(result, "relation_types", ())
                    )
                    candidate.relation_evidence = tuple(
                        getattr(result, "relation_evidence", ())
                    )
                if channel == "bm25":
                    candidate.keyword_score = max(candidate.keyword_score, normalize_score(result.score, max_result_score(results)))
                if channel == "vector":
                    candidate.vector_score = max(candidate.vector_score, normalize_score(result.score, max_result_score(results)))
        results = [candidate_to_result(candidate, self) for candidate in fused.values()]
        trace_channel_counts(
            enabled=list(channel_results),
            eligible=list(channel_results),
            counts=counts,
        )
        return sorted(
            results,
            key=lambda item: (
                -item.score,
                source_type_rank(item.source_type),
                item.document_id,
                item.chunk_index,
            ),
        )

    def _search_serial(
        self,
        query: str,
        fetch_k: int,
    ) -> tuple[list[BM25SearchResult], list[VectorSearchResult]]:
        with latency_timer("bm25_search_latency_ms"):
            keyword_results = BM25SearchService(self.db).search(query, top_k=fetch_k)
        vector_query = current_hyde_vector_query() or query
        vector_results = self._vector_search_service(self.db).search(
            vector_query,
            top_k=fetch_k,
        )
        return keyword_results, vector_results

    def _search_parallel(
        self,
        query: str,
        fetch_k: int,
    ) -> tuple[list[BM25SearchResult], list[VectorSearchResult]]:
        bind = self.db.get_bind()
        ThreadSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=bind)

        def run_keyword() -> list[BM25SearchResult]:
            token = set_current_latency_trace(trace)
            with ThreadSessionLocal() as db:
                try:
                    with latency_timer("bm25_search_latency_ms"):
                        return BM25SearchService(db).search(query, top_k=fetch_k)
                finally:
                    reset_current_latency_trace(token)

        trace = get_current_latency_trace()
        vector_query = current_hyde_vector_query() or query

        def run_vector() -> list[VectorSearchResult]:
            token = set_current_latency_trace(trace)
            with ThreadSessionLocal() as db:
                try:
                    return self._vector_search_service(db).search(
                        vector_query,
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
        if not results:
            return []
        active_plan = (
            current_retrieval_plan()
            if self.settings.retrieval_runtime_enabled
            else None
        )
        required_channels = required_channels_for_plan(active_plan)
        if not self.reranking_enabled:
            selected = select_fusion_results(
                results,
                requested_top_k=top_k,
                settings=self.settings,
                required_channels=required_channels,
            )
            trace_selected_results(
                query=query,
                candidates=results,
                selected=selected,
                requested_top_k=top_k,
                dynamic=self.settings.reranking_dynamic_top_k_enabled,
                reason="reranking_disabled",
            )
            return selected
        rerank_candidates = reserve_required_rerank_candidates(
            results,
            limit=max(1, min(len(results), self.reranking_recall_k)),
            plan=active_plan,
        )
        trace = get_current_latency_trace()
        if self.reranking_provider is None:
            if self.settings.reranking_fusion_fail_soft_enabled:
                return self._select_fusion_fail_soft(
                    query=query,
                    candidates=rerank_candidates,
                    top_k=top_k,
                    error_type="not_configured",
                    required_channels=required_channels,
                )
            raise RuntimeError("重排序失效：未配置 reranker。")
        if trace is not None:
            trace.set_value("reranking_provider", self.reranking_provider.provider_name)
            trace.set_value("reranking_model", self.reranking_provider.model_name)
            trace.set_value("reranking_fallback", False)
            trace.set_value("reranking_error", "")
            trace.set_value("reranking_candidate_count", len(rerank_candidates))
        cached_results = self._lookup_rerank_cache(
            query,
            rerank_candidates,
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
                    candidates=[rerank_candidate_text(result) for result in rerank_candidates],
                    top_k=rerank_request_top_k(rerank_candidates, top_k, self.settings),
                )
            if rerank_scores_are_degenerate(reranked):
                if reranker_allows_degenerate_fusion(self.reranking_provider):
                    if trace is not None:
                        trace.set_value("reranking_score_quality", "degenerate_fusion_dynamic")
                        trace.set_value("reranking_degenerate_scores", True)
                        trace.set_value(
                            "rerank_score_preview",
                            [round(float(item.score), 6) for item in reranked[:12]],
                        )
                    reranked_results = select_fusion_results(
                        rerank_candidates,
                        requested_top_k=top_k,
                        settings=self.settings,
                        required_channels=required_channels,
                    )
                    trace_selected_results(
                        query=query,
                        candidates=results,
                        selected=reranked_results,
                        requested_top_k=top_k,
                        dynamic=self.settings.reranking_dynamic_top_k_enabled,
                        reason="rerank_degenerate_fusion_dynamic",
                    )
                    self._store_rerank_cache(
                        query,
                        rerank_candidates,
                        reranked_results,
                        top_k=top_k,
                        provider_name=self.reranking_provider.provider_name,
                        model_name=self.reranking_provider.model_name,
                        fallback=False,
                    )
                    return reranked_results
                raise RuntimeError("reranker returned degenerate scores")
        except Exception as exc:
            # Reranking is required for the default hybrid path. If the primary
            # reranker fails, only a configured fallback reranker may recover it.
            if trace is not None:
                trace.set_value("reranking_fallback", True)
                fallback_count = int(trace.values.get("reranking_fallback_count", 0)) + 1
                trace.set_value("reranking_fallback_count", fallback_count)
                trace.set_value("reranking_error", "runtime_error")
                trace.set_value("reranking_error_type", type(exc).__name__)
                trace.set_value("reranking_error_summary", str(exc)[:220])
            fallback_configured = self.reranking_fallback_provider is not None
            fallback_reranked = self._rerank_with_fallback_provider(
                query,
                rerank_candidates,
                top_k=top_k,
            )
            if fallback_reranked is not None:
                return fallback_reranked
            if self.settings.reranking_fusion_fail_soft_enabled:
                return self._select_fusion_fail_soft(
                    query=query,
                    candidates=rerank_candidates,
                    top_k=top_k,
                    error_type="dual_failure" if fallback_configured else "fallback_not_configured",
                    required_channels=required_channels,
                )
            if fallback_configured:
                raise RuntimeError("重排序失效：主 reranker 失败，GLM fallback reranker 也失败。") from None
            raise RuntimeError(
                "重排序失效：主 reranker 重试后仍失败，未配置独立 fallback reranker。"
            ) from None
        reranked_results = select_reranked_results(
            rerank_candidates,
            reranked,
            requested_top_k=top_k,
            settings=self.settings,
            required_channels=required_channels,
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
            rerank_candidates,
            reranked_results,
            top_k=top_k,
            provider_name=self.reranking_provider.provider_name,
            model_name=self.reranking_provider.model_name,
            fallback=False,
        )
        return reranked_results

    def _select_fusion_fail_soft(
        self,
        *,
        query: str,
        candidates: list[HybridSearchResult],
        top_k: int,
        error_type: str,
        required_channels: tuple[str, ...],
    ) -> list[HybridSearchResult]:
        selected = select_fusion_results(
            candidates,
            requested_top_k=top_k,
            settings=self.settings,
            required_channels=required_channels,
        )
        trace = get_current_latency_trace()
        if trace is not None:
            trace.set_value("reranking_degraded", True)
            trace.set_value("reranking_degradation_level", "fusion_fail_soft")
            trace.set_value("reranking_error", "runtime_error")
            trace.set_value("reranking_error_type", error_type)
        trace_selected_results(
            query=query,
            candidates=candidates,
            selected=selected,
            requested_top_k=top_k,
            dynamic=self.settings.reranking_dynamic_top_k_enabled,
            reason="reranker_unavailable_fusion_dynamic",
        )
        return selected

    def _rerank_with_fallback_provider(
        self,
        query: str,
        results: list[HybridSearchResult],
        *,
        top_k: int,
    ) -> list[HybridSearchResult] | None:
        if self.reranking_fallback_provider is None:
            trace = get_current_latency_trace()
            if trace is not None:
                trace.set_value("reranking_fallback_used", False)
                trace.set_value("reranking_fallback_error", "not_configured")
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
                    candidates=[rerank_candidate_text(result) for result in results],
                    top_k=rerank_request_top_k(results, top_k, self.settings),
                )
        except Exception:
            if trace is not None:
                trace.set_value("reranking_fallback_error", "runtime_error")
            return None
        if rerank_scores_are_degenerate(reranked):
            if trace is not None:
                trace.set_value("reranking_fallback_used", True)
                trace.set_value("reranking_fallback_error", "")
                trace.set_value("reranking_fallback_score_quality", "degenerate_fusion_dynamic")
                trace.set_value("reranking_fallback_degenerate_scores", True)
                trace.set_value(
                    "reranking_fallback_score_preview",
                    [round(float(item.score), 6) for item in reranked[:12]],
                )
            reranked_results = select_fusion_results(
                results,
                requested_top_k=top_k,
                settings=self.settings,
            )
            trace_selected_results(
                query=query,
                candidates=results,
                selected=reranked_results,
                requested_top_k=top_k,
                dynamic=self.settings.reranking_dynamic_top_k_enabled,
                reason="rerank_fallback_degenerate_fusion_dynamic",
            )
            return reranked_results
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
        active_plan = (
            current_retrieval_plan()
            if self.settings.retrieval_runtime_enabled
            else None
        )
        graph_fingerprint = "disabled"
        if active_plan is not None and active_plan.graph_requirement != "disabled":
            from app.services.graphrag.retriever import graph_content_fingerprint

            graph_fingerprint = graph_content_fingerprint(
                Path(self.settings.graphrag_graph_path)
            )
        identity = base_cache_identity(self.db)
        identity.update(
            {
                "layer": "rerank",
                "agent_cache_scope": active_agent_cache_scope(),
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
                "quality_gate": "nondegenerate-scores-v1",
                "retrieval_plan_digest": retrieval_plan_digest(
                    active_plan
                ),
                "retrieval_pipeline_schema": (
                "hybrid-phase63-gap-closure-bm25-pgvector-v1"
                if active_plan is not None
                else "hybrid-legacy-bm25-v2"
                ),
                "graph_fingerprint": graph_fingerprint,
                "rerank_input_hash": rerank_input_identity_hash(results),
                "graph_weight": self.settings.hybrid_graph_channel_weight,
                "table_text_weight": self.settings.hybrid_table_text_channel_weight,
                "figure_caption_weight": self.settings.hybrid_figure_caption_channel_weight,
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
        trace = get_current_latency_trace()
        lane = "fallback" if fallback else "primary"
        if cache is None:
            if trace is not None:
                trace.set_value(f"rerank_cache_{lane}_hit", False)
                trace.set_value(f"rerank_cache_{lane}_backend", "disabled")
                trace.set_value(f"rerank_cache_{lane}_reason", "disabled")
            return None
        started = time.perf_counter()
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
            if trace is not None:
                trace.set_value(f"rerank_cache_{lane}_hit", False)
                trace.set_value(f"rerank_cache_{lane}_backend", lookup.backend)
                trace.set_value(f"rerank_cache_{lane}_reason", lookup.reason)
                trace.add_duration("rerank_cache_lookup_latency_ms", (time.perf_counter() - started) * 1000.0)
            return None
        payload = lookup.payload.get("payload", {})
        chunk_ids = payload.get("chunk_ids")
        if not isinstance(chunk_ids, list) or not all(isinstance(chunk_id, int) for chunk_id in chunk_ids):
            if trace is not None:
                trace.set_value(f"rerank_cache_{lane}_hit", False)
                trace.set_value(f"rerank_cache_{lane}_backend", lookup.backend)
                trace.set_value(f"rerank_cache_{lane}_reason", "invalid_payload")
            return None
        by_chunk_id = {result.chunk_id: result for result in results}
        if any(chunk_id not in by_chunk_id for chunk_id in chunk_ids):
            if trace is not None:
                trace.set_value(f"rerank_cache_{lane}_hit", False)
                trace.set_value(f"rerank_cache_{lane}_backend", lookup.backend)
                trace.set_value(f"rerank_cache_{lane}_reason", "candidate_miss")
            return None
        selected = [by_chunk_id[chunk_id] for chunk_id in chunk_ids]
        if trace is not None:
            trace.set_value(f"rerank_cache_{lane}_hit", True)
            trace.set_value(f"rerank_cache_{lane}_backend", lookup.backend)
            trace.set_value(f"rerank_cache_{lane}_reason", lookup.reason)
            trace.set_value(f"rerank_cache_{lane}_row_count", len(selected))
            trace.add_duration("rerank_cache_lookup_latency_ms", (time.perf_counter() - started) * 1000.0)
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


def rerank_scores_are_degenerate(reranked: list[ReRankResult]) -> bool:
    if len(reranked) <= 1:
        return False
    scores = [float(item.score) for item in reranked]
    return max(scores) - min(scores) <= 1e-9


def reranker_allows_degenerate_fusion(provider: ReRankingProvider) -> bool:
    provider_name = getattr(provider, "provider_name", "").strip().casefold()
    model_name = getattr(provider, "model_name", "").strip().casefold()
    return provider_name in {"paratera", "glm", "zhipu", "bigmodel"} or "glm" in model_name


def select_reranked_results(
    results: list[HybridSearchResult],
    reranked: list[ReRankResult],
    *,
    requested_top_k: int,
    settings: object,
    required_channels: tuple[str, ...] | None = None,
) -> list[HybridSearchResult]:
    if not reranked:
        return []
    ordered = [results[item.index] for item in reranked]
    if not getattr(settings, "reranking_dynamic_top_k_enabled", False):
        return select_constrained_results(
            ordered,
            target_count=min(requested_top_k, len(ordered)),
            required_channels=required_channels,
        )

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
    return select_constrained_results(
        ordered,
        target_count=len(selected),
        required_channels=required_channels,
    )


def select_fusion_results(
    results: list[HybridSearchResult],
    *,
    requested_top_k: int,
    settings: object,
    required_channels: tuple[str, ...] | None = None,
) -> list[HybridSearchResult]:
    if not results:
        return []
    if not getattr(settings, "reranking_dynamic_top_k_enabled", False):
        return select_constrained_results(
            results,
            target_count=min(requested_top_k, len(results)),
            required_channels=required_channels,
        )

    max_results = max(1, int(getattr(settings, "reranking_dynamic_max_results", requested_top_k)))
    max_results = min(max_results, len(results))
    min_results = max(1, int(getattr(settings, "reranking_dynamic_min_results", 1)))
    min_results = min(min_results, max_results)
    threshold_ratio = float(getattr(settings, "reranking_dynamic_relative_score_threshold", 0.0))
    threshold_ratio = min(max(threshold_ratio, 0.0), 1.0)
    best_score = max((float(result.score) for result in results), default=0.0)
    threshold = best_score * threshold_ratio

    selected: list[HybridSearchResult] = []
    for position, result in enumerate(results[:max_results]):
        if position < min_results or float(result.score) >= threshold:
            selected.append(result)
    return select_constrained_results(
        results,
        target_count=len(selected),
        required_channels=required_channels,
    )


def select_constrained_results(
    ordered: list[HybridSearchResult],
    *,
    target_count: int,
    required_channels: tuple[str, ...] | None = None,
) -> list[HybridSearchResult]:
    """Select a bounded ordered set while retaining available required lanes."""
    if not ordered:
        return []
    requirements = required_channels or required_channels_for_plan(current_retrieval_plan())
    selected = list(ordered[: max(0, min(target_count, len(ordered)))])
    if not requirements:
        return selected

    max_count = max(0, min(len(ordered), max(target_count, len(requirements))))
    for channel in requirements:
        if any(channel in item.channels for item in selected):
            continue
        required_candidate = next(
            (item for item in ordered if channel in item.channels),
            None,
        )
        if required_candidate is None:
            continue
        if len(selected) < max_count:
            selected.append(required_candidate)
            continue
        protected_channels = {
            required_channel
            for required_channel in requirements
            if any(required_channel in item.channels for item in selected)
        }
        replace_index = next(
            (
                index
                for index in range(len(selected) - 1, -1, -1)
                if not protected_channels.intersection(selected[index].channels)
            ),
            None,
        )
        if replace_index is not None:
            selected[replace_index] = required_candidate

    selected_ids = {item.chunk_id for item in selected}
    return [item for item in ordered if item.chunk_id in selected_ids]


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
                "channels": list(result.channels),
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
                "channels": list(result.channels),
                "title": result.document_title[:80],
            }
            for result in selected[:12]
        ],
    )
    trace.set_value(
        "retrieval_selected_channels",
        sorted({channel for result in selected for channel in result.channels}),
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
    results: list[BM25SearchResult] | list[VectorSearchResult],
    channel: str,
    max_score: float,
) -> None:
    for result in results:
        candidate = candidates.setdefault(result.chunk_id, _HybridCandidate(result=result))
        normalized_score = normalize_score(result.score, max_score)
        if channel == "bm25":
            candidate.keyword_score = max(candidate.keyword_score, normalized_score)
        elif channel == "vector":
            candidate.vector_score = max(candidate.vector_score, normalized_score)
        else:
            raise ValueError(f"Unsupported hybrid channel: {channel}")


def candidate_to_result(candidate: _HybridCandidate, service: HybridSearchService) -> HybridSearchResult:
    bonus = service.both_match_bonus if candidate.keyword_score > 0 and candidate.vector_score > 0 else 0.0
    channel_scores = candidate.channel_scores or {}
    if channel_scores:
        combined_score = sum(channel_scores.values())
        channels = tuple(sorted(channel_scores))
    else:
        combined_score = (
            candidate.keyword_score * service.keyword_weight
            + candidate.vector_score * service.vector_weight
            + bonus
        )
        channels = tuple(
            channel
            for channel, score in (
                ("bm25", candidate.keyword_score),
                ("vector", candidate.vector_score),
            )
            if score > 0
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
        channels=channels,
        matched_node_ids=(
            candidate.matched_node_ids
            or tuple(getattr(result, "matched_node_ids", ()))
        ),
        graph_hop_count=(
            candidate.graph_hop_count
            if candidate.graph_hop_count is not None
            else getattr(result, "graph_hop_count", None)
        ),
        relation_types=(
            candidate.relation_types
            or tuple(getattr(result, "relation_types", ()))
        ),
        relation_evidence=(
            candidate.relation_evidence
            or tuple(getattr(result, "relation_evidence", ()))
        ),
    )


def rerank_candidate_text(result: HybridSearchResult) -> str:
    if not result.relation_types and not result.relation_evidence:
        return result.content
    relation_types = ", ".join(result.relation_types)
    evidence = "\n".join(
        f"Graph relation: {item}" for item in result.relation_evidence
    )
    return (
        f"Graph relation types: {relation_types}\n"
        f"{evidence}\n"
        f"Document title: {result.document_title}\n"
        f"{result.content}"
    )


def reserve_required_rerank_candidates(
    results: list[HybridSearchResult],
    *,
    limit: int,
    plan: RetrievalPlan | None,
) -> list[HybridSearchResult]:
    bounded_limit = max(0, min(int(limit), len(results)))
    pool = list(results[:bounded_limit])
    if not pool or plan is None:
        return pool
    required_channels = list(required_channels_for_plan(plan))
    protected: set[str] = {
        channel
        for channel in required_channels
        if any(channel in item.channels for item in pool)
    }
    for channel in required_channels:
        if channel in protected:
            continue
        candidate = next(
            (
                item
                for item in results[bounded_limit:]
                if channel in item.channels
                and all(item.chunk_id != current.chunk_id for current in pool)
            ),
            None,
        )
        if candidate is None:
            continue
        replace_index = next(
            (
                index
                for index in range(len(pool) - 1, -1, -1)
                if not protected.intersection(pool[index].channels)
            ),
            None,
        )
        if replace_index is None:
            continue
        pool[replace_index] = candidate
        protected.add(channel)
    return pool


def required_channels_for_plan(plan: RetrievalPlan | None) -> tuple[str, ...]:
    if plan is None:
        return ()
    return tuple(
        channel
        for channel, requirement in (
            ("graph", plan.graph_requirement),
            ("table_text", plan.table_text_requirement),
            ("figure_caption", plan.figure_caption_requirement),
        )
        if requirement == "required"
    )


def rerank_input_identity_hash(results: list[HybridSearchResult]) -> str:
    payload = [
        {
            "chunk_id": result.chunk_id,
            "text_hash": hashlib.sha256(
                rerank_candidate_text(result).encode("utf-8")
            ).hexdigest(),
        }
        for result in results
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def trace_required_channel_satisfaction(
    *,
    selected: list[HybridSearchResult],
    channel_plan: dict[str, object],
) -> None:
    requirements = channel_plan.get("channel_requirements")
    if not isinstance(requirements, dict):
        return
    required = [
        channel
        for channel in ("graph", "table_text", "figure_caption")
        if requirements.get(channel) == "required"
    ]
    trace = get_current_latency_trace()
    if trace is not None:
        trace.set_value("retrieval_required_channels", required)
        trace.set_value("retrieval_required_channel_insertions", [])
        trace.set_value(
            "retrieval_required_channels_satisfied",
            all(any(channel in item.channels for item in selected) for channel in required),
        )


def trace_graph_selection(results: list[HybridSearchResult]) -> None:
    trace = get_current_latency_trace()
    if trace is None:
        return
    graph_results = [item for item in results if "graph" in item.channels]
    relation_types = sorted(
        {
            relation_type
            for item in graph_results
            for relation_type in item.relation_types
            if relation_type
        }
    )
    trace.set_value("graph_selected_count", len(graph_results))
    trace.set_value(
        "graph_selected_chunk_ids",
        [item.chunk_id for item in graph_results[:20]],
    )
    trace.set_value("graph_relation_type_preview", relation_types[:12])


def max_result_score(
    results: list[BM25SearchResult] | list[VectorSearchResult] | list[HybridSearchResult],
) -> float:
    return max((result.score for result in results), default=0.0)


def normalize_score(score: float, max_score: float) -> float:
    if score <= 0 or max_score <= 0:
        return 0.0
    return min(1.0, score / max_score)


def query_matches_terms(query: str, terms: tuple[str, ...]) -> bool:
    normalized = query.casefold()
    compact = normalized.replace(" ", "")
    for term in terms:
        lowered = term.casefold()
        if lowered in normalized or lowered.replace(" ", "") in compact:
            return True
    return False


def query_channel_terms(query: str) -> list[str]:
    normalized = query.strip()
    if not normalized:
        return []
    ascii_terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9./+-]*", normalized)
    chinese_terms = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
    terms = [term.casefold() for term in ascii_terms if len(term) >= 2]
    terms.extend(chinese_terms)
    return list(dict.fromkeys(terms))


def chunk_text_match_score(text: str, terms: list[str]) -> float:
    normalized = text.casefold()
    score = 0.0
    for term in terms:
        if term.casefold() in normalized:
            score += 1.0
    return score


def channel_candidate_counts(results: list[HybridSearchResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        for channel in result.channels:
            counts[channel] = counts.get(channel, 0) + 1
    return counts


def set_current_hyde_vector_query(query: str) -> Token[str]:
    return _CURRENT_HYDE_VECTOR_QUERY.set(query)


def reset_current_hyde_vector_query(token: Token[str]) -> None:
    _CURRENT_HYDE_VECTOR_QUERY.reset(token)


def current_hyde_vector_query() -> str:
    return _CURRENT_HYDE_VECTOR_QUERY.get()


def hyde_vector_query_hash() -> str:
    query = current_hyde_vector_query()
    if not query:
        return ""
    return hashlib.sha256(" ".join(query.split()).encode("utf-8")).hexdigest()


def trace_channel_counts(
    *,
    enabled: object,
    eligible: object,
    counts: object,
) -> None:
    trace = get_current_latency_trace()
    if trace is None:
        return
    trace.set_value("retrieval_enabled_channels", safe_str_list(enabled))
    trace.set_value("retrieval_eligible_channels", safe_str_list(eligible))
    trace.set_value("retrieval_channel_candidate_counts", safe_count_dict(counts))


def safe_str_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item) for item in value]


def safe_count_dict(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    counts: dict[str, int] = {}
    for key, item in value.items():
        try:
            counts[str(key)] = int(item)
        except (TypeError, ValueError):
            continue
    return counts
