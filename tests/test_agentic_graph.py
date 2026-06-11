"""Tests for the LangGraph agentic RAG graph (Phase 21)."""

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.agentic.graph import build_agentic_graph, run_agentic_rag
from app.services.agentic.nodes import (
    citation_check_node,
    generate_node,
    grade_node,
    grade_router,
    retrieve_node,
    rewrite_node,
)
from app.services.agentic.state import MAX_ITERATIONS, AgenticState
from app.services.brain.workflow import (
    DEFAULT_REFUSAL_ANSWER,
    RESPONSIBILITY_REFUSAL_ANSWER,
)
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider


def make_session(tmp_path):
    db_path = tmp_path / "agentic_test.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_rfc_documents(db) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Rock-filled concrete thermal control guide",
            source_type="open_access_pdf",
            source_path="thermal-guide.md",
            file_name="thermal-guide.md",
            file_extension=".md",
            content_hash="agentic-thermal-hash",
            raw_path="data/raw/thermal-guide.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Thermal control in rock-filled concrete dams involves managing "
                    "hydration heat through cooling pipes and low-heat cement. "
                    "Adiabatic temperature rise must be monitored. 堆石混凝土 温控。"
                ),
                char_count=150,
                heading_path="Thermal control",
                start_char=0,
                end_char=150,
            ),
            ChunkCreate(
                chunk_index=1,
                content=(
                    "Self-compacting concrete filling performance in rock-filled "
                    "concrete depends on aggregate grading and flowability. "
                    "堆石混凝土 填充 自密实 流动。"
                ),
                char_count=140,
                heading_path="Filling performance",
                start_char=151,
                end_char=291,
            ),
        ],
    )


def seed_responsibility_documents(db) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="RFC mix design compliance notes",
            source_type="local_file",
            source_path="compliance.md",
            file_name="compliance.md",
            file_extension=".md",
            content_hash="agentic-compliance-hash",
            raw_path="data/raw/compliance.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "堆石混凝土 配合比 设计 规范 要求 自密实 流动 强度 "
                    "指标 can provide indicators for engineering review."
                ),
                char_count=80,
                heading_path="Mix design",
                start_char=0,
                end_char=80,
            ),
        ],
    )


# --- Graph structure tests ---


def test_graph_compiles_with_expected_nodes():
    graph = build_agentic_graph()
    compiled = graph.compile()
    node_names = set(compiled.nodes.keys()) - {"__start__"}
    assert node_names == {"retrieve", "grade", "rewrite", "re_retrieve", "generate", "citation_check"}


def test_max_iterations_is_three():
    assert MAX_ITERATIONS == 3


# --- Retrieve node tests ---


def test_retrieve_node_returns_results(tmp_path):
    session_factory = make_session(tmp_path)
    with session_factory() as db:
        seed_rfc_documents(db)
        state: AgenticState = {
            "question": "rock-filled concrete thermal control 堆石混凝土",
            "_db": db,
            "_embedding_provider": DeterministicEmbeddingProvider(dimension=32),
            "_chat_model_provider": DeterministicChatModelProvider(),
        }
        result = retrieve_node(state)

    assert "results" in result
    assert len(result["results"]) > 0
    assert result["iteration_count"] == 0
    assert result["retrieval_queries"] == ["rock-filled concrete thermal control 堆石混凝土"]


# --- Grade node tests ---


def test_grade_node_sufficient_evidence(tmp_path):
    session_factory = make_session(tmp_path)
    with session_factory() as db:
        seed_rfc_documents(db)
        state: AgenticState = {
            "question": "rock-filled concrete thermal control 堆石混凝土",
            "_db": db,
            "_embedding_provider": DeterministicEmbeddingProvider(dimension=32),
            "_chat_model_provider": DeterministicChatModelProvider(),
        }
        retrieve_result = retrieve_node(state)
        state.update(retrieve_result)
        grade_result = grade_node(state)

    assert grade_result["evidence_sufficient"] is True
    assert grade_result["confidence_score"] > 0


def test_grade_node_off_topic_returns_insufficient():
    state: AgenticState = {
        "question": "how to cook chicken soup",
        "results": [],
        "iteration_count": 0,
    }
    result = grade_node(state)
    assert result["evidence_sufficient"] is False


# --- Grade router tests ---


def test_grade_router_sufficient_goes_to_generate():
    state: AgenticState = {"evidence_sufficient": True, "iteration_count": 0}
    assert grade_router(state) == "generate"


def test_grade_router_insufficient_below_max_goes_to_rewrite():
    state: AgenticState = {"evidence_sufficient": False, "iteration_count": 0}
    assert grade_router(state) == "rewrite"


def test_grade_router_insufficient_at_max_goes_to_generate():
    state: AgenticState = {"evidence_sufficient": False, "iteration_count": MAX_ITERATIONS}
    assert grade_router(state) == "generate"


# --- Rewrite node tests ---


def test_rewrite_node_increments_iteration():
    state: AgenticState = {
        "question": "堆石混凝土温控措施",
        "results": [],
        "iteration_count": 1,
    }
    result = rewrite_node(state)
    assert result["iteration_count"] == 2
    assert "rewritten_query" in result


# --- Generate node tests ---


def test_generate_node_produces_answer(tmp_path):
    session_factory = make_session(tmp_path)
    with session_factory() as db:
        seed_rfc_documents(db)
        embedding = DeterministicEmbeddingProvider(dimension=32)
        chat = DeterministicChatModelProvider()
        state: AgenticState = {
            "question": "rock-filled concrete thermal control 堆石混凝土",
            "_db": db,
            "_embedding_provider": embedding,
            "_chat_model_provider": chat,
        }
        retrieve_result = retrieve_node(state)
        state.update(retrieve_result)
        gen_result = generate_node(state)

    assert gen_result["refused"] is False
    assert gen_result["answer"]
    assert gen_result["responsibility_gate_triggered"] is False


def test_generate_node_refuses_responsibility_question(tmp_path):
    session_factory = make_session(tmp_path)
    with session_factory() as db:
        seed_responsibility_documents(db)
        embedding = DeterministicEmbeddingProvider(dimension=32)
        chat = DeterministicChatModelProvider()
        state: AgenticState = {
            "question": "请判定本工程的堆石混凝土配合比设计是否符合规范要求？",
            "_db": db,
            "_embedding_provider": embedding,
            "_chat_model_provider": chat,
            "results": list(
                __import__(
                    "app.services.retrieval.hybrid_search", fromlist=["HybridSearchService"]
                ).HybridSearchService(db, embedding).search(
                    query="堆石混凝土配合比规范", top_k=3
                )
            ),
        }
        gen_result = generate_node(state)

    assert gen_result["refused"] is True
    assert gen_result["responsibility_gate_triggered"] is True
    assert RESPONSIBILITY_REFUSAL_ANSWER in gen_result["answer"]


def test_generate_node_refuses_no_results():
    state: AgenticState = {
        "question": "test question",
        "results": [],
        "_chat_model_provider": DeterministicChatModelProvider(),
    }
    result = generate_node(state)
    assert result["refused"] is True
    assert DEFAULT_REFUSAL_ANSWER in result["answer"]


# --- Citation check node tests ---


def test_citation_check_valid_citations(tmp_path):
    session_factory = make_session(tmp_path)
    with session_factory() as db:
        seed_rfc_documents(db)
        embedding = DeterministicEmbeddingProvider(dimension=32)
        from app.services.retrieval.hybrid_search import HybridSearchService
        results = list(HybridSearchService(db, embedding).search(
            query="rock-filled concrete thermal 堆石混凝土", top_k=2,
        ))
        state: AgenticState = {
            "citations": [1],
            "results": results,
        }
        result = citation_check_node(state)

    assert result["invalid_citations"] == []


def test_citation_check_detects_invalid():
    state: AgenticState = {
        "citations": [1, 99],
        "results": [],
    }
    result = citation_check_node(state)
    assert result["invalid_citations"] == []

    from app.services.retrieval.hybrid_search import HybridSearchResult
    fake_result = HybridSearchResult(
        document_id=1, document_title="t", source_type="s", source_path=None,
        file_name="f", chunk_id=10, chunk_index=0, content="c",
        heading_path=None, score=1.0, keyword_score=1.0, vector_score=0.0,
    )
    state2: AgenticState = {
        "citations": [1, 99],
        "results": [fake_result],
    }
    result2 = citation_check_node(state2)
    assert 99 in result2["invalid_citations"]


# --- Hard iteration cap test ---


def test_hard_iteration_cap_enforced(tmp_path):
    """Ensure the graph terminates after MAX_ITERATIONS even if evidence is never sufficient."""
    session_factory = make_session(tmp_path)
    with session_factory() as db:
        DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Unrelated content about RFC construction",
                source_type="local_file",
                source_path="unrelated.md",
                file_name="unrelated.md",
                file_extension=".md",
                content_hash="agentic-unrelated-hash",
                raw_path="data/raw/unrelated.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="堆石混凝土 generic content that does not cover specific answer points about seismic performance",
                    char_count=80,
                    heading_path="General",
                    start_char=0,
                    end_char=80,
                ),
            ],
        )
        result = run_agentic_rag(
            question="堆石混凝土坝体在特大地震下的非线性动力响应特征有哪些？",
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=DeterministicChatModelProvider(),
        )

    assert result.iteration_count <= MAX_ITERATIONS


# --- End-to-end tests ---


def test_end_to_end_agentic_rag_on_topic(tmp_path):
    session_factory = make_session(tmp_path)
    with session_factory() as db:
        seed_rfc_documents(db)
        result = run_agentic_rag(
            question="rock-filled concrete thermal control 堆石混凝土温控",
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=DeterministicChatModelProvider(),
        )

    assert result.answer
    assert not result.refused
    assert result.question == "rock-filled concrete thermal control 堆石混凝土温控"
    assert len(result.sources) > 0
    assert result.iteration_count <= MAX_ITERATIONS


def test_end_to_end_agentic_rag_off_topic(tmp_path):
    session_factory = make_session(tmp_path)
    with session_factory() as db:
        seed_rfc_documents(db)
        result = run_agentic_rag(
            question="how to cook chicken soup",
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=DeterministicChatModelProvider(),
        )

    assert result.refused or DEFAULT_REFUSAL_ANSWER in result.answer


def test_end_to_end_agentic_rag_responsibility_gate(tmp_path):
    session_factory = make_session(tmp_path)
    with session_factory() as db:
        seed_responsibility_documents(db)
        result = run_agentic_rag(
            question="请判定本工程的堆石混凝土配合比设计是否符合规范要求？",
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=DeterministicChatModelProvider(),
        )

    assert result.refused
    assert RESPONSIBILITY_REFUSAL_ANSWER in result.answer


def test_end_to_end_empty_database(tmp_path):
    session_factory = make_session(tmp_path)
    with session_factory() as db:
        result = run_agentic_rag(
            question="堆石混凝土温控 rock-filled concrete",
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=DeterministicChatModelProvider(),
        )

    assert result.refused or DEFAULT_REFUSAL_ANSWER in result.answer
