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
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9./+-]*|[\u4e00-\u9fff]{2,}")


@dataclass(frozen=True)
class GraphSearchMatch:
    chunk_id: int
    score: float
    matched_node_ids: tuple[str, ...]
    hop_count: int


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
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.graph = graph
        self.graph_path = graph_path
        self.hybrid_service_factory = hybrid_service_factory
        self.graph_boost = graph_boost

    def search(self, query: str, top_k: int = 5, max_hops: int = 2) -> GraphEnhancedSearchOutcome:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if max_hops < 1 or max_hops > 2:
            raise ValueError("max_hops must be 1 or 2")

        graph_matches: list[GraphSearchMatch] = []
        graph_summary = GraphSearchSummary(available=False, fallback=True, hop_count=max_hops)
        with latency_timer("graph_search_latency_ms"):
            try:
                graph = self._load_graph()
                graph_matches = graph_search_matches(graph, normalized_query, max_hops=max_hops)
                graph_summary = GraphSearchSummary(
                    available=True,
                    fallback=False,
                    matched_entity_count=len(matched_query_node_ids(graph, normalized_query)),
                    candidate_chunk_count=len(graph_matches),
                    hop_count=max_hops,
                )
            except (OSError, ValueError, RuntimeError) as exc:
                graph_summary = GraphSearchSummary(
                    available=False,
                    fallback=True,
                    error=type(exc).__name__,
                    hop_count=max_hops,
                )
        record_graph_summary(graph_summary)

        hybrid_results = self._hybrid_search(normalized_query, top_k=top_k)
        if not graph_matches:
            return GraphEnhancedSearchOutcome(
                results=hybrid_results,
                graph_matches=[],
                summary=graph_summary,
            )

        graph_results = graph_results_from_matches(self.db, graph_matches)
        fused = fuse_graph_and_hybrid_results(
            hybrid_results=hybrid_results,
            graph_results=graph_results,
            graph_matches=graph_matches,
            top_k=top_k,
            graph_boost=self.graph_boost,
        )
        return GraphEnhancedSearchOutcome(
            results=fused,
            graph_matches=graph_matches,
            summary=graph_summary,
        )

    def _load_graph(self) -> nx.MultiDiGraph:
        if self.graph is not None:
            return self.graph
        if self.graph_path is None:
            raise ValueError("graph or graph_path is required")
        return load_graph(self.graph_path)

    def _hybrid_search(self, query: str, *, top_k: int) -> list[HybridSearchResult]:
        if self.hybrid_service_factory is not None:
            return self.hybrid_service_factory().search(query=query, top_k=top_k)
        return HybridSearchService(self.db, self.embedding_provider).search(query=query, top_k=top_k)


def graph_search_matches(
    graph: nx.MultiDiGraph,
    query: str,
    *,
    max_hops: int = 2,
) -> list[GraphSearchMatch]:
    anchors = matched_query_node_ids(graph, query)
    if not anchors:
        return []
    undirected = graph.to_undirected()
    chunk_scores: dict[int, float] = defaultdict(float)
    chunk_nodes: dict[int, set[str]] = defaultdict(set)
    chunk_hops: dict[int, int] = {}

    for anchor in anchors:
        path_lengths = nx.single_source_shortest_path_length(
            undirected,
            anchor,
            cutoff=max_hops,
        )
        for node_id, distance in path_lengths.items():
            node_score = 1.0 / (1.0 + float(distance))
            for chunk_id in safe_ints(graph.nodes[node_id].get("chunk_ids") or ()):
                chunk_scores[chunk_id] += node_score
                chunk_nodes[chunk_id].add(node_id)
                chunk_hops[chunk_id] = min(chunk_hops.get(chunk_id, max_hops), int(distance))
            for _, _, attrs in graph.edges(node_id, data=True):
                chunk_id = safe_int(attrs.get("source_chunk_id"))
                if chunk_id is None:
                    continue
                chunk_scores[chunk_id] += node_score * 0.5
                chunk_nodes[chunk_id].add(node_id)
                chunk_hops[chunk_id] = min(chunk_hops.get(chunk_id, max_hops), int(distance))

    return [
        GraphSearchMatch(
            chunk_id=chunk_id,
            score=round(score, 6),
            matched_node_ids=tuple(sorted(chunk_nodes[chunk_id])),
            hop_count=chunk_hops.get(chunk_id, max_hops),
        )
        for chunk_id, score in sorted(
            chunk_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


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
    if not normalized_candidate:
        return False
    if normalized_candidate in normalized_query:
        return True
    candidate_tokens = set(query_terms(candidate))
    return bool(candidate_tokens and candidate_tokens <= query_tokens)


def normalize_query_text(text: str) -> str:
    return normalize_entity_name(text.replace("-", " "))


def query_terms(text: str) -> list[str]:
    return [
        normalize_query_text(match.group(0))
        for match in TOKEN_RE.finditer(text)
        if len(normalize_query_text(match.group(0))) >= 2
    ]


def graph_results_from_matches(
    db: Session,
    matches: list[GraphSearchMatch],
) -> list[HybridSearchResult]:
    chunk_ids = [match.chunk_id for match in matches]
    if not chunk_ids:
        return []
    score_by_chunk = {match.chunk_id: match.score for match in matches}
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
