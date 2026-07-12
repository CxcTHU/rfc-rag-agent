from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import networkx as nx

from app.services.graphrag.graph_search import (
    GraphSearchMatch,
    GraphSearchSummary,
    cap_graph_matches,
    graph_search_matches,
    matched_query_node_ids,
    normalize_relation_focus,
    record_graph_summary,
)
from app.services.graphrag.graph_store import load_graph
from app.services.observability.latency_trace import get_current_latency_trace, latency_timer


@dataclass(frozen=True)
class GraphCandidate:
    chunk_id: int
    score: float
    matched_node_ids: tuple[str, ...]
    hop_count: int
    relation_types: tuple[str, ...] = ()
    relation_evidence: tuple[str, ...] = ()

    @classmethod
    def from_match(cls, match: GraphSearchMatch) -> GraphCandidate:
        return cls(
            chunk_id=match.chunk_id,
            score=match.score,
            matched_node_ids=match.matched_node_ids,
            hop_count=match.hop_count,
            relation_types=match.relation_types,
            relation_evidence=match.relation_evidence,
        )


@dataclass(frozen=True)
class GraphRetrievalOutcome:
    candidates: list[GraphCandidate]
    summary: GraphSearchSummary
    fingerprint: str


class GraphRetriever:
    """Bounded, fail-open Local GraphRAG retriever.

    This class only discovers graph-backed chunk candidates. Fusion, document
    hydration, and final reranking remain responsibilities of the Hybrid
    retrieval runtime.
    """

    def __init__(
        self,
        *,
        graph: nx.MultiDiGraph | None = None,
        graph_path: Path | None = None,
    ) -> None:
        self.graph = graph
        self.graph_path = graph_path

    def retrieve(
        self,
        query: str,
        *,
        max_hops: int,
        max_matches: int,
        relation_focus: str | None = None,
    ) -> GraphRetrievalOutcome:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if max_hops < 1 or max_hops > 2:
            raise ValueError("max_hops must be 1 or 2")
        if max_matches < 0:
            raise ValueError("max_matches must not be negative")

        fingerprint = self.fingerprint()
        summary = GraphSearchSummary(
            available=False,
            fallback=True,
            hop_count=max_hops,
        )
        candidates: list[GraphCandidate] = []
        with latency_timer("graph_search_latency_ms"):
            try:
                graph = self._load_graph()
                matches = graph_search_matches(
                    graph,
                    normalized_query,
                    max_hops=max_hops,
                    relation_focus=normalize_relation_focus(relation_focus),
                )
                capped_matches = cap_graph_matches(matches, max_matches)
                candidates = [GraphCandidate.from_match(match) for match in capped_matches]
                summary = GraphSearchSummary(
                    available=True,
                    fallback=False,
                    matched_entity_count=len(
                        matched_query_node_ids(graph, normalized_query)
                    ),
                    candidate_chunk_count=len(matches),
                    hop_count=max_hops,
                )
            except (OSError, ValueError, RuntimeError) as exc:
                summary = GraphSearchSummary(
                    available=False,
                    fallback=True,
                    error=type(exc).__name__,
                    hop_count=max_hops,
                )

        record_graph_summary(summary)
        trace = get_current_latency_trace()
        if trace is not None:
            trace.set_value("graph_fingerprint", fingerprint)
        return GraphRetrievalOutcome(
            candidates=candidates,
            summary=summary,
            fingerprint=fingerprint,
        )

    def fingerprint(self) -> str:
        if self.graph_path is not None:
            return graph_content_fingerprint(self.graph_path)
        if self.graph is not None:
            return "in-memory"
        return "missing"

    def _load_graph(self) -> nx.MultiDiGraph:
        if self.graph is not None:
            return self.graph
        if self.graph_path is None:
            raise ValueError("graph or graph_path is required")
        return load_graph(self.graph_path)


def graph_content_fingerprint(path: Path) -> str:
    try:
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
    except OSError:
        return "missing"
    return _graph_content_fingerprint_cached(
        str(resolved),
        int(stat.st_mtime_ns),
        int(stat.st_size),
    )


@lru_cache(maxsize=32)
def _graph_content_fingerprint_cached(
    resolved_path: str,
    mtime_ns: int,
    size: int,
) -> str:
    del mtime_ns, size
    try:
        digest = hashlib.sha256()
        with Path(resolved_path).open("rb") as stream:
            for block in iter(lambda: stream.read(64 * 1024), b""):
                digest.update(block)
    except OSError:
        return "missing"
    return digest.hexdigest()[:24]
