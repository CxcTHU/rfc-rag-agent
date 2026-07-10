import csv
from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.sources import get_source_ingestion_config
from app.core.config import Settings, get_settings
from app.db.models import Base
from app.db.repositories import SourceCreate, SourceRepository
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.services.ingestion.service import IngestionConfig


@contextmanager
def make_test_client(tmp_path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "sources_api.sqlite"
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
        return IngestionConfig(raw_dir=tmp_path / "raw", chunk_size=200, chunk_overlap=20)

    def override_settings() -> Settings:
        return Settings(source_sync_allowed_roots=str(tmp_path))

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_source_ingestion_config] = override_ingestion_config
    app.dependency_overrides[get_settings] = override_settings
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def write_source_csv(path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source_id", "title", "doi", "url", "source_type", "access_rights", "abstract"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_sources_sync_list_and_detail_api(tmp_path) -> None:
    candidate_csv = tmp_path / "sources.csv"
    write_source_csv(
        candidate_csv,
        [
            {
                "source_id": "api_source_1",
                "title": "API Source Rock-Filled Concrete",
                "doi": "10.123/api",
                "url": "https://example.org/api-source",
                "source_type": "open_access_candidate",
                "access_rights": "metadata",
                "abstract": "API source abstract.",
            }
        ],
    )

    with make_test_client(tmp_path) as client:
        sync_response = client.post(
            "/sources/sync",
            json={
                "include_defaults": False,
                "candidate_csvs": [str(candidate_csv)],
            },
        )
        list_response = client.get("/sources")
        detail_response = client.get("/sources/api_source_1")

    assert sync_response.status_code == 200
    assert sync_response.json()["created"] == 1
    assert list_response.status_code == 200
    sources = list_response.json()["sources"]
    assert len(sources) == 1
    assert sources[0]["source_id"] == "api_source_1"
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "API Source Rock-Filled Concrete"


def test_sources_reindex_generates_metadata_card_and_links_document(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        seed_source(client, tmp_path)
        response = client.post(
            "/sources/reindex_source/reindex",
            json={"metadata_cards_dir": str(tmp_path / "metadata_cards")},
        )
        detail_response = client.get("/sources/reindex_source")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_id"] == "reindex_source"
    assert payload["document_id"] > 0
    assert payload["chunk_count"] >= 1
    assert payload["source_status"] == "imported"
    detail = detail_response.json()
    assert detail["status"] == "imported"
    assert detail["document_id"] == payload["document_id"]


def test_sources_reindex_returns_404_for_missing_source(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post("/sources/missing_source/reindex", json={})

    assert response.status_code == 404
    assert "missing_source" in response.json()["detail"]


def seed_source(client: TestClient, tmp_path) -> None:
    override_get_db = app.dependency_overrides[get_db]
    db_generator = override_get_db()
    db = next(db_generator)
    try:
        SourceRepository(db).create_source(
            SourceCreate(
                source_id="reindex_source",
                title="Reindex Metadata Source",
                normalized_title="reindex metadata source",
                authors="Feng Jin",
                year="2023",
                venue="Engineering",
                category="review",
                discovered_via="test",
                doi="10.123/reindex",
                normalized_doi="10.123/reindex",
                url="https://example.org/reindex",
                normalized_url="https://example.org/reindex",
                abstract="This metadata source can be reindexed into a document.",
                source_type="metadata_record",
                trust_level="high",
                access_rights="metadata",
                fulltext_permission="metadata_only",
                status="candidate",
            )
        )
    finally:
        db.close()
        try:
            next(db_generator)
        except StopIteration:
            pass
