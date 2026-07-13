from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.services.graphrag.graph_store import load_graph
from app.services.graphrag.schema import normalize_entity_name
from app.services.observability.latency_trace import (
    get_current_latency_trace,
    latency_timer,
)
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.hybrid_search import (
    HybridSearchResult,
    HybridSearchService,
    add_results,
    candidate_to_result,
    max_result_score,
)
from app.services.retrieval.keyword_search import KeywordSearchService, source_type_rank
from app.services.retrieval.reranking import ReRankingProvider
from app.services.retrieval.vector_search import VectorSearchService


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9./+-]*|[\u4e00-\u9fff]{2,}")
QUERY_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "about",
        "between",
        "for",
        "from",
        "how",
        "in",
        "is",
        "of",
        "or",
        "the",
        "to",
        "what",
        "which",
        "who",
        "with",
        "write",
    }
)


@dataclass(frozen=True)
class GraphSearchMatch:
    chunk_id: int
    score: float
    matched_node_ids: tuple[str, ...]
    hop_count: int
    relation_types: tuple[str, ...] = ()
    relation_evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class GraphSearchSummary:
    available: bool
    fallback: bool
    error: str = ""
    matched_entity_count: int = 0
    candidate_chunk_count: int = 0
    hop_count: int = 0


@dataclass(frozen=True)
class GraphEnhancedSearchOutcome:
    results: list[HybridSearchResult]
    graph_matches: list[GraphSearchMatch]
    summary: GraphSearchSummary


class GraphEnhancedSearchService:
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        *,
        graph: nx.MultiDiGraph | None = None,
        graph_path: Path | None = None,
        hybrid_service_factory: Callable[[], HybridSearchService] | None = None,
        graph_boost: float = 0.25,
        max_graph_matches: int = 200,
        hybrid_candidate_k: int | None = None,
        multi_channel_candidate_k: int | None = None,
        final_reranking_provider: ReRankingProvider | None = None,
        final_rerank_candidate_k: int | None = None,
        relation_focus: str | None = None,
        final_graph_candidate_quota: int = 0,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.graph = graph
        self.graph_path = graph_path
        self.hybrid_service_factory = hybrid_service_factory
        self.graph_boost = graph_boost
        self.max_graph_matches = max_graph_matches
        self.hybrid_candidate_k = hybrid_candidate_k
        self.multi_channel_candidate_k = multi_channel_candidate_k
        self.final_reranking_provider = final_reranking_provider
        self.final_rerank_candidate_k = final_rerank_candidate_k
        self.relation_focus = normalize_relation_focus(relation_focus)
        self.final_graph_candidate_quota = final_graph_candidate_quota

    def search(self, query: str, top_k: int = 5, max_hops: int = 2) -> GraphEnhancedSearchOutcome:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if max_hops < 1 or max_hops > 2:
            raise ValueError("max_hops must be 1 or 2")

        from app.services.graphrag.retriever import GraphRetriever

        outcome = GraphRetriever(
            graph=self.graph,
            graph_path=self.graph_path,
        ).retrieve(
            normalized_query,
            max_hops=max_hops,
            max_matches=self.max_graph_matches,
            relation_focus=self.relation_focus,
        )
        graph_matches = [
            GraphSearchMatch(
                chunk_id=candidate.chunk_id,
                score=candidate.score,
                matched_node_ids=candidate.matched_node_ids,
                hop_count=candidate.hop_count,
                relation_types=candidate.relation_types,
                relation_evidence=candidate.relation_evidence,
            )
            for candidate in outcome.candidates
        ]
        graph_summary = outcome.summary

        hybrid_results = self._hybrid_search(
            normalized_query,
            top_k=max(top_k, self.hybrid_candidate_k or top_k),
        )
        if not graph_matches:
            if self.final_reranking_provider is not None:
                hybrid_results = rerank_fused_results(
                    query=normalized_query,
                    results=hybrid_results,
                    provider=self.final_reranking_provider,
                    top_k=top_k,
                    candidate_k=self.final_rerank_candidate_k,
                    relation_types_by_chunk={},
                    relation_evidence_by_chunk={},
                    graph_priority_chunk_ids=(),
                    graph_candidate_quota=0,
                )
            else:
                hybrid_results = hybrid_results[:top_k]
            return GraphEnhancedSearchOutcome(
                results=hybrid_results,
                graph_matches=[],
                summary=graph_summary,
            )

        capped_graph_matches = cap_graph_matches(graph_matches, self.max_graph_matches)
        graph_results = graph_results_from_matches(self.db, capped_graph_matches)
        fused = fuse_graph_and_hybrid_results(
            hybrid_results=hybrid_results,
            graph_results=graph_results,
            graph_matches=capped_graph_matches,
            top_k=max(top_k, len(hybrid_results) + len(graph_results)),
            graph_boost=self.graph_boost,
        )
        if self.final_reranking_provider is not None:
            fused = rerank_fused_results(
                query=normalized_query,
                results=fused,
                provider=self.final_reranking_provider,
                top_k=top_k,
                candidate_k=self.final_rerank_candidate_k,
                relation_types_by_chunk={
                    match.chunk_id: match.relation_types
                    for match in capped_graph_matches
                },
                relation_evidence_by_chunk={
                    match.chunk_id: match.relation_evidence
                    for match in capped_graph_matches
                },
                graph_priority_chunk_ids=tuple(match.chunk_id for match in capped_graph_matches),
                graph_candidate_quota=self.final_graph_candidate_quota,
            )
        else:
            fused = fused[:top_k]
        return GraphEnhancedSearchOutcome(
            results=fused,
            graph_matches=capped_graph_matches,
            summary=graph_summary,
        )

    def _load_graph(self) -> nx.MultiDiGraph:
        if self.graph is not None:
            return self.graph
        if self.graph_path is None:
            raise ValueError("graph or graph_path is required")
        return load_graph(self.graph_path)

    def _hybrid_search(self, query: str, *, top_k: int) -> list[HybridSearchResult]:
        if self.multi_channel_candidate_k is not None:
            return self._multi_channel_hybrid_search(
                query,
                per_channel_k=max(top_k, self.multi_channel_candidate_k),
            )
        if self.hybrid_service_factory is not None:
            return self.hybrid_service_factory().search(query=query, top_k=top_k)
        return HybridSearchService(self.db, self.embedding_provider).search(query=query, top_k=top_k)

    def _multi_channel_hybrid_search(self, query: str, *, per_channel_k: int) -> list[HybridSearchResult]:
        keyword_results = KeywordSearchService(self.db).search(query, top_k=per_channel_k)
        vector_results = VectorSearchService(self.db, self.embedding_provider).search(query, top_k=per_channel_k)
        candidates = {}
        add_results(candidates, keyword_results, "keyword", max_result_score(keyword_results))
        add_results(candidates, vector_results, "vector", max_result_score(vector_results))
        scoring_service = HybridSearchService(
            self.db,
            self.embedding_provider,
            reranking_enabled=False,
        )
        hybrid_results = [candidate_to_result(candidate, scoring_service) for candidate in candidates.values()]
        return sorted(
            hybrid_results,
            key=lambda item: (
                -item.score,
                source_type_rank(item.source_type),
                item.document_id,
                item.chunk_index,
            ),
        )


def graph_search_matches(
    graph: nx.MultiDiGraph,
    query: str,
    *,
    max_hops: int = 2,
    relation_focus: str | None = None,
    max_matches: int | None = None,
) -> list[GraphSearchMatch]:
    matches, _candidate_count = graph_search_matches_with_count(
        graph,
        query,
        max_hops=max_hops,
        relation_focus=relation_focus,
        max_matches=max_matches,
    )
    return matches


def graph_search_matches_with_count(
    graph: nx.MultiDiGraph,
    query: str,
    *,
    max_hops: int = 2,
    relation_focus: str | None = None,
    max_matches: int | None = None,
) -> tuple[list[GraphSearchMatch], int]:
    """Return bounded matches plus the count discovered before the output cap."""
    anchors = matched_query_node_ids(graph, query)
    if not anchors:
        return [], 0
    normalized_relation_focus = normalize_relation_focus(relation_focus)
    chunk_scores: dict[int, float] = defaultdict(float)
    chunk_nodes: dict[int, set[str]] = defaultdict(set)
    chunk_hops: dict[int, int] = {}

    distances = bounded_undirected_distances(graph, anchors, max_hops=max_hops)
    for node_id, distance in distances.items():
        node_score = 1.0 / (1.0 + float(distance))
        if not normalized_relation_focus:
            for chunk_id in safe_ints(graph.nodes[node_id].get("chunk_ids") or ()):
                chunk_scores[chunk_id] += node_score
                if len(chunk_nodes[chunk_id]) < 8:
                    chunk_nodes[chunk_id].add(node_id)
                chunk_hops[chunk_id] = min(chunk_hops.get(chunk_id, max_hops), int(distance))
        for _, _target_id, attrs in graph.edges(node_id, data=True):
            relation_type = str(attrs.get("type") or "")
            if normalized_relation_focus and relation_type != normalized_relation_focus:
                continue
            chunk_id = safe_int(attrs.get("source_chunk_id"))
            if chunk_id is None:
                continue
            chunk_scores[chunk_id] += node_score * 0.5
            if len(chunk_nodes[chunk_id]) < 8:
                chunk_nodes[chunk_id].add(node_id)
            chunk_hops[chunk_id] = min(chunk_hops.get(chunk_id, max_hops), int(distance))

    ranked_chunk_ids = [
        chunk_id
        for chunk_id, _score in sorted(
            chunk_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    candidate_count = len(ranked_chunk_ids)
    if max_matches is not None:
        ranked_chunk_ids = ranked_chunk_ids[: max(0, max_matches)]
    selected_chunk_ids = set(ranked_chunk_ids)
    chunk_relation_types: dict[int, set[str]] = defaultdict(set)
    chunk_relation_evidence: dict[int, set[str]] = defaultdict(set)
    for node_id in distances:
        for _, target_id, attrs in graph.edges(node_id, data=True):
            chunk_id = safe_int(attrs.get("source_chunk_id"))
            if chunk_id not in selected_chunk_ids:
                continue
            relation_type = str(attrs.get("type") or "")
            if normalized_relation_focus and relation_type != normalized_relation_focus:
                continue
            if relation_type:
                chunk_relation_types[chunk_id].add(relation_type)
            if len(chunk_relation_evidence[chunk_id]) >= 3:
                continue
            edge_text = graph_edge_evidence(graph, node_id, str(target_id), attrs)
            if edge_text:
                chunk_relation_evidence[chunk_id].add(edge_text)

    return (
        [
            GraphSearchMatch(
                chunk_id=chunk_id,
                score=round(chunk_scores[chunk_id], 6),
                matched_node_ids=tuple(sorted(chunk_nodes[chunk_id])),
                hop_count=chunk_hops.get(chunk_id, max_hops),
                relation_types=tuple(sorted(chunk_relation_types.get(chunk_id, ()))),
                relation_evidence=tuple(sorted(chunk_relation_evidence.get(chunk_id, ()))[:3]),
            )
            for chunk_id in ranked_chunk_ids
        ],
        candidate_count,
    )


def bounded_undirected_distances(
    graph: nx.MultiDiGraph,
    anchors: list[str],
    *,
    max_hops: int,
) -> dict[str, int]:
    """Traverse local neighbors without constructing a full undirected graph copy."""
    distances = {anchor: 0 for anchor in anchors}
    frontier = list(distances)
    for distance in range(1, max_hops + 1):
        next_frontier: list[str] = []
        for node_id in frontier:
            for neighbor in (*graph.successors(node_id), *graph.predecessors(node_id)):
                neighbor_id = str(neighbor)
                if neighbor_id in distances:
                    continue
                distances[neighbor_id] = distance
                next_frontier.append(neighbor_id)
        if not next_frontier:
            break
        frontier = next_frontier
    return distances


def graph_edge_evidence(graph: nx.MultiDiGraph, node_id: str, target_id: str, attrs: dict[str, Any]) -> str:
    relation_type = str(attrs.get("type") or "")
    if not relation_type:
        return ""
    source_name = str(graph.nodes[node_id].get("name") or node_id)
    target_name = str(graph.nodes[target_id].get("name") or target_id)
    evidence = str(attrs.get("evidence") or "")
    relation = f"{source_name} --{relation_type}--> {target_name}".strip()
    if evidence:
        relation = f"{relation}; evidence: {evidence[:120]}"
    return relation[:240]


def normalize_relation_focus(relation_focus: str | None) -> str | None:
    value = (relation_focus or "").strip()
    if not value or value == "none":
        return None
    return value


def cap_graph_matches(matches: list[GraphSearchMatch], limit: int) -> list[GraphSearchMatch]:
    if limit <= 0:
        return []
    return matches[:limit]


def matched_query_node_ids(graph: nx.MultiDiGraph, query: str) -> list[str]:
    normalized_query = normalize_query_text(query)
    query_tokens = set(query_terms(query))
    matches: list[str] = []
    for node_id, attrs in graph.nodes(data=True):
        candidates = [
            str(attrs.get("name") or ""),
            str(attrs.get("normalized_name") or ""),
            *[str(item) for item in attrs.get("mentions") or ()],
        ]
        if any(candidate_matches_query(candidate, normalized_query, query_tokens) for candidate in candidates):
            matches.append(str(node_id))
    return sorted(set(matches))


def candidate_matches_query(candidate: str, normalized_query: str, query_tokens: set[str]) -> bool:
    normalized_candidate = normalize_query_text(candidate)
    if not normalized_candidate or not is_meaningful_query_candidate(normalized_candidate):
        return False
    if standard_candidate_matches_query(normalized_candidate, normalized_query):
        return True
    candidate_tokens = set(query_terms(candidate))
    if is_short_ascii_query_candidate(normalized_candidate):
        return bool(candidate_tokens and candidate_tokens <= query_tokens)
    if normalized_candidate in normalized_query:
        return True
    return bool(candidate_tokens and candidate_tokens <= query_tokens)


def standard_candidate_matches_query(normalized_candidate: str, normalized_query: str) -> bool:
    match = re.search(
        r"\b(?P<prefix>gb/t|gb|dl/t|dl|nb/t|db\d+/t|sl/t|sl|astm|aci)\s+"
        r"(?P<number>\d{2,6})(?:\s+(?P<year>\d{4}))?\b",
        normalized_candidate,
    )
    if not match:
        return False
    prefix = match.group("prefix")
    number = match.group("number")
    year = match.group("year")
    without_year = f"{prefix} {number}"
    compact_without_year = without_year.replace("/", "").replace(" ", "")
    compact_query = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", normalized_query)
    if without_year in normalized_query or compact_without_year in compact_query:
        return True
    if year:
        with_year = f"{without_year} {year}"
        compact_with_year = with_year.replace("/", "").replace(" ", "")
        return with_year in normalized_query or compact_with_year in compact_query
    return False


def is_meaningful_query_candidate(normalized_candidate: str) -> bool:
    compact = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", normalized_candidate)
    if len(compact) <= 1 and compact.isascii():
        return False
    return True


def is_short_ascii_query_candidate(normalized_candidate: str) -> bool:
    compact = re.sub(r"[^0-9a-zA-Z]+", "", normalized_candidate)
    return bool(compact and compact.isascii() and len(compact) <= 2)


def normalize_query_text(text: str) -> str:
    return normalize_entity_name(text.replace("-", " "))


def query_terms(text: str) -> list[str]:
    return [
        term
        for match in TOKEN_RE.finditer(text)
        if len(term := normalize_query_text(match.group(0))) >= 2
        and term not in QUERY_STOPWORDS
    ]


def graph_results_from_matches(
    db: Session,
    matches: list[GraphSearchMatch] | list[Any],
) -> list[HybridSearchResult]:
    chunk_ids = [match.chunk_id for match in matches]
    if not chunk_ids:
        return []
    score_by_chunk = {match.chunk_id: match.score for match in matches}
    match_by_chunk = {match.chunk_id: match for match in matches}
    statement = (
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(chunk_ids))
    )
    rows = db.execute(statement).all()
    by_id = {chunk.id: (chunk, document) for chunk, document in rows}
    results: list[HybridSearchResult] = []
    max_score = max(score_by_chunk.values(), default=1.0)
    for chunk_id in chunk_ids:
        row = by_id.get(chunk_id)
        if row is None:
            continue
        chunk, document = row
        match = match_by_chunk[chunk_id]
        score = score_by_chunk[chunk_id] / max(max_score, 1e-9)
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
                score=round(score, 6),
                keyword_score=0.0,
                vector_score=0.0,
                chunk_type=chunk.chunk_type,
                source_image_path=chunk.source_image_path,
                caption=chunk.caption,
                page_number=chunk.page_number,
                matched_node_ids=tuple(match.matched_node_ids),
                graph_hop_count=int(match.hop_count),
                relation_types=tuple(match.relation_types),
                relation_evidence=tuple(match.relation_evidence),
            )
        )
    return results


def fuse_graph_and_hybrid_results(
    *,
    hybrid_results: list[HybridSearchResult],
    graph_results: list[HybridSearchResult],
    graph_matches: list[GraphSearchMatch],
    top_k: int,
    graph_boost: float = 0.25,
) -> list[HybridSearchResult]:
    graph_score_by_chunk = {match.chunk_id: match.score for match in graph_matches}
    max_graph_score = max(graph_score_by_chunk.values(), default=1.0)
    merged: dict[int, HybridSearchResult] = {}

    for result in hybrid_results:
        graph_score = graph_score_by_chunk.get(result.chunk_id, 0.0) / max(max_graph_score, 1e-9)
        boosted_score = min(1.0, result.score + graph_score * graph_boost)
        merged[result.chunk_id] = replace(result, score=round(boosted_score, 6))

    for result in graph_results:
        if result.chunk_id in merged:
            continue
        graph_score = graph_score_by_chunk.get(result.chunk_id, result.score) / max(max_graph_score, 1e-9)
        merged[result.chunk_id] = replace(result, score=round(graph_score * graph_boost, 6))

    return sorted(
        merged.values(),
        key=lambda item: (-item.score, item.document_id, item.chunk_index, item.chunk_id),
    )[:top_k]


def rerank_fused_results(
    *,
    query: str,
    results: list[HybridSearchResult],
    provider: ReRankingProvider,
    top_k: int,
    candidate_k: int | None = None,
    relation_types_by_chunk: dict[int, tuple[str, ...]] | None = None,
    relation_evidence_by_chunk: dict[int, tuple[str, ...]] | None = None,
    graph_priority_chunk_ids: tuple[int, ...] = (),
    graph_candidate_quota: int = 0,
) -> list[HybridSearchResult]:
    if not results:
        return []
    candidates = select_final_rerank_candidates(
        results,
        max_candidates=max(top_k, candidate_k or top_k),
        graph_priority_chunk_ids=graph_priority_chunk_ids,
        graph_candidate_quota=graph_candidate_quota,
    )
    relation_types_by_chunk = relation_types_by_chunk or {}
    relation_evidence_by_chunk = relation_evidence_by_chunk or {}
    rerank_texts = [
        graph_augmented_candidate_text(
            result,
            relation_types=relation_types_by_chunk.get(result.chunk_id, ()),
            relation_evidence=relation_evidence_by_chunk.get(result.chunk_id, ()),
        )
        for result in candidates
    ]
    trace = get_current_latency_trace()
    if trace is not None:
        trace.set_value("graph_final_reranking_provider", provider.provider_name)
        trace.set_value("graph_final_reranking_model", provider.model_name)
        trace.set_value("graph_final_reranking_fallback", False)
        trace.set_value("graph_final_reranking_error", "")
    try:
        with latency_timer("graph_final_rerank_latency_ms"):
            reranked = provider.rerank(
                query=query,
                candidates=rerank_texts,
                top_k=top_k,
            )
    except Exception:
        if trace is not None:
            trace.set_value("graph_final_reranking_fallback", True)
            trace.set_value("graph_final_reranking_error", "runtime_error")
        return results[:top_k]
    return [candidates[item.index] for item in reranked]


def select_final_rerank_candidates(
    results: list[HybridSearchResult],
    *,
    max_candidates: int,
    graph_priority_chunk_ids: tuple[int, ...] = (),
    graph_candidate_quota: int = 0,
) -> list[HybridSearchResult]:
    if max_candidates <= 0:
        return []
    by_chunk = {result.chunk_id: result for result in results}
    selected: list[HybridSearchResult] = []
    seen: set[int] = set()
    if graph_candidate_quota > 0:
        for chunk_id in graph_priority_chunk_ids:
            result = by_chunk.get(chunk_id)
            if result is None or result.chunk_id in seen:
                continue
            selected.append(result)
            seen.add(result.chunk_id)
            if len(selected) >= min(graph_candidate_quota, max_candidates):
                break
    for result in results:
        if result.chunk_id in seen:
            continue
        selected.append(result)
        seen.add(result.chunk_id)
        if len(selected) >= max_candidates:
            break
    return selected


def graph_augmented_candidate_text(
    result: HybridSearchResult,
    *,
    relation_types: tuple[str, ...] = (),
    relation_evidence: tuple[str, ...] = (),
) -> str:
    if not relation_types and not relation_evidence:
        return result.content
    relation_label = ", ".join(str(item) for item in relation_types)
    relation_lines = "\n".join(f"Graph relation: {item}" for item in relation_evidence)
    heading = f" heading={result.heading_path}" if result.heading_path else ""
    return (
        f"Graph relation types: {relation_label}.{heading}\n"
        f"{relation_lines}\n"
        f"Document title: {result.document_title}\n"
        f"{result.content}"
    )


def record_graph_summary(summary: GraphSearchSummary) -> None:
    trace = get_current_latency_trace()
    if trace is None:
        return
    trace.set_value("graph_search_available", summary.available)
    trace.set_value("graph_search_fallback", summary.fallback)
    trace.set_value("graph_search_error", summary.error)
    trace.set_value("graph_entity_count", summary.matched_entity_count)
    trace.set_value("graph_candidate_chunk_count", summary.candidate_chunk_count)
    trace.set_value("graph_hop_count", summary.hop_count)


def safe_ints(values: Any) -> list[int]:
    ints: list[int] = []
    for value in values:
        parsed = safe_int(value)
        if parsed is not None:
            ints.append(parsed)
    return ints


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
