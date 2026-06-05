from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import (
    ChunkCreate,
    ChunkEmbeddingCreate,
    ChunkEmbeddingRepository,
    DocumentCreate,
    DocumentRepository,
    deserialize_embedding,
)
from app.db.session import create_sqlite_engine


def test_document_repository_creates_and_queries_document(tmp_path) -> None:
    database_path = tmp_path / "repository.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        repository = DocumentRepository(db)
        document = repository.create_with_chunks(
            DocumentCreate(
                title="堆石混凝土资料",
                source_type="local_file",
                source_path="sample.md",
                file_name="sample.md",
                file_extension=".md",
                content_hash="repository-hash",
                raw_path="data/raw/repository-hash.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="堆石混凝土概念。",
                    char_count=8,
                    heading_path="概念",
                    start_char=0,
                    end_char=8,
                )
            ],
        )

        saved_document = repository.get_by_content_hash("repository-hash")
        documents = repository.list_documents()
        chunk_count = repository.count_chunks(document.id)

    assert saved_document is not None
    assert saved_document.id == document.id
    assert [item.title for item in documents] == ["堆石混凝土资料"]
    assert chunk_count == 1


def test_chunk_embedding_repository_saves_and_queries_embedding(tmp_path) -> None:
    database_path = tmp_path / "repository_embedding.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        document_repository = DocumentRepository(db)
        document = document_repository.create_with_chunks(
            DocumentCreate(
                title="堆石混凝土温控资料",
                source_type="local_file",
                source_path="thermal.md",
                file_name="thermal.md",
                file_extension=".md",
                content_hash="thermal-hash",
                raw_path="data/raw/thermal.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="堆石混凝土温升控制需要关注水化热。",
                    char_count=18,
                    heading_path="温控",
                    start_char=0,
                    end_char=18,
                )
            ],
        )
        chunk = document_repository.list_chunks(document.id)[0]
        embedding_repository = ChunkEmbeddingRepository(db)

        saved_embedding = embedding_repository.save_embedding(
            ChunkEmbeddingCreate(
                chunk_id=chunk.id,
                provider="deterministic",
                model_name="hash-token-v1",
                dimension=4,
                embedding=[0.1, 0.2, 0.3, 0.4],
                content_hash="chunk-hash-v1",
            )
        )
        queried_embedding = embedding_repository.get_embedding(
            chunk_id=chunk.id,
            provider="deterministic",
            model_name="hash-token-v1",
        )
        embeddings = embedding_repository.list_embeddings(provider="deterministic")
        embedding_count = embedding_repository.count_embeddings(provider="deterministic")

    assert queried_embedding is not None
    assert queried_embedding.id == saved_embedding.id
    assert queried_embedding.dimension == 4
    assert deserialize_embedding(queried_embedding.embedding_json) == [0.1, 0.2, 0.3, 0.4]
    assert [embedding.id for embedding in embeddings] == [saved_embedding.id]
    assert embedding_count == 1


def test_chunk_embedding_repository_updates_existing_embedding(tmp_path) -> None:
    database_path = tmp_path / "repository_embedding_update.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        document_repository = DocumentRepository(db)
        document = document_repository.create_with_chunks(
            DocumentCreate(
                title="堆石混凝土弹性模量资料",
                source_type="metadata_record",
                source_path="elastic.md",
                file_name="elastic.md",
                file_extension=".md",
                content_hash="elastic-hash",
                raw_path="data/raw/elastic.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="The elastic modulus of rock-filled concrete was reviewed.",
                    char_count=60,
                    heading_path="Abstract",
                    start_char=0,
                    end_char=60,
                )
            ],
        )
        chunk = document_repository.list_chunks(document.id)[0]
        embedding_repository = ChunkEmbeddingRepository(db)

        first_embedding = embedding_repository.save_embedding(
            ChunkEmbeddingCreate(
                chunk_id=chunk.id,
                provider="deterministic",
                model_name="hash-token-v1",
                dimension=2,
                embedding=[1.0, 0.0],
                content_hash="chunk-hash-v1",
            )
        )
        updated_embedding = embedding_repository.save_embedding(
            ChunkEmbeddingCreate(
                chunk_id=chunk.id,
                provider="deterministic",
                model_name="hash-token-v1",
                dimension=2,
                embedding=[0.0, 1.0],
                content_hash="chunk-hash-v2",
            )
        )
        embedding_count = embedding_repository.count_embeddings()

    assert updated_embedding.id == first_embedding.id
    assert deserialize_embedding(updated_embedding.embedding_json) == [0.0, 1.0]
    assert updated_embedding.content_hash == "chunk-hash-v2"
    assert embedding_count == 1
