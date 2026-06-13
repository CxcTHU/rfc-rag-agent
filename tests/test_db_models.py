from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, ChunkEmbedding, Conversation, Document, Message
from app.db.session import create_sqlite_engine


def test_document_and_chunks_can_be_persisted(tmp_path) -> None:
    database_path = tmp_path / "test.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        document = Document(
            title="堆石混凝土施工资料",
            source_type="local_file",
            source_path="sample.md",
            file_name="sample.md",
            file_extension=".md",
            content_hash="sample-hash",
            raw_path="data/raw/sample.md",
            status="imported",
            chunks=[
                Chunk(
                    chunk_index=0,
                    content="堆石混凝土由大粒径堆石体和自密实混凝土组成。",
                    char_count=25,
                    heading_path="概念",
                    start_char=0,
                    end_char=25,
                ),
                Chunk(
                    chunk_index=1,
                    content="施工质量控制需要关注填充密实性和材料级配。",
                    char_count=22,
                    heading_path="施工质量",
                    start_char=26,
                    end_char=48,
                ),
            ],
        )
        db.add(document)
        db.commit()
        document_id = document.id

    with TestingSessionLocal() as db:
        saved_document = db.get(Document, document_id)
        saved_chunks = db.scalars(
            select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
        ).all()

    assert saved_document is not None
    assert saved_document.title == "堆石混凝土施工资料"
    assert saved_document.content_hash == "sample-hash"
    assert [chunk.chunk_index for chunk in saved_chunks] == [0, 1]
    assert saved_chunks[0].content.startswith("堆石混凝土")


def test_chunk_embedding_can_be_persisted(tmp_path) -> None:
    database_path = tmp_path / "test_embedding.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        document = Document(
            title="堆石混凝土向量资料",
            source_type="local_file",
            source_path="sample.md",
            file_name="sample.md",
            file_extension=".md",
            content_hash="sample-embedding-hash",
            raw_path="data/raw/sample.md",
            status="imported",
            chunks=[
                Chunk(
                    chunk_index=0,
                    content="堆石混凝土温升控制。",
                    char_count=10,
                    heading_path="温控",
                    start_char=0,
                    end_char=10,
                )
            ],
        )
        db.add(document)
        db.commit()
        chunk_id = document.chunks[0].id

        chunk_embedding = ChunkEmbedding(
            chunk_id=chunk_id,
            provider="deterministic",
            model_name="hash-token-v1",
            dimension=3,
            embedding_json="[0.1,0.2,0.3]",
            content_hash="chunk-content-hash",
        )
        db.add(chunk_embedding)
        db.commit()
        embedding_id = chunk_embedding.id

    with TestingSessionLocal() as db:
        saved_embedding = db.get(ChunkEmbedding, embedding_id)

    assert saved_embedding is not None
    assert saved_embedding.chunk_id == chunk_id
    assert saved_embedding.provider == "deterministic"
    assert saved_embedding.model_name == "hash-token-v1"
    assert saved_embedding.dimension == 3
    assert saved_embedding.content_hash == "chunk-content-hash"


def test_parent_child_chunks_can_be_persisted(tmp_path) -> None:
    database_path = tmp_path / "test_parent_child.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        document = Document(
            title="父子块资料",
            source_type="local_file",
            source_path="parent-child.md",
            file_name="parent-child.md",
            file_extension=".md",
            content_hash="parent-child-hash",
            raw_path="data/raw/parent-child.md",
            status="imported",
        )
        parent = Chunk(
            chunk_index=0,
            content="父块保存更完整的施工质量上下文。",
            char_count=17,
            heading_path="施工质量",
            start_char=0,
            end_char=17,
        )
        child = Chunk(
            chunk_index=1,
            content="子块用于精准召回。",
            char_count=9,
            heading_path="施工质量",
            start_char=0,
            end_char=9,
            parent_chunk=parent,
        )
        document.chunks = [parent, child]
        db.add(document)
        db.commit()
        child_id = child.id

    with TestingSessionLocal() as db:
        saved_child = db.get(Chunk, child_id)
        assert saved_child is not None
        assert saved_child.parent_chunk is not None
        assert saved_child.parent_chunk.content.startswith("父块保存")
        assert [chunk.content for chunk in saved_child.parent_chunk.child_chunks] == ["子块用于精准召回。"]


def test_conversation_and_messages_can_be_persisted(tmp_path) -> None:
    database_path = tmp_path / "test_conversation.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        conversation = Conversation(
            title="填充性能追问",
            messages=[
                Message(role="user", content="什么影响填充性能？"),
                Message(
                    role="assistant",
                    content="填充性能受自密实混凝土流动性和堆石孔隙影响。",
                    mode="default",
                    metadata_json='{"citations":["[1]"]}',
                ),
                Message(role="summary", content="用户正在了解填充性能影响因素。"),
            ],
        )
        db.add(conversation)
        db.commit()
        conversation_id = conversation.id

    with TestingSessionLocal() as db:
        saved_conversation = db.get(Conversation, conversation_id)
        saved_messages = db.query(Message).filter_by(conversation_id=conversation_id).all()

    assert saved_conversation is not None
    assert saved_conversation.title == "填充性能追问"
    assert [message.role for message in saved_messages] == ["user", "assistant", "summary"]
    assert saved_messages[1].mode == "default"
    assert saved_messages[1].metadata_json == '{"citations":["[1]"]}'
