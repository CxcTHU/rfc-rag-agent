from sqlalchemy.orm import Session

from app.db.models import Base, Chunk, Document
from app.db.session import create_database_engine
from app.services.graphrag.graph_search import (
    GraphEnhancedSearchService,
    fuse_graph_and_hybrid_results,
    graph_search_matches,
)
from app.services.graphrag.graph_store import build_knowledge_graph
from app.services.graphrag.schema import GraphEntity, GraphExtractionResult, GraphRelation
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.hybrid_search import HybridSearchResult


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
