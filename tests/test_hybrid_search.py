from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate
from app.db.repositories import DocumentCreate
from app.db.repositories import DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.hybrid_search import HybridSearchService
from app.services.retrieval.hybrid_search import normalize_score
from app.services.retrieval.vector_index import VectorIndexService


def make_session(tmp_path):
    database_path = tmp_path / "hybrid_search.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_hybrid_documents(db: Session) -> None:
    repository = DocumentRepository(db)
    repository.create_with_chunks(
        DocumentCreate(
            title="Filling Capacity Evaluation of Self-Compacting Concrete",
            source_type="local_file",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="hybrid-filling-hash",
            raw_path="data/raw/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Filling capacity is evaluated by observing self compacting concrete flowability in prepacked rock voids.",
                char_count=101,
                heading_path="Filling",
                start_char=0,
                end_char=101,
            )
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="Thermal control note",
            source_type="metadata_record",
            source_path="thermal.md",
            file_name="thermal.md",
            file_extension=".md",
            content_hash="hybrid-thermal-hash",
            raw_path="data/raw/thermal.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Hydration heat and temperature control are discussed for rock filled concrete dams.",
                char_count=79,
                heading_path="Thermal",
                start_char=0,
                end_char=79,
            )
        ],
    )


def test_hybrid_search_uses_keyword_evidence_to_rank_expected_match(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)
        VectorIndexService(db, provider).build_index()

        results = HybridSearchService(db, provider).search("filling capacity rock-filled concrete", top_k=2)

    assert results
    assert results[0].document_title == "Filling Capacity Evaluation of Self-Compacting Concrete"
    assert results[0].keyword_score > 0
    assert results[0].score >= results[0].keyword_score * 0.7


def test_hybrid_search_returns_keyword_results_when_vector_index_is_missing(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_hybrid_documents(db)

        results = HybridSearchService(db, provider).search("filling capacity", top_k=2)

    assert results
    assert results[0].keyword_score > 0
    assert results[0].vector_score == 0
    assert "Filling Capacity" in results[0].document_title


def test_hybrid_search_rejects_invalid_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        service = HybridSearchService(db, provider)

        try:
            service.search("   ")
        except ValueError as exc:
            assert "query" in str(exc)
        else:
            raise AssertionError("Expected ValueError for empty query")

        try:
            service.search("filling", top_k=0)
        except ValueError as exc:
            assert "top_k" in str(exc)
        else:
            raise AssertionError("Expected ValueError for invalid top_k")


def test_normalize_score_handles_zero_and_caps_to_one() -> None:
    assert normalize_score(0.0, 10.0) == 0.0
    assert normalize_score(5.0, 0.0) == 0.0
    assert normalize_score(12.0, 10.0) == 1.0
    assert normalize_score(5.0, 10.0) == 0.5
