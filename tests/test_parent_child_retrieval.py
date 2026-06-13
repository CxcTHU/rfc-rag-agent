from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.ingestion.parent_chunker import flatten_child_chunks, split_parent_child_text
from app.services.retrieval.parent_child_search import ParentChildSearchService


@dataclass(frozen=True)
class SearchResultFixture:
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    content: str
    heading_path: str | None
    score: float


def make_session(tmp_path):
    database_path = tmp_path / "parent_child.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_split_parent_child_text_returns_parent_and_child_plans() -> None:
    text = (
        "# 施工质量\n\n"
        "堆石混凝土施工质量需要关注堆石级配、自密实混凝土流动性、填充密实性和温控措施。"
        "这些因素共同影响结构可靠性和现场质量控制。"
    )

    plans = split_parent_child_text(
        text,
        parent_chunk_size=80,
        parent_chunk_overlap=10,
        child_chunk_size=35,
        child_chunk_overlap=5,
    )

    assert plans
    assert all(plan.parent.char_count >= max(child.char_count for child in plan.children) for plan in plans)
    assert flatten_child_chunks(plans)


def test_split_parent_child_text_rejects_parent_smaller_than_child() -> None:
    try:
        split_parent_child_text("abc", parent_chunk_size=100, child_chunk_size=100)
    except ValueError as exc:
        assert "parent_chunk_size" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid chunk sizes")


def test_parent_child_search_expands_child_hit_to_parent_context(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        document = DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Parent child document",
                source_type="local_file",
                source_path="parent.md",
                file_name="parent.md",
                file_extension=".md",
                content_hash="parent-child-search-hash",
                raw_path="data/raw/parent.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="Parent context explains filling capacity, flowability, and aggregate voids.",
                    char_count=75,
                    heading_path="Parent",
                    start_char=0,
                    end_char=75,
                ),
                ChunkCreate(
                    chunk_index=1,
                    content="Child hit mentions flowability.",
                    char_count=29,
                    heading_path="Parent",
                    start_char=0,
                    end_char=29,
                ),
            ],
        )
        parent, child = DocumentRepository(db).list_chunks(document.id)
        child.parent_chunk_id = parent.id
        db.commit()

        result = SearchResultFixture(
            document_id=document.id,
            document_title=document.title,
            source_type=document.source_type,
            source_path=document.source_path,
            file_name=document.file_name,
            chunk_id=child.id,
            chunk_index=child.chunk_index,
            content=child.content,
            heading_path=child.heading_path,
            score=0.9,
        )

        expanded = ParentChildSearchService(db).expand_result(result)

    assert "aggregate voids" in expanded.content
    assert expanded.core_content == "Child hit mentions flowability."
    assert expanded.context_chunk_ids[0] == parent.id
    assert expanded.context_chunk_ids[1] == child.id


def test_parent_child_search_falls_back_when_parent_is_missing(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        document = DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Fallback document",
                source_type="local_file",
                source_path="fallback.md",
                file_name="fallback.md",
                file_extension=".md",
                content_hash="fallback-parent-child-hash",
                raw_path="data/raw/fallback.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="Previous adjacent context.",
                    char_count=26,
                    heading_path="Fallback",
                    start_char=0,
                    end_char=26,
                ),
                ChunkCreate(
                    chunk_index=1,
                    content="Child without parent.",
                    char_count=21,
                    heading_path="Fallback",
                    start_char=27,
                    end_char=48,
                ),
            ],
        )
        child = db.query(Chunk).filter_by(document_id=document.id, chunk_index=1).one()
        result = SearchResultFixture(
            document_id=document.id,
            document_title=document.title,
            source_type=document.source_type,
            source_path=document.source_path,
            file_name=document.file_name,
            chunk_id=child.id,
            chunk_index=child.chunk_index,
            content=child.content,
            heading_path=child.heading_path,
            score=0.8,
        )

        expanded = ParentChildSearchService(db).expand_result(result)

    assert "Previous adjacent context." in expanded.content
    assert expanded.context_window == 1
