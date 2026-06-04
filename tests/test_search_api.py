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
    database_path = tmp_path / "search_api.sqlite"
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
        return IngestionConfig(raw_dir=tmp_path / "raw", chunk_size=50, chunk_overlap=8)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ingestion_config] = override_ingestion_config
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_search_api_returns_matching_chunks_after_import(tmp_path) -> None:
    markdown_content = (
        "# 堆石混凝土施工质量\n\n"
        "堆石混凝土施工质量控制需要关注填充密实性和材料级配。\n\n"
        "## 材料\n\n"
        "自密实混凝土应充分填充堆石体空隙。"
    )

    with make_test_client(tmp_path) as client:
        import_response = client.post(
            "/documents/import",
            files={"file": ("quality.md", markdown_content.encode("utf-8"), "text/markdown")},
        )
        search_response = client.post(
            "/search",
            json={"query": "施工质量", "top_k": 3},
        )

    assert import_response.status_code == 200
    assert search_response.status_code == 200

    payload = search_response.json()
    assert payload["query"] == "施工质量"
    assert payload["top_k"] == 3
    assert len(payload["results"]) >= 1
    assert payload["results"][0]["document_title"] == "堆石混凝土施工质量"
    assert payload["results"][0]["file_name"] == "quality.md"
    assert payload["results"][0]["source_path"] == "quality.md"
    assert "施工质量" in payload["results"][0]["content"]
    assert payload["results"][0]["score"] > 0


def test_search_api_returns_empty_results_for_no_match(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post("/search", json={"query": "未导入内容", "top_k": 5})

    assert response.status_code == 200
    assert response.json()["results"] == []
