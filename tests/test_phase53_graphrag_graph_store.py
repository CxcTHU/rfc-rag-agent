import json

from app.services.graphrag.graph_store import (
    build_knowledge_graph,
    graph_from_json_data,
    graph_stats,
    graph_to_json_data,
    prune_isolated_nodes_by_type,
)
from app.services.graphrag.schema import GraphEntity, GraphExtractionResult, GraphRelation


def make_result(chunk_id: int) -> GraphExtractionResult:
    return GraphExtractionResult(
        chunk_id=chunk_id,
        document_id=1,
        document_title="RFC graph sample",
        entities=(
            GraphEntity(name="GB/T 50080", type="Standard"),
            GraphEntity(name="rock-filled concrete", type="Material", mentions=("RFC",)),
            GraphEntity(name="compressive strength", type="Parameter"),
            GraphEntity(name="45 MPa", type="Value"),
        ),
        relations=(
            GraphRelation(
                subject="GB/T 50080",
                predicate="standard_defines",
                object="compressive strength",
                source_chunk_id=chunk_id,
            ),
            GraphRelation(
                subject="rock-filled concrete",
                predicate="material_has_property",
                object="compressive strength",
                source_chunk_id=chunk_id,
            ),
            GraphRelation(
                subject="compressive strength",
                predicate="parameter_range",
                object="45 MPa",
                source_chunk_id=chunk_id,
            ),
        ),
    )


def test_build_knowledge_graph_nodes_and_edges_have_required_attrs() -> None:
    graph = build_knowledge_graph([make_result(10)])

    assert graph.number_of_nodes() == 4
    assert graph.number_of_edges() == 3
    for _, attrs in graph.nodes(data=True):
        assert attrs["type"]
        assert attrs["chunk_ids"] == [10]
    for _, _, attrs in graph.edges(data=True):
        assert attrs["type"]
        assert attrs["source_chunk_id"] == 10


def test_graph_json_persistence_round_trip_is_repeatable() -> None:
    graph = build_knowledge_graph([make_result(10), make_result(11)])
    first_data = graph_to_json_data(graph)
    loaded_graph = graph_from_json_data(json.loads(json.dumps(first_data)))
    second_data = graph_to_json_data(loaded_graph)

    assert first_data == second_data
    material_node = next(
        node for node in second_data["nodes"] if node["id"].startswith("Material:")
    )
    assert material_node["chunk_ids"] == [10, 11]


def test_graph_stats_include_components_degree_and_type_counts() -> None:
    graph = build_knowledge_graph([make_result(10)])
    stats = graph_stats(graph).to_dict()

    assert stats["node_count"] == 4
    assert stats["edge_count"] == 3
    assert stats["connected_components"] == 1
    assert stats["node_type_counts"]["Material"] == 1
    assert stats["edge_type_counts"]["parameter_range"] == 1
    assert stats["degree_distribution"]
    assert stats["isolated_node_count"] == 0
    assert stats["largest_connected_component_ratio"] == "1.0000"


def test_graph_store_canonicalizes_standard_and_material_aliases() -> None:
    first = GraphExtractionResult(
        chunk_id=1,
        document_id=1,
        document_title="aliases",
        entities=(
            GraphEntity(name="GB/T50080", type="Standard"),
            GraphEntity(name="RFC", type="Material"),
        ),
        relations=(
            GraphRelation(
                subject="GB/T50080",
                predicate="standard_defines",
                object="RFC",
                source_chunk_id=1,
            ),
        ),
    )
    second = GraphExtractionResult(
        chunk_id=2,
        document_id=1,
        document_title="aliases",
        entities=(
            GraphEntity(name="GBT 50080", type="Standard"),
            GraphEntity(name="rock filled concrete", type="Material"),
        ),
        relations=(
            GraphRelation(
                subject="GBT 50080",
                predicate="standard_defines",
                object="rock filled concrete",
                source_chunk_id=2,
            ),
        ),
    )

    graph = build_knowledge_graph([first, second])

    assert graph.has_node("Standard:gb/t 50080")
    assert graph.has_node("Material:rock-filled concrete")
    assert graph.number_of_nodes() == 2
    material = graph.nodes["Material:rock-filled concrete"]
    assert material["chunk_ids"] == [1, 2]
    assert "RFC" in material["mentions"]
    assert "rock filled concrete" in material["mentions"]
    assert graph.number_of_edges() == 2


def test_graph_store_canonicalizes_chinese_standard_aliases() -> None:
    graph = build_knowledge_graph(
        [
            GraphExtractionResult(
                chunk_id=1,
                document_id=1,
                document_title="aliases",
                entities=(
                    GraphEntity(name="NBT 10077-2024", type="Standard"),
                    GraphEntity(name="DB63T 2086-2022", type="Standard"),
                ),
            ),
            GraphExtractionResult(
                chunk_id=2,
                document_id=1,
                document_title="aliases",
                entities=(
                    GraphEntity(name="NB/T 10077-2024", type="Standard"),
                    GraphEntity(name="DB63/T 2086-2022", type="Standard"),
                ),
            ),
        ]
    )

    assert graph.has_node("Standard:nb/t 10077-2024")
    assert graph.has_node("Standard:db63/t 2086-2022")
    assert graph.number_of_nodes() == 2
    assert graph.nodes["Standard:nb/t 10077-2024"]["chunk_ids"] == [1, 2]


def test_prune_isolated_nodes_by_type_keeps_other_isolates() -> None:
    graph = build_knowledge_graph(
        [
            make_result(10),
            GraphExtractionResult(
                chunk_id=12,
                document_id=1,
                document_title="isolates",
                entities=(
                    GraphEntity(name="0.001 MPa", type="Value"),
                    GraphEntity(name="GB/T 14902", type="Standard"),
                    GraphEntity(name="rockfill", type="Material"),
                ),
                relations=(),
            ),
        ]
    )

    pruned = prune_isolated_nodes_by_type(graph, node_types={"Value"})

    assert pruned == 1
    assert "Value:0.001 mpa" not in graph
    assert "Standard:gb/t 14902" in graph
    assert "Material:rockfill" in graph
