from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.bm25_search import BM25SearchService, inverse_document_frequency, lexical_length


def make_session(tmp_path):
    database_path = tmp_path / "bm25_search.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_bm25_documents(db: Session) -> None:
    repository = DocumentRepository(db)
    repository.create_with_chunks(
        DocumentCreate(
            title="ITZ strength of rock-filled concrete",
            source_type="local_file",
            source_path="itz.md",
            file_name="itz.md",
            file_extension=".md",
            content_hash="bm25-itz-hash",
            raw_path="data/raw/itz.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="The interfacial transition zone between rock and SCC affects compressive strength.",
                char_count=82,
                heading_path="ITZ strength",
                start_char=0,
                end_char=82,
            )
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="Thermal control guide",
            source_type="metadata_record",
            source_path="thermal.md",
            file_name="thermal.md",
            file_extension=".md",
            content_hash="bm25-thermal-hash",
            raw_path="data/raw/thermal.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Hydration heat and temperature control are discussed for RFC dams.",
                char_count=68,
                heading_path="Thermal",
                start_char=0,
                end_char=68,
            )
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="孔隙率与抗压性能",
            source_type="open_access_pdf",
            source_path="porosity.md",
            file_name="porosity.md",
            file_extension=".md",
            content_hash="bm25-porosity-hash",
            raw_path="data/raw/porosity.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="堆石混凝土孔隙率和孔洞缺陷会影响抗压行为与强度。",
                char_count=29,
                heading_path="孔隙率 抗压",
                start_char=0,
                end_char=29,
            )
        ],
    )


def test_bm25_search_ranks_exact_english_domain_match_first(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_bm25_documents(db)
        results = BM25SearchService(db).search("rock and SCC interface ITZ strength", top_k=3)

    assert results
    assert results[0].document_title == "ITZ strength of rock-filled concrete"
    assert "itz" in results[0].matched_terms
    assert results[0].title_score > 0


def test_bm25_search_supports_chinese_domain_terms(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_bm25_documents(db)
        results = BM25SearchService(db).search("孔隙率会怎么影响抗压强度", top_k=3)

    assert results[0].document_title == "孔隙率与抗压性能"
    assert any(term in results[0].matched_terms for term in ("孔隙率", "抗压", "strength"))
    assert results[0].heading_score > 0


def test_bm25_search_keeps_stable_order_for_ties(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        repository = DocumentRepository(db)
        for index, title in enumerate(["Tie A", "Tie B"], start=1):
            repository.create_with_chunks(
                DocumentCreate(
                    title=title,
                    source_type="local_file",
                    source_path=f"tie-{index}.md",
                    file_name=f"tie-{index}.md",
                    file_extension=".md",
                    content_hash=f"bm25-tie-{index}",
                    raw_path=f"data/raw/tie-{index}.md",
                ),
                [
                    ChunkCreate(
                        chunk_index=0,
                        content="same rare term",
                        char_count=14,
                        heading_path="Tie",
                        start_char=0,
                        end_char=14,
                    )
                ],
            )
        results = BM25SearchService(db).search("rare term", top_k=2)

    assert [result.document_title for result in results] == ["Tie A", "Tie B"]


def test_bm25_search_rejects_invalid_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        service = BM25SearchService(db)

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


def test_bm25_helpers_handle_length_and_idf() -> None:
    assert lexical_length("孔隙率 porosity test") >= 4
    assert inverse_document_frequency(corpus_size=10, document_frequency=1) > inverse_document_frequency(
        corpus_size=10,
        document_frequency=8,
    )
