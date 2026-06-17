from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import (
    ChunkCreate,
    ChunkEmbeddingCreate,
    ChunkEmbeddingRepository,
    ConversationCreate,
    ConversationRepository,
    DocumentCreate,
    DocumentRepository,
    MessageCreate,
    deserialize_embedding,
    deserialize_metadata,
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


def test_conversation_repository_creates_lists_and_appends_messages(tmp_path) -> None:
    database_path = tmp_path / "conversation_repository.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        repository = ConversationRepository(db)
        conversation = repository.create_conversation(ConversationCreate(title="新对话"))
        user_message = repository.add_message(
            message_data=MessageCreate(
                conversation_id=conversation.id,
                role="user",
                content="请解释堆石混凝土的填充性能。",
            )
        )
        assistant_message = repository.add_message(
            message_data=MessageCreate(
                conversation_id=conversation.id,
                role="assistant",
                content="填充性能主要与流动性、骨料孔隙和施工控制有关。",
                mode="agentic",
                metadata={"citations": ["[1]"], "iteration_count": 1},
            )
        )

        saved_conversation = repository.get_conversation(conversation.id)
        conversations = repository.list_conversations()
        messages = repository.list_messages(conversation.id)

    assert saved_conversation is not None
    assert saved_conversation.title == "请解释堆石混凝土的填充性能。"
    assert [item.id for item in conversations] == [conversation.id]
    assert [message.id for message in messages] == [user_message.id, assistant_message.id]
    assert messages[1].mode == "agentic"
    assert deserialize_metadata(messages[1].metadata_json) == {
        "citations": ["[1]"],
        "iteration_count": 1,
    }


def test_conversation_repository_deletes_messages_with_conversation(tmp_path) -> None:
    database_path = tmp_path / "conversation_delete.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        repository = ConversationRepository(db)
        conversation = repository.create_conversation()
        repository.add_message(
            MessageCreate(
                conversation_id=conversation.id,
                role="user",
                content="第一轮问题",
            )
        )

        deleted = repository.delete_conversation(conversation.id)
        missing_deleted = repository.delete_conversation(conversation.id)
        remaining_messages = repository.count_messages(conversation.id)

    assert deleted is True
    assert missing_deleted is False
    assert remaining_messages == 0


def test_conversation_repository_renames_conversation(tmp_path) -> None:
    database_path = tmp_path / "conversation_rename.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        repository = ConversationRepository(db)
        conversation = repository.create_conversation(ConversationCreate(title="旧标题"))
        updated = repository.rename_conversation(conversation.id, "阶段 42 新标题")
        missing = repository.rename_conversation(999, "missing")

    assert updated is not None
    assert updated.id == conversation.id
    assert updated.title == "阶段 42 新标题"
    assert updated.updated_at >= conversation.updated_at
    assert missing is None
