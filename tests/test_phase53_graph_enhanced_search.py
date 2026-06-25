from sqlalchemy.orm import Session

from app.db.models import Base, Chunk, Document
from app.db.session import create_database_engine
from app.services.graphrag.graph_search import (
    GraphEnhancedSearchService,
    cap_graph_matches,
    fuse_graph_and_hybrid_results,
    GraphSearchMatch,
    graph_augmented_candidate_text,
    graph_search_matches,
    matched_query_node_ids,
    select_final_rerank_candidates,
)
from app.services.graphrag.graph_store import build_knowledge_graph
from app.services.graphrag.schema import GraphEntity, GraphExtractionResult, GraphRelation
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.hybrid_search import HybridSearchResult
from app.services.retrieval.reranking import ReRankResult


class EmptyEmbeddingProvider:
    provider_name = "empty"
    model_name = "empty"
    dimension = 3

    def embed(self, texts):
        return [[0.0, 0.0, 0.0] for _ in texts]


class FakeHybridService:
    def __init__(self, results):
        self.results = results
        self.called = False

    def search(self, query: str, top_k: int):
        self.called = True
        return self.results[:top_k]


class FakeFinalReranker:
    provider_name = "fake-final"
    model_name = "fake-final-v1"

    def rerank(self, query: str, candidates, top_k: int = 5):
        scored = []
        for index, candidate in enumerate(candidates):
            score = 10.0 if "45 MPa" in candidate else 1.0
            scored.append(ReRankResult(index=index, score=score, content=candidate))
        return sorted(scored, key=lambda item: (-item.score, item.index))[:top_k]


def sample_graph():
    return build_knowledge_graph(
        [
            GraphExtractionResult(
                chunk_id=1,
                document_id=1,
                document_title="RFC graph",
                entities=(
                    GraphEntity(name="rock-filled concrete", type="Material", mentions=("RFC",)),
                    GraphEntity(name="compressive strength", type="Parameter"),
                    GraphEntity(name="45 MPa", type="Value"),
                ),
                relations=(
                    GraphRelation(
                        subject="rock-filled concrete",
                        predicate="material_has_property",
                        object="compressive strength",
                        source_chunk_id=1,
                    ),
                    GraphRelation(
                        subject="compressive strength",
                        predicate="parameter_range",
                        object="45 MPa",
                        source_chunk_id=2,
                    ),
                ),
            )
        ]
    )


def hybrid_result(chunk_id: int, score: float) -> HybridSearchResult:
    return HybridSearchResult(
        document_id=1,
        document_title="Hybrid doc",
        source_type="local_file",
        source_path=None,
        file_name="doc.pdf",
        chunk_id=chunk_id,
        chunk_index=chunk_id,
        content=f"chunk {chunk_id}",
        heading_path=None,
        score=score,
        keyword_score=score,
        vector_score=0.0,
    )


def seed_chunks(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'graph-search.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        document = Document(
            title="Graph doc",
            file_name="graph.pdf",
            file_extension=".pdf",
            content_hash="phase53-graph-search",
            raw_path="/tmp/graph.pdf",
        )
        db.add(document)
        db.flush()
        db.add_all(
            [
                Chunk(
                    id=1,
                    document_id=document.id,
                    chunk_index=0,
                    content="Rock-filled concrete compressive strength.",
                    char_count=42,
                ),
                Chunk(
                    id=2,
                    document_id=document.id,
                    chunk_index=1,
                    content="45 MPa value.",
                    char_count=12,
                ),
            ]
        )
        db.commit()
    return engine


def test_graph_search_traverses_one_to_two_hops_and_collects_chunks() -> None:
    matches = graph_search_matches(sample_graph(), "RFC compressive strength", max_hops=2)

    assert [match.chunk_id for match in matches] == [1, 2]
    assert matches[0].score > matches[1].score
    assert matches[1].hop_count <= 2


def test_graph_search_relation_focus_keeps_matching_relation_chunks_only() -> None:
    matches = graph_search_matches(
        sample_graph(),
        "RFC compressive strength",
        max_hops=2,
        relation_focus="parameter_range",
    )

    assert [match.chunk_id for match in matches] == [2]
    assert matches[0].relation_types == ("parameter_range",)
    assert "parameter_range" in matches[0].relation_evidence[0]


def test_graph_enhanced_search_fuses_graph_chunks_with_hybrid_results(tmp_path) -> None:
    engine = seed_chunks(tmp_path)
    fake_hybrid = FakeHybridService([hybrid_result(99, 0.7)])
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        with Session(engine) as db:
            outcome = GraphEnhancedSearchService(
                db,
                EmptyEmbeddingProvider(),
                graph=sample_graph(),
                hybrid_service_factory=lambda: fake_hybrid,
            ).search("RFC compressive strength", top_k=3)
    finally:
        reset_current_latency_trace(token)

    chunk_ids = [result.chunk_id for result in outcome.results]
    assert fake_hybrid.called
    assert chunk_ids == [99, 1, 2]
    assert outcome.summary.available is True
    assert trace.values["graph_search_available"] is True
    assert trace.values["graph_candidate_chunk_count"] == 2


def test_graph_enhanced_search_fail_opens_to_hybrid_when_graph_missing(tmp_path) -> None:
    engine = seed_chunks(tmp_path)
    fake_hybrid = FakeHybridService([hybrid_result(99, 0.7)])
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        with Session(engine) as db:
            outcome = GraphEnhancedSearchService(
                db,
                EmptyEmbeddingProvider(),
                graph_path=tmp_path / "missing.json",
                hybrid_service_factory=lambda: fake_hybrid,
            ).search("RFC compressive strength", top_k=3)
    finally:
        reset_current_latency_trace(token)

    assert [result.chunk_id for result in outcome.results] == [99]
    assert outcome.summary.fallback is True
    assert trace.values["graph_search_fallback"] is True
    assert trace.values["graph_search_error"] == "FileNotFoundError"


def test_fusion_deduplicates_and_boosts_existing_hybrid_result() -> None:
    fused = fuse_graph_and_hybrid_results(
        hybrid_results=[hybrid_result(1, 0.5), hybrid_result(3, 0.4)],
        graph_results=[hybrid_result(1, 1.0), hybrid_result(2, 0.8)],
        graph_matches=[],
        top_k=3,
    )

    assert [result.chunk_id for result in fused] == [1, 3, 2]
    assert len({result.chunk_id for result in fused}) == len(fused)


def test_cap_graph_matches_keeps_highest_scored_prefix() -> None:
    matches = [
        GraphSearchMatch(chunk_id=1, score=3.0, matched_node_ids=("a",), hop_count=0),
        GraphSearchMatch(chunk_id=2, score=2.0, matched_node_ids=("b",), hop_count=1),
        GraphSearchMatch(chunk_id=3, score=1.0, matched_node_ids=("c",), hop_count=2),
    ]

    capped = cap_graph_matches(matches, 2)

    assert [match.chunk_id for match in capped] == [1, 2]


def test_query_matching_ignores_single_letter_ascii_entities() -> None:
    graph = build_knowledge_graph(
        [
            GraphExtractionResult(
                chunk_id=1,
                document_id=1,
                document_title="single letters",
                entities=(
                    GraphEntity(name="W", type="Parameter"),
                    GraphEntity(name="CH", type="Parameter"),
                    GraphEntity(name="GB/T 50080", type="Standard"),
                ),
                relations=(),
            )
        ]
    )

    assert matched_query_node_ids(graph, "Who won the latest football championship?") == []
    assert matched_query_node_ids(graph, "CH parameter") == ["Parameter:ch"]
    assert matched_query_node_ids(graph, "GB/T 50080 concrete testing")


def test_query_matching_matches_standard_without_year_suffix() -> None:
    graph = build_knowledge_graph(
        [
            GraphExtractionResult(
                chunk_id=1,
                document_id=1,
                document_title="local standard",
                entities=(GraphEntity(name="DB63/T 2086-2022", type="Standard"),),
                relations=(),
            )
        ]
    )

    assert matched_query_node_ids(graph, "DB63/T 2086 construction quality") == [
        "Standard:db63/t 2086-2022"
    ]


def test_query_matching_ignores_stopword_only_value_match() -> None:
    graph = build_knowledge_graph(
        [
            GraphExtractionResult(
                chunk_id=1,
                document_id=1,
                document_title="stopwords",
                entities=(
                    GraphEntity(name="about 6 C", type="Value"),
                    GraphEntity(name="summer temperature", type="Parameter"),
                ),
                relations=(),
            )
        ]
    )

    assert matched_query_node_ids(graph, "Write a poem about summer beaches.") == []
    assert matched_query_node_ids(graph, "summer temperature") == ["Parameter:summer temperature"]


def test_graph_enhanced_search_caps_graph_matches_after_summary(tmp_path) -> None:
    engine = seed_chunks(tmp_path)
    fake_hybrid = FakeHybridService([])
    with Session(engine) as db:
        outcome = GraphEnhancedSearchService(
            db,
            EmptyEmbeddingProvider(),
            graph=sample_graph(),
            hybrid_service_factory=lambda: fake_hybrid,
            max_graph_matches=1,
        ).search("RFC compressive strength", top_k=3)

    assert outcome.summary.candidate_chunk_count == 2
    assert len(outcome.graph_matches) == 1


def test_graph_enhanced_search_can_rerank_after_graph_fusion(tmp_path) -> None:
    engine = seed_chunks(tmp_path)
    fake_hybrid = FakeHybridService([hybrid_result(99, 0.9)])
    with Session(engine) as db:
        outcome = GraphEnhancedSearchService(
            db,
            EmptyEmbeddingProvider(),
            graph=sample_graph(),
            hybrid_service_factory=lambda: fake_hybrid,
            final_reranking_provider=FakeFinalReranker(),
        ).search("RFC compressive strength", top_k=3)

    assert [result.chunk_id for result in outcome.results] == [2, 99, 1]


def test_final_rerank_candidate_selection_reserves_graph_quota() -> None:
    results = [hybrid_result(chunk_id, 1.0 / chunk_id) for chunk_id in range(1, 7)]

    selected = select_final_rerank_candidates(
        results,
        max_candidates=4,
        graph_priority_chunk_ids=(6, 5, 4),
        graph_candidate_quota=2,
    )

    assert [result.chunk_id for result in selected] == [6, 5, 1, 2]


def test_graph_augmented_candidate_text_adds_relation_hint_only_for_graph_candidates() -> None:
    result = hybrid_result(2, 0.3)

    augmented = graph_augmented_candidate_text(
        result,
        relation_types=("parameter_range",),
        relation_evidence=("compressive strength --parameter_range--> 45 MPa",),
    )
    plain = graph_augmented_candidate_text(result)

    assert augmented.startswith("Graph relation types: parameter_range.")
    assert "Graph relation: compressive strength --parameter_range--> 45 MPa" in augmented
    assert "chunk 2" in augmented
    assert plain == "chunk 2"
