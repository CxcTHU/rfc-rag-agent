from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, Document
from app.db.session import create_sqlite_engine
from app.services.ingestion.service import (
    EmptyDocumentError,
    IngestionConfig,
    IngestionService,
)


def make_session(tmp_path):
    database_path = tmp_path / "ingestion.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_ingestion_service_imports_markdown_into_documents_and_chunks(tmp_path) -> None:
    source_file = tmp_path / "rfc.md"
    source_file.write_text(
        "# 堆石混凝土概念\n\n"
        "堆石混凝土由大粒径堆石体和自密实混凝土组成。"
        "施工质量控制需要关注填充密实性、材料级配和浇筑过程。\n\n"
        "## 施工\n\n"
        "施工阶段应保证自密实混凝土能够充分填充堆石体空隙。",
        encoding="utf-8",
    )
    raw_dir = tmp_path / "raw"
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        service = IngestionService(
            db,
            IngestionConfig(raw_dir=raw_dir, chunk_size=45, chunk_overlap=8),
        )
        result = service.import_document(source_file)

        document = db.get(Document, result.document_id)
        chunks = db.scalars(
            select(Chunk)
            .where(Chunk.document_id == result.document_id)
            .order_by(Chunk.chunk_index)
        ).all()

    assert result.status == "imported"
    assert result.title == "堆石混凝土概念"
    assert result.chunk_count >= 2
    assert Path(result.raw_path).exists()
    assert document is not None
    assert document.content_hash == result.content_hash
    assert document.raw_path == result.raw_path
    assert len(chunks) == result.chunk_count
    assert chunks[0].heading_path == "堆石混凝土概念"
    assert any("施工质量控制" in chunk.content for chunk in chunks)


def test_ingestion_service_returns_duplicate_for_same_file(tmp_path) -> None:
    source_file = tmp_path / "duplicate.txt"
    source_file.write_text("堆石混凝土资料可以用于关键词检索。", encoding="utf-8")
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        service = IngestionService(db, IngestionConfig(raw_dir=tmp_path / "raw"))

        first_result = service.import_document(source_file)
        second_result = service.import_document(source_file)

        documents = db.scalars(select(Document)).all()

    assert first_result.status == "imported"
    assert second_result.status == "duplicate"
    assert second_result.document_id == first_result.document_id
    assert len(documents) == 1


def test_ingestion_service_can_store_custom_source_type(tmp_path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("Rock-filled concrete full text.", encoding="utf-8")
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        service = IngestionService(db, IngestionConfig(raw_dir=tmp_path / "raw"))
        result = service.import_document(source_file, source_type="open_access_pdf")
        document = db.get(Document, result.document_id)

    assert document is not None
    assert document.source_type == "open_access_pdf"


def test_ingestion_service_rejects_blank_document(tmp_path) -> None:
    source_file = tmp_path / "blank.txt"
    source_file.write_text(" \n\n\t ", encoding="utf-8")
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        service = IngestionService(db, IngestionConfig(raw_dir=tmp_path / "raw"))

        with pytest.raises(EmptyDocumentError):
            service.import_document(source_file)
