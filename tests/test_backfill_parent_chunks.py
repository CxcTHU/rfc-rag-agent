from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, ChunkEmbedding
from app.db.repositories import (
    ChunkCreate,
    ChunkEmbeddingCreate,
    ChunkEmbeddingRepository,
    DocumentCreate,
    DocumentRepository,
)
from app.db.session import create_sqlite_engine
from app.services.retrieval.vector_index import calculate_text_hash
from scripts.backfill_parent_chunks import (
    ChildSpan,
    PARENT_HEADING_PREFIX,
    backfill_parent_chunks,
    choose_parent_for_child,
)


def make_session(tmp_path):
    database_path = tmp_path / "backfill_parent_chunks.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_document(db):
    repository = DocumentRepository(db)
    document = repository.create_with_chunks(
        DocumentCreate(
            title="Backfill parent chunks",
            source_type="local_file",
            source_path="backfill.md",
            file_name="backfill.md",
            file_extension=".md",
            content_hash="backfill-parent-chunks-doc-hash",
            raw_path="data/raw/backfill.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="堆石混凝土填充性能需要关注自密实混凝土流动性。",
                char_count=25,
                heading_path=None,
                start_char=0,
                end_char=25,
            ),
            ChunkCreate(
                chunk_index=1,
                content="大粒径堆石的孔隙结构会影响浆体填充路径。",
                char_count=23,
                heading_path="填充性能",
                start_char=26,
                end_char=49,
            ),
            ChunkCreate(
                chunk_index=2,
                content="施工质量控制还需要关注温控、振捣和现场检测。",
                char_count=24,
                heading_path="施工质量",
                start_char=50,
                end_char=74,
            ),
        ],
    )
    embedding_repository = ChunkEmbeddingRepository(db)
    for chunk in repository.list_chunks(document.id):
        embedding_repository.save_embedding(
            ChunkEmbeddingCreate(
                chunk_id=chunk.id,
                provider="deterministic",
                model_name="hash-token-v1",
                dimension=3,
                embedding=[1.0, 0.0, 0.0],
                content_hash=calculate_text_hash(chunk.content),
            ),
        )
    return document


def test_backfill_parent_chunks_dry_run_does_not_write(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        document = seed_document(db)
        stats = backfill_parent_chunks(
            db=db,
            dry_run=True,
            parent_chunk_size=70,
            parent_chunk_overlap=10,
        )
        chunks = DocumentRepository(db).list_chunks(document.id)

    assert stats.dry_run is True
    assert stats.parent_chunks_created > 0
    assert stats.child_chunks_updated == 3
    assert len(chunks) == 3
    assert all(chunk.parent_chunk_id is None for chunk in chunks)


def test_backfill_parent_chunks_creates_parents_and_links_existing_children(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        document = seed_document(db)
        stats = backfill_parent_chunks(
            db=db,
            parent_chunk_size=70,
            parent_chunk_overlap=10,
        )
        chunks = DocumentRepository(db).list_chunks(document.id)
        parent_chunks = [
            chunk
            for chunk in chunks
            if chunk.heading_path and chunk.heading_path.startswith(PARENT_HEADING_PREFIX)
        ]
        child_chunks = [
            chunk
            for chunk in chunks
            if not (chunk.heading_path and chunk.heading_path.startswith(PARENT_HEADING_PREFIX))
        ]
        parent_ids = {chunk.id for chunk in parent_chunks}
        parent_embedding_count = db.scalar(
            select(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(parent_ids))
        )

    assert stats.documents_changed == 1
    assert stats.parent_chunks_created >= 1
    assert stats.child_chunks_updated == 3
    assert len(child_chunks) == 3
    assert all(child.parent_chunk_id in parent_ids for child in child_chunks)
    assert parent_embedding_count is None


def test_backfill_parent_chunks_is_idempotent(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        document = seed_document(db)
        first_stats = backfill_parent_chunks(
            db=db,
            parent_chunk_size=70,
            parent_chunk_overlap=10,
        )
        second_stats = backfill_parent_chunks(
            db=db,
            parent_chunk_size=70,
            parent_chunk_overlap=10,
        )
        parent_chunks = [
            chunk
            for chunk in DocumentRepository(db).list_chunks(document.id)
            if chunk.heading_path and chunk.heading_path.startswith(PARENT_HEADING_PREFIX)
        ]

    assert first_stats.parent_chunks_created == len(parent_chunks)
    assert second_stats.parent_chunks_created == 0
    assert second_stats.parent_chunks_reused == len(parent_chunks)
    assert second_stats.child_chunks_updated == 0


def test_choose_parent_for_child_falls_back_to_nearest_parent_without_overlap() -> None:
    child = Chunk(
        id=10,
        document_id=1,
        chunk_index=2,
        content="short tail",
        char_count=10,
        start_char=210,
        end_char=220,
    )
    earlier_parent = Chunk(
        id=20,
        document_id=1,
        chunk_index=3,
        content="earlier",
        char_count=100,
        start_char=0,
        end_char=100,
    )
    nearest_parent = Chunk(
        id=21,
        document_id=1,
        chunk_index=4,
        content="nearest",
        char_count=80,
        start_char=120,
        end_char=180,
    )

    parent = choose_parent_for_child(
        ChildSpan(chunk=child, start=210, end=220),
        [earlier_parent, nearest_parent],
    )

    assert parent is nearest_parent
