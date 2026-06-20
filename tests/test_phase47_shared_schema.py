import pytest
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker

from app.db.feedback_repository import FeedbackCreate, FeedbackRepository
from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.schemas.feedback import FeedbackCreateRequest


def make_session(tmp_path):
    database_path = tmp_path / "phase47_shared.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_chunk_create_persists_content_bbox_json(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        document = DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Phase 47 bbox test",
                source_type="open_access_pdf",
                source_path=None,
                file_name="bbox.pdf",
                file_extension=".pdf",
                content_hash="phase47-bbox",
                raw_path="data/raw/bbox.pdf",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="rock-filled concrete test chunk",
                    char_count=31,
                    heading_path=None,
                    start_char=0,
                    end_char=31,
                    page_number=3,
                    content_bbox_json='{"page":3,"confidence":"exact","bboxes":[]}',
                )
            ],
        )

        chunk = document.chunks[0]
        assert chunk.page_number == 3
        assert chunk.content_bbox_json == '{"page":3,"confidence":"exact","bboxes":[]}'


def test_feedback_repository_creates_and_counts_feedback(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        repository = FeedbackRepository(db)
        positive = repository.create_feedback(
            FeedbackCreate(
                question="What affects RFC strength?",
                answer="Strength depends on mix ratio and compaction quality.",
                rating="positive",
            )
        )
        negative = repository.create_feedback(
            FeedbackCreate(
                question="Where is the citation?",
                answer="No source was cited.",
                rating="negative",
                reason="no_citation",
                comment="Please include sources.",
            )
        )

        assert positive.id != negative.id
        assert repository.count_feedback() == 2
        assert repository.count_feedback("positive") == 1
        assert repository.count_feedback("negative") == 1
        assert repository.get_by_id(negative.id).reason == "no_citation"


def test_feedback_request_requires_reason_for_negative_feedback() -> None:
    with pytest.raises(ValidationError):
        FeedbackCreateRequest(
            question="Question",
            answer="Answer",
            rating="negative",
        )

    request = FeedbackCreateRequest(
        question=" Question ",
        answer=" Answer ",
        rating="positive",
    )
    assert request.question == "Question"
    assert request.answer == "Answer"
