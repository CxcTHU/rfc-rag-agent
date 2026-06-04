from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.keyword_search import KeywordSearchService


def make_session(tmp_path):
    database_path = tmp_path / "keyword_search.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_keyword_search_returns_matching_chunks_ordered_by_score(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        repository = DocumentRepository(db)
        repository.create_with_chunks(
            DocumentCreate(
                title="堆石混凝土施工质量资料",
                source_type="local_file",
                source_path="quality.md",
                file_name="quality.md",
                file_extension=".md",
                content_hash="quality-hash",
                raw_path="data/raw/quality.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="堆石混凝土施工质量控制需要关注填充密实性。",
                    char_count=24,
                    heading_path="施工质量",
                    start_char=0,
                    end_char=24,
                ),
                ChunkCreate(
                    chunk_index=1,
                    content="自密实混凝土应充分填充堆石体空隙。",
                    char_count=18,
                    heading_path="材料",
                    start_char=25,
                    end_char=43,
                ),
            ],
        )

        results = KeywordSearchService(db).search("施工质量", top_k=5)

    assert len(results) == 1
    assert results[0].document_title == "堆石混凝土施工质量资料"
    assert results[0].file_name == "quality.md"
    assert results[0].source_path == "quality.md"
    assert results[0].chunk_index == 0
    assert results[0].score > 0


def test_keyword_search_returns_empty_list_when_no_chunk_matches(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        results = KeywordSearchService(db).search("不存在的关键词", top_k=5)

    assert results == []


def test_keyword_search_expands_chinese_synonyms(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        repository = DocumentRepository(db)
        repository.create_with_chunks(
            DocumentCreate(
                title="A Comprehensive Literature Review on the Elastic Modulus of Rock-filled Concrete",
                source_type="metadata_record",
                source_path="metadata.md",
                file_name="metadata.md",
                file_extension=".md",
                content_hash="elastic-hash",
                raw_path="data/raw/metadata.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="The elastic modulus of rock-filled concrete depends on the rockfill ratio.",
                    char_count=75,
                    heading_path="Abstract",
                    start_char=0,
                    end_char=75,
                ),
            ],
        )

        results = KeywordSearchService(db).search("\u5f39\u6027\u6a21\u91cf \u5806\u77f3\u6df7\u51dd\u571f", top_k=5)

    assert len(results) == 1
    assert "Elastic Modulus" in results[0].document_title
    assert results[0].source_type == "metadata_record"


def test_keyword_search_boosts_specific_terms_over_generic_domain_terms(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        repository = DocumentRepository(db)
        repository.create_with_chunks(
            DocumentCreate(
                title="Rock-filled concrete overview",
                source_type="metadata_record",
                source_path="overview.md",
                file_name="overview.md",
                file_extension=".md",
                content_hash="overview-hash",
                raw_path="data/raw/overview.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content=" ".join(["rock-filled concrete"] * 30),
                    char_count=600,
                    heading_path="Abstract",
                    start_char=0,
                    end_char=600,
                ),
            ],
        )
        repository.create_with_chunks(
            DocumentCreate(
                title="Full-Scale micromechanical simulation of rock-filled concretes using Peridynamics",
                source_type="open_access_pdf",
                source_path="peridynamics.pdf",
                file_name="peridynamics.pdf",
                file_extension=".pdf",
                content_hash="peridynamics-hash",
                raw_path="data/raw/peridynamics.pdf",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="Peridynamics is a mesh-free method for simulating rock-filled concretes.",
                    char_count=75,
                    heading_path="Abstract",
                    start_char=0,
                    end_char=75,
                ),
            ],
        )

        results = KeywordSearchService(db).search("peridynamics rock-filled concrete", top_k=5)

    assert results[0].document_title.startswith("Full-Scale micromechanical")
    assert results[0].source_type == "open_access_pdf"
