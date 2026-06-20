from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.agent.tools import AgentToolbox
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.citation_locator import CitationLocator
from app.services.retrieval.embedding import DeterministicEmbeddingProvider


def make_session(tmp_path):
    database_path = tmp_path / "citation_locator.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_citation_locator_returns_bbox_location(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        document = DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Citation source",
                source_type="open_access_pdf",
                source_path=None,
                file_name="citation.pdf",
                file_extension=".pdf",
                content_hash="citation-source",
                raw_path="data/raw/citation.pdf",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="Rock-filled concrete citation text.",
                    char_count=35,
                    heading_path=None,
                    start_char=0,
                    end_char=35,
                    page_number=3,
                    content_bbox_json=(
                        '{"page":3,"confidence":"exact",'
                        '"bboxes":[{"x0":10,"y0":20,"x1":110,"y1":40}]}'
                    ),
                )
            ],
        )
        chunk = document.chunks[0]

        location = CitationLocator().locate(chunk.id, db)

    assert location is not None
    assert location.chunk_id == chunk.id
    assert location.document_id == document.id
    assert location.document_title == "Citation source"
    assert location.file_name == "citation.pdf"
    assert location.page_number == 3
    assert location.confidence == "exact"
    assert location.bboxes == [{"x0": 10.0, "y0": 20.0, "x1": 110.0, "y1": 40.0}]
    assert location.pdf_url == "/assets/raw/citation.pdf"


def test_citation_locator_returns_none_confidence_without_bbox(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        document = DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Page-only source",
                source_type="open_access_pdf",
                source_path=None,
                file_name="page-only.pdf",
                file_extension=".pdf",
                content_hash="page-only-source",
                raw_path="data/raw/page-only.pdf",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="Chunk without bbox.",
                    char_count=19,
                    heading_path=None,
                    start_char=0,
                    end_char=19,
                    page_number=7,
                )
            ],
        )
        chunk = document.chunks[0]

        location = CitationLocator().locate(chunk.id, db)

    assert location is not None
    assert location.page_number == 7
    assert location.bboxes is None
    assert location.confidence == "none"


def test_citation_locator_batch_returns_all_requested_chunks(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        document = DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Batch source",
                source_type="open_access_pdf",
                source_path=None,
                file_name="batch.pdf",
                file_extension=".pdf",
                content_hash="batch-source",
                raw_path="data/raw/batch.pdf",
            ),
            [
                ChunkCreate(
                    chunk_index=index,
                    content=f"Chunk {index}",
                    char_count=7,
                    heading_path=None,
                    start_char=None,
                    end_char=None,
                    page_number=index + 1,
                    content_bbox_json=(
                        f'{{"page":{index + 1},"confidence":"page_only","bboxes":[]}}'
                    ),
                )
                for index in range(3)
            ],
        )
        chunk_ids = [chunk.id for chunk in document.chunks]

        locations = CitationLocator().locate_batch(chunk_ids, db)

    assert set(locations) == set(chunk_ids)
    assert [locations[chunk_id].page_number for chunk_id in chunk_ids] == [1, 2, 3]
    assert all(location.confidence == "page_only" for location in locations.values())


def test_agent_toolbox_search_results_include_content_bbox(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Tool bbox source",
                source_type="open_access_pdf",
                source_path=None,
                file_name="tool-bbox.pdf",
                file_extension=".pdf",
                content_hash="tool-bbox-source",
                raw_path="data/raw/tool-bbox.pdf",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="Filling capacity depends on self-compacting concrete flowability.",
                    char_count=66,
                    heading_path=None,
                    start_char=None,
                    end_char=None,
                    page_number=5,
                    content_bbox_json=(
                        '{"page":5,"confidence":"partial",'
                        '"bboxes":[{"x0":1,"y0":2,"x1":3,"y1":4}]}'
                    ),
                )
            ],
        )
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )

        result = toolbox.search_knowledge("filling capacity", top_k=1)

    assert result.search_results[0].content_bbox is not None
    assert result.search_results[0].content_bbox["confidence"] == "partial"
    assert result.search_results[0].content_bbox["page_number"] == 5
    assert result.sources[0].content_bbox == result.search_results[0].content_bbox
