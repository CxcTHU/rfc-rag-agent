import csv

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import (
    ChunkCreate,
    DocumentCreate,
    DocumentRepository,
    SourceCreate,
    SourceRepository,
)
from app.db.session import create_sqlite_engine
from scripts.evaluate_sources import collect_source_metrics, format_metrics, write_metrics


def make_session(tmp_path):
    database_path = tmp_path / "evaluate_sources.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_source(source_id: str, **overrides) -> SourceCreate:
    data = {
        "source_id": source_id,
        "title": f"Source {source_id}",
        "normalized_title": f"source {source_id}",
        "source_type": "metadata_record",
        "trust_level": "medium",
        "access_rights": "metadata",
        "fulltext_permission": "metadata_only",
        "status": "candidate",
        "notes": None,
    }
    data.update(overrides)
    return SourceCreate(**data)


def test_collect_source_metrics_counts_governance_fields(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        document = DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Imported source document",
                source_type="metadata_record",
                source_path="https://example.org/imported",
                file_name="imported.md",
                file_extension=".md",
                content_hash="source-metrics-doc-hash",
                raw_path="data/raw/imported.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="Imported source content.",
                    char_count=24,
                    heading_path="Abstract",
                    start_char=0,
                    end_char=24,
                )
            ],
        )
        repository = SourceRepository(db)
        repository.create_source(
            make_source(
                "source_1",
                status="imported",
                trust_level="high",
                fulltext_permission="open_access",
                document_id=document.id,
            )
        )
        repository.create_source(
            make_source(
                "source_2",
                status="collected",
                fulltext_permission="institutional_access",
                notes="merged_duplicate_source_id=source_2_dup",
            )
        )

        metrics = collect_source_metrics(db)

    assert metrics.total_sources == 2
    assert metrics.linked_documents == 1
    assert metrics.merged_duplicates == 1
    assert metrics.status_counts == {"collected": 1, "imported": 1}
    assert metrics.permission_counts == {"institutional_access": 1, "open_access": 1}
    assert metrics.trust_counts == {"high": 1, "medium": 1}
    assert "total_sources=2" in format_metrics(metrics)


def test_write_metrics_outputs_explorable_csv(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    output_path = tmp_path / "source_registry_metrics.csv"

    with TestingSessionLocal() as db:
        SourceRepository(db).create_source(make_source("source_1"))
        metrics = collect_source_metrics(db)
    write_metrics(output_path, metrics)

    with output_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert {"scope": "summary", "key": "total_sources", "value": "1"} in rows
    assert {"scope": "status", "key": "candidate", "value": "1"} in rows
