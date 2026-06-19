from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, ChunkEmbedding, Document
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from scripts.index_phase45_cloud_candidates import index_candidate_chunks, read_all_document_ids


def make_session(tmp_path: Path):
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'index.sqlite').as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_indexes_only_phase45_candidate_document_chunks(tmp_path: Path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        repository = DocumentRepository(db)
        candidate = repository.create_with_chunks(
            DocumentCreate(
                title="candidate",
                source_type="institutional_access_pdf",
                source_path="candidate.pdf",
                file_name="candidate.pdf",
                file_extension=".pdf",
                content_hash="candidate-hash",
                raw_path="data/raw/candidate.pdf",
                status="imported",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="堆石混凝土施工质量控制。",
                    char_count=12,
                    heading_path=None,
                    start_char=None,
                    end_char=None,
                )
            ],
        )
        review = repository.create_with_chunks(
            DocumentCreate(
                title="review",
                source_type="institutional_access_pdf",
                source_path="review.pdf",
                file_name="review.pdf",
                file_extension=".pdf",
                content_hash="review-hash",
                raw_path="data/raw/review.pdf",
                status="imported",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="扫描版文本很少。",
                    char_count=7,
                    heading_path=None,
                    start_char=None,
                    end_char=None,
                )
            ],
        )

        provider = DeterministicEmbeddingProvider()
        first = index_candidate_chunks(db, provider, document_ids=[candidate.id])
        second = index_candidate_chunks(db, provider, document_ids=[candidate.id])
        embeddings = db.scalars(select(ChunkEmbedding)).all()
        chunks_with_embeddings = {
            db.get(Chunk, embedding.chunk_id).document_id for embedding in embeddings
        }
        review_id = review.id

    assert first.candidate_documents == 1
    assert first.indexed_chunks == 1
    assert second.skipped_chunks == 1
    assert chunks_with_embeddings == {candidate.id}
    assert review_id not in chunks_with_embeddings


def test_indexes_candidate_image_description_chunks(tmp_path: Path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        repository = DocumentRepository(db)
        document = repository.create_with_chunks(
            DocumentCreate(
                title="candidate",
                source_type="institutional_access_pdf",
                source_path="candidate.pdf",
                file_name="candidate.pdf",
                file_extension=".pdf",
                content_hash="candidate-image-hash",
                raw_path="data/raw/candidate.pdf",
                status="imported",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="普通文本 chunk。",
                    char_count=9,
                    heading_path=None,
                    start_char=None,
                    end_char=None,
                )
            ],
        )
        image_chunk = Chunk(
            document_id=document.id,
            chunk_index=1,
            content="图像描述 chunk。",
            char_count=9,
            chunk_type="image_description",
            source_image_path="data/images/1/page1_img1.png",
        )
        db.add(image_chunk)
        db.commit()

        provider = DeterministicEmbeddingProvider()
        result = index_candidate_chunks(
            db,
            provider,
            document_ids=[document.id],
            chunk_type="image_description",
        )
        embeddings = db.scalars(select(ChunkEmbedding)).all()

    assert result.indexed_chunks == 1
    assert len(embeddings) == 1


def test_read_all_document_ids_supports_all_document_image_indexing(tmp_path: Path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        repository = DocumentRepository(db)
        first = repository.create_with_chunks(
            DocumentCreate(
                title="first",
                source_type="institutional_access_pdf",
                source_path="first.pdf",
                file_name="first.pdf",
                file_extension=".pdf",
                content_hash="first-image-hash",
                raw_path="data/raw/first.pdf",
                status="imported",
            ),
            [],
        )
        second = repository.create_with_chunks(
            DocumentCreate(
                title="second",
                source_type="institutional_access_pdf",
                source_path="second.pdf",
                file_name="second.pdf",
                file_extension=".pdf",
                content_hash="second-image-hash",
                raw_path="data/raw/second.pdf",
                status="imported",
            ),
            [],
        )
        first_id = first.id
        second_id = second.id
        db.add_all(
            [
                Chunk(
                    document_id=first_id,
                    chunk_index=0,
                    content="第一张图像描述。",
                    char_count=8,
                    chunk_type="image_description",
                    source_image_path="data/images/first.png",
                ),
                Chunk(
                    document_id=second_id,
                    chunk_index=0,
                    content="第二张图像描述。",
                    char_count=8,
                    chunk_type="image_description",
                    source_image_path="data/images/second.png",
                ),
            ]
        )
        db.commit()

        document_ids = read_all_document_ids(db)
        result = index_candidate_chunks(
            db,
            DeterministicEmbeddingProvider(),
            document_ids=document_ids,
            chunk_type="image_description",
        )

    assert set(document_ids) == {first_id, second_id}
    assert result.indexed_chunks == 2
