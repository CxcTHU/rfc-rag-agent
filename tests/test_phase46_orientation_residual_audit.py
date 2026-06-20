import csv
import sqlite3
from pathlib import Path

from scripts.audit_phase46_orientation_residuals import (
    audit_orientation_rows,
    load_cleanup_report,
    load_db_image_info,
    load_manifest,
    load_phase45_rows,
    summarize,
)


def test_retry_report_overrides_same_orientation_path(tmp_path: Path) -> None:
    all_review = tmp_path / "all.csv"
    retry = tmp_path / "retry.csv"
    write_phase45_report(
        all_review,
        [
            {
                "chunk_id": 1,
                "document_id": 10,
                "source_image_path": "data/images/10/page1_img1.png",
                "status": "failed",
                "reason": "orientation_review",
            }
        ],
    )
    write_phase45_report(
        retry,
        [
            {
                "chunk_id": 2,
                "document_id": 10,
                "source_image_path": "data/images/10/page1_img1.png",
                "status": "fixed",
                "reason": "retry",
            }
        ],
    )

    rows = load_phase45_rows(all_review, [retry])

    assert len(rows) == 1
    assert rows[0].chunk_id == 2
    assert rows[0].phase45_status == "fixed"


def test_failed_type_a_without_current_embedding_is_cleanup_resolved(tmp_path: Path) -> None:
    rows, manifest, cleanup, db_path = setup_audit_fixture(tmp_path, classification="type_a", with_db_chunk=False)

    with sqlite3.connect(db_path) as connection:
        audit_rows = audit_orientation_rows(
            rows,
            load_manifest(manifest),
            load_cleanup_report(cleanup),
            load_db_image_info(connection),
        )

    assert audit_rows[0].final_status == "resolved_by_cleanup"
    assert audit_rows[0].audit_reason == "phase46_type_a_cleanup_removed_chunk_embedding"
    assert summarize(audit_rows)["cleanup_resolved"] == 1


def test_failed_non_type_a_with_chunk_embedding_is_still_candidate(tmp_path: Path) -> None:
    rows, manifest, cleanup, db_path = setup_audit_fixture(tmp_path, classification="normal", with_db_chunk=True)

    with sqlite3.connect(db_path) as connection:
        audit_rows = audit_orientation_rows(
            rows,
            load_manifest(manifest),
            load_cleanup_report(cleanup),
            load_db_image_info(connection),
        )

    assert audit_rows[0].final_status == "still_candidate"
    assert audit_rows[0].current_chunk_count == 1
    assert audit_rows[0].current_embedding_count == 1
    assert summarize(audit_rows)["still_candidate"] == 1


def test_fixed_phase45_rows_remain_fixed_even_if_chunk_exists(tmp_path: Path) -> None:
    rows, manifest, cleanup, db_path = setup_audit_fixture(
        tmp_path,
        classification="normal",
        with_db_chunk=True,
        phase45_status="fixed",
    )

    with sqlite3.connect(db_path) as connection:
        audit_rows = audit_orientation_rows(
            rows,
            load_manifest(manifest),
            load_cleanup_report(cleanup),
            load_db_image_info(connection),
        )

    assert audit_rows[0].final_status == "fixed"
    assert summarize(audit_rows)["fixed"] == 1


def setup_audit_fixture(
    tmp_path: Path,
    *,
    classification: str,
    with_db_chunk: bool,
    phase45_status: str = "failed",
):
    report = tmp_path / "phase45.csv"
    manifest = tmp_path / "manifest.csv"
    cleanup = tmp_path / "cleanup.csv"
    db_path = tmp_path / "audit.sqlite"
    source_image_path = "data/images/421/page3_img1.png"
    write_phase45_report(
        report,
        [
            {
                "chunk_id": 7,
                "document_id": 421,
                "source_image_path": source_image_path,
                "status": phase45_status,
                "reason": "orientation_review:sideways",
            }
        ],
    )
    write_manifest(manifest, source_image_path, classification)
    write_cleanup(cleanup, source_image_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            create table chunks (
                id integer primary key,
                document_id integer,
                chunk_type text,
                source_image_path text
            )
            """
        )
        connection.execute("create table chunk_embeddings (id integer primary key, chunk_id integer)")
        if with_db_chunk:
            connection.execute(
                "insert into chunks (id, document_id, chunk_type, source_image_path) "
                "values (99, 421, 'image_description', ?)",
                (source_image_path,),
            )
            connection.execute("insert into chunk_embeddings (id, chunk_id) values (1, 99)")
    return load_phase45_rows(report, []), manifest, cleanup, db_path


def write_phase45_report(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["chunk_id", "document_id", "source_image_path", "status", "reason", "backup_path", "error"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "backup_path": "", "error": ""})


def write_manifest(path: Path, source_image_path: str, classification: str) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["source_image_path", "classification", "chunk_id", "embedding_count"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_image_path": source_image_path,
                "classification": classification,
                "chunk_id": 7,
                "embedding_count": 1,
            }
        )


def write_cleanup(path: Path, source_image_path: str) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["source_image_path", "status", "deleted_chunk", "deleted_embeddings"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_image_path": source_image_path,
                "status": "cleaned",
                "deleted_chunk": 1,
                "deleted_embeddings": 1,
            }
        )
