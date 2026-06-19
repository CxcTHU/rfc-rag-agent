from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine


def test_chunk_model_defaults_to_text_chunk_type(tmp_path) -> None:
    database_path = tmp_path / "chunk-default.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        repository = DocumentRepository(db)
        document = repository.create_with_chunks(
            DocumentCreate(
                title="默认文本 chunk",
                source_type="local_file",
                source_path="text.md",
                file_name="text.md",
                file_extension=".md",
                content_hash="stage45-text-chunk",
                raw_path="data/raw/stage45-text-chunk.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="普通文本片段。",
                    char_count=7,
                    heading_path="概念",
                    start_char=0,
                    end_char=7,
                )
            ],
        )
        chunk = repository.list_chunks(document.id)[0]

    assert chunk.chunk_type == "text"
    assert chunk.source_image_path is None


def test_repository_can_create_image_description_chunk(tmp_path) -> None:
    database_path = tmp_path / "chunk-image.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        repository = DocumentRepository(db)
        document = repository.create_with_chunks(
            DocumentCreate(
                title="图表描述 chunk",
                source_type="open_access_pdf",
                source_path="figure.pdf",
                file_name="figure.pdf",
                file_extension=".pdf",
                content_hash="stage45-image-chunk",
                raw_path="data/raw/stage45-image-chunk.pdf",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="图表显示堆石混凝土强度随龄期增长。",
                    char_count=18,
                    heading_path="试验结果 > [图表]",
                    start_char=None,
                    end_char=None,
                    chunk_type="image_description",
                    source_image_path="data/images/1/page1_img1.png",
                )
            ],
        )

    with TestingSessionLocal() as db:
        chunk = db.scalar(select(Chunk).where(Chunk.document_id == document.id))

    assert chunk is not None
    assert chunk.chunk_type == "image_description"
    assert chunk.source_image_path == "data/images/1/page1_img1.png"


def test_stage45_alembic_migration_declares_multimodal_chunk_columns() -> None:
    migration = Path("alembic/versions/20260618_0002_chunk_multimodal_fields.py").read_text(
        encoding="utf-8"
    )

    assert '"chunk_type"' in migration
    assert '"source_image_path"' in migration
    assert 'server_default="text"' in migration
    assert "ix_chunks_chunk_type" in migration
