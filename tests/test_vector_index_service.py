from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, Document
from app.db.repositories import (
    ChunkCreate,
    ChunkEmbeddingRepository,
    DocumentCreate,
    DocumentRepository,
    deserialize_embedding,
)
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService, calculate_text_hash


def make_session(tmp_path):
    database_path = tmp_path / "vector_index.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_document_with_chunks(db):
    repository = DocumentRepository(db)
    document = repository.create_with_chunks(
        DocumentCreate(
            title="堆石混凝土向量索引资料",
            source_type="local_file",
            source_path="vector.md",
            file_name="vector.md",
            file_extension=".md",
            content_hash="vector-document-hash",
            raw_path="data/raw/vector.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="堆石混凝土温升控制需要关注水化热。",
                char_count=18,
                heading_path="温控",
                start_char=0,
                end_char=18,
            ),
            ChunkCreate(
                chunk_index=1,
                content="Self-compacting concrete should fill the rock voids.",
                char_count=55,
                heading_path="Filling",
                start_char=19,
                end_char=74,
            ),
        ],
    )
    return document


def test_vector_index_service_builds_embeddings_for_chunks(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        document = seed_document_with_chunks(db)
        provider = DeterministicEmbeddingProvider(dimension=16)
        result = VectorIndexService(db, provider).build_index(batch_size=1)
        embedding_repository = ChunkEmbeddingRepository(db)
        embeddings = embedding_repository.list_embeddings(
            provider=provider.provider_name,
            model_name=provider.model_name,
        )
        chunks = DocumentRepository(db).list_chunks(document.id)

    assert result.total_chunks == 2
    assert result.indexed_chunks == 2
    assert result.updated_chunks == 0
    assert result.skipped_chunks == 0
    assert len(embeddings) == 2
    assert embeddings[0].dimension == 16
    assert embeddings[0].content_hash == calculate_text_hash(chunks[0].content)
    assert len(deserialize_embedding(embeddings[0].embedding_json)) == 16


def test_vector_index_service_skips_unchanged_embeddings(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_document_with_chunks(db)
        provider = DeterministicEmbeddingProvider(dimension=8)
        first_result = VectorIndexService(db, provider).build_index()
        second_result = VectorIndexService(db, provider).build_index()

    assert first_result.indexed_chunks == 2
    assert second_result.indexed_chunks == 0
    assert second_result.updated_chunks == 0
    assert second_result.skipped_chunks == 2


def test_vector_index_service_updates_stale_embedding_when_chunk_changes(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        document = seed_document_with_chunks(db)
        provider = DeterministicEmbeddingProvider(dimension=8)
        VectorIndexService(db, provider).build_index()

        chunk = DocumentRepository(db).list_chunks(document.id)[0]
        original_hash = calculate_text_hash(chunk.content)
        chunk.content = "堆石混凝土温控还需要关注绝热温升。"
        db.commit()

        result = VectorIndexService(db, provider).build_index()
        saved_embedding = ChunkEmbeddingRepository(db).get_embedding(
            chunk_id=chunk.id,
            provider=provider.provider_name,
            model_name=provider.model_name,
        )

    assert result.indexed_chunks == 0
    assert result.updated_chunks == 1
    assert result.skipped_chunks == 1
    assert saved_embedding is not None
    assert saved_embedding.content_hash != original_hash
    assert saved_embedding.content_hash == calculate_text_hash("堆石混凝土温控还需要关注绝热温升。")


def test_vector_index_service_respects_limit(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_document_with_chunks(db)
        provider = DeterministicEmbeddingProvider(dimension=8)
        result = VectorIndexService(db, provider).build_index(limit=1)

    assert result.total_chunks == 1
    assert result.indexed_chunks == 1


def test_vector_index_service_skips_parent_chunks_with_children(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        document = Document(
            title="父子块向量索引资料",
            source_type="local_file",
            source_path="parent-child.md",
            file_name="parent-child.md",
            file_extension=".md",
            content_hash="parent-child-vector-document-hash",
            raw_path="data/raw/parent-child.md",
        )
        parent = Chunk(
            document=document,
            chunk_index=0,
            content="父块只提供完整上下文，不应该生成 embedding。",
            char_count=24,
            heading_path="父块",
            start_char=0,
            end_char=24,
        )
        child = Chunk(
            document=document,
            chunk_index=1,
            content="子块用于精准召回，需要生成 embedding。",
            char_count=21,
            heading_path="父块",
            start_char=0,
            end_char=21,
            parent_chunk=parent,
        )
        standalone = Chunk(
            document=document,
            chunk_index=2,
            content="旧普通块没有子块，也需要继续生成 embedding。",
            char_count=23,
            heading_path="旧数据",
            start_char=25,
            end_char=48,
        )
        db.add_all([document, parent, child, standalone])
        db.commit()

        provider = DeterministicEmbeddingProvider(dimension=8)
        result = VectorIndexService(db, provider).build_index()
        parent_embedding = ChunkEmbeddingRepository(db).get_embedding(
            chunk_id=parent.id,
            provider=provider.provider_name,
            model_name=provider.model_name,
        )
        child_embedding = ChunkEmbeddingRepository(db).get_embedding(
            chunk_id=child.id,
            provider=provider.provider_name,
            model_name=provider.model_name,
        )
        standalone_embedding = ChunkEmbeddingRepository(db).get_embedding(
            chunk_id=standalone.id,
            provider=provider.provider_name,
            model_name=provider.model_name,
        )

    assert result.total_chunks == 2
    assert result.indexed_chunks == 2
    assert parent_embedding is None
    assert child_embedding is not None
    assert standalone_embedding is not None


def test_vector_index_service_rejects_invalid_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=8)
        service = VectorIndexService(db, provider)

        try:
            service.build_index(limit=0)
        except ValueError as exc:
            assert "limit" in str(exc)
        else:
            raise AssertionError("Expected ValueError for invalid limit")

        try:
            service.build_index(batch_size=0)
        except ValueError as exc:
            assert "batch_size" in str(exc)
        else:
            raise AssertionError("Expected ValueError for invalid batch_size")
