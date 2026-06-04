from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.documents import get_ingestion_config
from app.db.models import Base
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.services.ingestion.service import IngestionConfig


@contextmanager
def make_test_client(tmp_path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "documents_api.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_ingestion_config() -> IngestionConfig:
        return IngestionConfig(raw_dir=tmp_path / "raw", chunk_size=45, chunk_overlap=8)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ingestion_config] = override_ingestion_config
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_import_document_api_and_list_documents(tmp_path) -> None:
    markdown_content = (
        "# 堆石混凝土概念\n\n"
        "堆石混凝土由大粒径堆石体和自密实混凝土组成。"
        "施工质量控制需要关注填充密实性、材料级配和浇筑过程。"
    )

    with make_test_client(tmp_path) as client:
        import_response = client.post(
            "/documents/import",
            files={"file": ("rfc.md", markdown_content.encode("utf-8"), "text/markdown")},
        )
        list_response = client.get("/documents")

    assert import_response.status_code == 200
    imported = import_response.json()
    assert imported["title"] == "堆石混凝土概念"
    assert imported["status"] == "imported"
    assert imported["chunk_count"] >= 1

    assert list_response.status_code == 200
    documents = list_response.json()["documents"]
    assert len(documents) == 1
    assert documents[0]["title"] == "堆石混凝土概念"
    assert documents[0]["file_name"] == "rfc.md"
    assert documents[0]["chunk_count"] == imported["chunk_count"]


def test_list_document_chunks_api_returns_imported_chunks(tmp_path) -> None:
    markdown_content = (
        "# 堆石混凝土施工质量\n\n"
        "堆石混凝土施工质量控制需要关注填充密实性。\n\n"
        "自密实混凝土应充分填充堆石体空隙，避免堵塞、离析和孔洞残留。"
    )

    with make_test_client(tmp_path) as client:
        import_response = client.post(
            "/documents/import",
            files={"file": ("quality.md", markdown_content.encode("utf-8"), "text/markdown")},
        )
        document_id = import_response.json()["document_id"]
        chunks_response = client.get(f"/documents/{document_id}/chunks")

    assert chunks_response.status_code == 200
    payload = chunks_response.json()
    assert payload["document_id"] == document_id
    assert payload["title"] == "堆石混凝土施工质量"
    assert payload["file_name"] == "quality.md"
    assert payload["chunk_count"] == len(payload["chunks"])
    assert payload["chunk_count"] >= 1
    assert payload["chunks"][0]["chunk_index"] == 0
    assert "填充密实性" in payload["chunks"][0]["content"]
    assert "char_count" in payload["chunks"][0]
    assert "created_at" in payload["chunks"][0]


def test_list_document_chunks_api_returns_404_for_missing_document(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.get("/documents/999/chunks")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document 999 was not found."


def test_import_document_api_rejects_unsupported_file(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/documents/import",
            files={
                "file": (
                    "sample.docx",
                    b"not supported",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]
