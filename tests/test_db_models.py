from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, Document
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
