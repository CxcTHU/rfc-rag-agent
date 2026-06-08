from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.context_expansion import ContextExpansionService, truncate_context
from app.services.retrieval.keyword_search import KeywordSearchService


def make_session(tmp_path):
    database_path = tmp_path / "context_expansion.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_context_documents(db: Session) -> None:
    repository = DocumentRepository(db)
    repository.create_with_chunks(
        DocumentCreate(
            title="RFC context guide",
            source_type="local_file",
            source_path="context.md",
            file_name="context.md",
            file_extension=".md",
            content_hash="context-guide-hash",
            raw_path="data/raw/context.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Opening context explains the rock-filled concrete test setup.",
                char_count=61,
                heading_path="Setup",
                start_char=0,
                end_char=61,
            ),
            ChunkCreate(
                chunk_index=1,
                content="Core evidence says ITZ between rock and SCC can influence compressive strength.",
                char_count=78,
                heading_path="ITZ",
                start_char=62,
                end_char=140,
            ),
            ChunkCreate(
                chunk_index=2,
                content="Following context describes porosity and local defects near the interface.",
                char_count=72,
                heading_path="ITZ",
                start_char=141,
                end_char=213,
            ),
        ],
    )
    repository.create_with_chunks(
        DocumentCreate(
            title="Other document",
            source_type="local_file",
            source_path="other.md",
            file_name="other.md",
            file_extension=".md",
            content_hash="other-context-hash",
            raw_path="data/raw/other.md",
        ),
        [
            ChunkCreate(
                chunk_index=1,
                content="This chunk has the same index but belongs to another document.",
                char_count=61,
                heading_path="Other",
                start_char=0,
                end_char=61,
            ),
        ],
    )


def test_context_expansion_adds_adjacent_chunks_without_changing_core_identity(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_context_documents(db)
        result = KeywordSearchService(db).search("compressive strength ITZ", top_k=1)[0]
        expanded = ContextExpansionService(db).expand_result(result, window=1)

    assert expanded.chunk_id == result.chunk_id
    assert expanded.chunk_index == result.chunk_index
    assert expanded.core_content == result.content
    assert "Opening context" in expanded.content
    assert "Core evidence" in expanded.content
    assert "Following context" in expanded.content
    assert "another document" not in expanded.content
    assert len(expanded.context_chunk_ids) == 3


def test_context_expansion_respects_document_edges(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_context_documents(db)
        result = KeywordSearchService(db).search("Opening context", top_k=1)[0]
        expanded = ContextExpansionService(db).expand_result(result, window=1)

    assert len(expanded.context_chunk_ids) == 2
    assert "Opening context" in expanded.content
    assert "Core evidence" in expanded.content


def test_context_expansion_can_be_disabled_with_zero_window(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_context_documents(db)
        result = KeywordSearchService(db).search("compressive strength ITZ", top_k=1)[0]
        expanded = ContextExpansionService(db).expand_result(result, window=0)

    assert expanded.context_chunk_ids == (result.chunk_id,)
    assert expanded.content == result.content


def test_context_expansion_rejects_invalid_limits(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        service = ContextExpansionService(db)
        seed_context_documents(db)
        result = KeywordSearchService(db).search("compressive strength ITZ", top_k=1)[0]

        try:
            service.expand_result(result, window=-1)
        except ValueError as exc:
            assert "window" in str(exc)
        else:
            raise AssertionError("Expected ValueError for negative window")

        try:
            service.expand_result(result, max_context_chars=0)
        except ValueError as exc:
            assert "max_context_chars" in str(exc)
        else:
            raise AssertionError("Expected ValueError for invalid context limit")


def test_truncate_context_adds_suffix_when_needed() -> None:
    truncated = truncate_context("a" * 80, max_context_chars=40)

    assert len(truncated) <= 40
    assert truncated.endswith("[context truncated]")
