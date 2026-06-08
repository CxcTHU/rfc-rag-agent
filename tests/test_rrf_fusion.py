from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.rrf_fusion import RRFHybridSearchService, reciprocal_rank_score
from app.services.retrieval.vector_index import VectorIndexService
from app.services.generation.prompt_builder import build_rag_prompt


def make_session(tmp_path):
    database_path = tmp_path / "rrf_fusion.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_rrf_documents(db: Session) -> None:
    repository = DocumentRepository(db)
    repository.create_with_chunks(
        DocumentCreate(
            title="ITZ strength source",
            source_type="local_file",
            source_path="itz.md",
            file_name="itz.md",
            file_extension=".md",
            content_hash="rrf-itz-hash",
            raw_path="data/raw/itz.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Before context explains the rock and SCC specimen setup.",
                char_count=59,
                heading_path="Setup",
                start_char=0,
                end_char=59,
            ),
            ChunkCreate(
                chunk_index=1,
                content="ITZ interface between rock and SCC affects compressive strength.",
                char_count=66,
                heading_path="ITZ",
                start_char=60,
                end_char=126,
            ),
            ChunkCreate(
                chunk_index=2,
                content="After context explains local porosity near the interface.",
                char_count=58,
                heading_path="ITZ",
                start_char=127,
                end_char=185,
            ),
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="Filling capacity source",
            source_type="open_access_pdf",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="rrf-filling-hash",
            raw_path="data/raw/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Filling capacity depends on SCC flowability through prepacked rock voids.",
                char_count=76,
                heading_path="Filling",
                start_char=0,
                end_char=76,
            )
        ],
    )


def test_rrf_hybrid_search_combines_bm25_and_vector_channels(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_rrf_documents(db)
        VectorIndexService(db, provider).build_index()

        results = RRFHybridSearchService(db, provider).search("ITZ interface compressive strength", top_k=2)

    assert results
    assert results[0].document_title == "ITZ strength source"
    assert "bm25" in results[0].matched_channels
    assert "vector" in results[0].matched_channels
    assert results[0].bm25_rank is not None
    assert results[0].vector_rank is not None
    assert "rrf_score" in results[0].provenance


def test_rrf_hybrid_search_degrades_to_bm25_when_vector_index_is_missing(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_rrf_documents(db)

        results = RRFHybridSearchService(db, provider).search("filling capacity", top_k=2)

    assert results[0].document_title == "Filling capacity source"
    assert results[0].matched_channels == ("bm25",)
    assert results[0].bm25_rank == 1
    assert results[0].vector_rank is None


def test_rrf_hybrid_search_can_expand_context_for_prompt_assembly(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_rrf_documents(db)
        VectorIndexService(db, provider).build_index()

        results = RRFHybridSearchService(db, provider).search(
            "ITZ interface compressive strength",
            top_k=1,
            context_window=1,
        )
        prompt = build_rag_prompt("How does ITZ affect strength?", results)

    assert results[0].chunk_index == 1
    assert "Before context" in results[0].content
    assert "ITZ interface" in results[0].content
    assert "After context" in results[0].content
    assert results[0].context_window == 1
    assert len(results[0].context_chunk_ids) == 3
    assert prompt.sources[0].chunk_id == results[0].chunk_id
    assert "Before context" in prompt.context_text


def test_rrf_hybrid_search_rejects_invalid_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        service = RRFHybridSearchService(db, provider)

        try:
            service.search("   ")
        except ValueError as exc:
            assert "query" in str(exc)
        else:
            raise AssertionError("Expected ValueError for empty query")

        try:
            service.search("ITZ", top_k=0)
        except ValueError as exc:
            assert "top_k" in str(exc)
        else:
            raise AssertionError("Expected ValueError for invalid top_k")

        try:
            RRFHybridSearchService(db, provider, rank_constant=0)
        except ValueError as exc:
            assert "rank_constant" in str(exc)
        else:
            raise AssertionError("Expected ValueError for invalid rank constant")


def test_reciprocal_rank_score_uses_rank_not_raw_scores() -> None:
    assert reciprocal_rank_score(None) == 0.0
    assert reciprocal_rank_score(1) > reciprocal_rank_score(5)
    assert reciprocal_rank_score(1, rank_constant=10) == 1 / 11
