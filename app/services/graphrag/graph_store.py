from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx

from app.services.graphrag.schema import (
    GraphEntity,
    GraphExtractionResult,
    GraphRelation,
    normalize_entity_name,
)


GRAPH_SCHEMA_VERSION = "phase53-networkx-v1"


@dataclass(frozen=True)
class GraphStats:
    node_count: int
    edge_count: int
    connected_components: int
    degree_distribution: dict[int, int]
    node_type_counts: dict[str, int]
    edge_type_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "connected_components": self.connected_components,
            "degree_distribution": {
                str(degree): count
                for degree, count in sorted(self.degree_distribution.items())
            },
            "node_type_counts": dict(sorted(self.node_type_counts.items())),
            "edge_type_counts": dict(sorted(self.edge_type_counts.items())),
        }


def entity_node_id(entity: GraphEntity) -> str:
    return f"{entity.type}:{entity.normalized_name}"


def build_knowledge_graph(results: list[GraphExtractionResult]) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph(schema_version=GRAPH_SCHEMA_VERSION)
    name_index: dict[tuple[int | str, str], str] = {}

    for result in results:
        chunk_id = result.chunk_id
        for entity in result.entities:
            node_id = entity_node_id(entity)
            if graph.has_node(node_id):
                attrs = graph.nodes[node_id]
                attrs["chunk_ids"] = sorted(set(attrs.get("chunk_ids", [])) | {chunk_id}, key=str)
                attrs["mentions"] = sorted(set(attrs.get("mentions", [])) | set(entity.mentions))
            else:
                graph.add_node(
                    node_id,
                    name=entity.name,
                    type=entity.type,
                    normalized_name=entity.normalized_name,
                    mentions=sorted(entity.mentions),
                    chunk_ids=[chunk_id],
                )
            name_index[(chunk_id, normalize_entity_name(entity.name))] = node_id

        for relation in result.relations:
            source_id = resolve_relation_node_id(relation.subject, chunk_id, name_index)
            target_id = resolve_relation_node_id(relation.object, chunk_id, name_index)
            if source_id is None or target_id is None:
                continue
            graph.add_edge(
                source_id,
                target_id,
                type=relation.predicate,
                source_chunk_id=relation.source_chunk_id or chunk_id,
                evidence=relation.evidence[:240],
            )

    return graph


def resolve_relation_node_id(
    name: str,
    chunk_id: int | str,
    name_index: dict[tuple[int | str, str], str],
) -> str | None:
    normalized = normalize_entity_name(name)
    if (chunk_id, normalized) in name_index:
        return name_index[(chunk_id, normalized)]
    for (candidate_chunk_id, candidate_name), node_id in name_index.items():
        if candidate_name == normalized:
            return node_id
    return None


def graph_to_json_data(graph: nx.MultiDiGraph) -> dict[str, Any]:
    nodes = [
        {"id": node_id, **sanitize_node_attrs(attrs)}
        for node_id, attrs in graph.nodes(data=True)
    ]
    edges = [
        {
            "source": source,
            "target": target,
            "key": str(key),
            **sanitize_edge_attrs(attrs),
        }
        for source, target, key, attrs in graph.edges(keys=True, data=True)
    ]
    return {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "directed": True,
        "multigraph": True,
        "nodes": sorted(nodes, key=lambda item: item["id"]),
        "edges": sorted(
            edges,
            key=lambda item: (
                item["source"],
                item["target"],
                item.get("type", ""),
                str(item.get("source_chunk_id", "")),
                item["key"],
            ),
        ),
    }


def graph_from_json_data(data: dict[str, Any]) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph(schema_version=str(data.get("schema_version") or GRAPH_SCHEMA_VERSION))
    for node in data.get("nodes") or ():
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        attrs = {key: value for key, value in node.items() if key != "id"}
        graph.add_node(node_id, **attrs)
    for edge in data.get("edges") or ():
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if not source or not target:
            continue
        attrs = {
            key: value
            for key, value in edge.items()
            if key not in {"source", "target", "key"}
        }
        graph.add_edge(source, target, key=str(edge.get("key") or ""), **attrs)
    return graph


def save_graph(graph: nx.MultiDiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(graph_to_json_data(graph), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_graph(path: Path) -> nx.MultiDiGraph:
    return graph_from_json_data(json.loads(path.read_text(encoding="utf-8")))


def graph_stats(graph: nx.MultiDiGraph) -> GraphStats:
    undirected = graph.to_undirected()
    connected_components = nx.number_connected_components(undirected) if graph.number_of_nodes() else 0
    degree_counter = Counter(dict(undirected.degree()).values())
    node_type_counter = Counter(
        str(attrs.get("type") or "Unknown")
        for _, attrs in graph.nodes(data=True)
    )
    edge_type_counter = Counter(
        str(attrs.get("type") or "unknown")
        for _, _, attrs in graph.edges(data=True)
    )
    return GraphStats(
        node_count=graph.number_of_nodes(),
        edge_count=graph.number_of_edges(),
        connected_components=connected_components,
        degree_distribution=dict(degree_counter),
        node_type_counts=dict(node_type_counter),
        edge_type_counts=dict(edge_type_counter),
    )


def sanitize_node_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(attrs.get("name") or ""),
        "type": str(attrs.get("type") or "Unknown"),
        "normalized_name": str(attrs.get("normalized_name") or ""),
        "mentions": sorted(str(item) for item in attrs.get("mentions") or ()),
        "chunk_ids": sorted(attrs.get("chunk_ids") or (), key=str),
    }


def sanitize_edge_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": str(attrs.get("type") or "unknown"),
        "source_chunk_id": attrs.get("source_chunk_id"),
    }
    evidence = str(attrs.get("evidence") or "").strip()
    if evidence:
        data["evidence"] = evidence[:240]
    return data


def load_extraction_results(path: Path) -> list[GraphExtractionResult]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("GraphRAG extraction file must contain a rows list")
    return [
        GraphExtractionResult.from_dict(row)
        for row in rows
        if isinstance(row, dict) and row.get("status", "ok") == "ok"
    ]
