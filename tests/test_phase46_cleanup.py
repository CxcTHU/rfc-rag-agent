import csv
import sqlite3
from pathlib import Path

from scripts.clean_phase46_decoration_empty import (
    clean_targets,
    read_targets,
    resolve_safe_image_path,
)


def test_cleanup_dry_run_does_not_delete_db_or_files(tmp_path: Path) -> None:
    db_path, image_dir, type_a, type_c = setup_cleanup_fixture(tmp_path)
    manifest = write_manifest(tmp_path, type_a, type_c)
    targets = read_targets(manifest)

    with sqlite3.connect(db_path) as connection:
        rows = clean_targets(connection, targets, image_dir=image_dir, root=tmp_path, apply=False)
        chunk_count = connection.execute("select count(1) from chunks").fetchone()[0]
        embedding_count = connection.execute("select count(1) from chunk_embeddings").fetchone()[0]

    assert {row.status for row in rows} == {"dry_run"}
    assert chunk_count == 2
    assert embedding_count == 2
    assert type_a.exists()
    assert type_c.exists()


def test_cleanup_applies_type_a_db_only_and_type_c_db_plus_file(tmp_path: Path) -> None:
    db_path, image_dir, type_a, type_c = setup_cleanup_fixture(tmp_path)
    manifest = write_manifest(tmp_path, type_a, type_c)
    targets = read_targets(manifest)

    with sqlite3.connect(db_path) as connection:
        rows = clean_targets(connection, targets, image_dir=image_dir, root=tmp_path, apply=True)
        chunk_count = connection.execute("select count(1) from chunks").fetchone()[0]
        embedding_count = connection.execute("select count(1) from chunk_embeddings").fetchone()[0]

    by_class = {row.classification: row for row in rows}
    assert by_class["type_a"].deleted_chunk == 1
    assert by_class["type_a"].deleted_embeddings == 1
    assert by_class["type_a"].deleted_file == 0
    assert by_class["type_c"].deleted_chunk == 1
    assert by_class["type_c"].deleted_embeddings == 1
    assert by_class["type_c"].deleted_file == 1
    assert chunk_count == 0
    assert embedding_count == 0
    assert type_a.exists()
    assert not type_c.exists()


def test_resolve_safe_image_path_rejects_outside_image_dir(tmp_path: Path) -> None:
    image_dir = tmp_path / "data" / "images"
    image_dir.mkdir(parents=True)

    try:
        resolve_safe_image_path("data/raw/not-image.png", image_dir=image_dir, root=tmp_path)
    except ValueError as exc:
        assert "outside image dir" in str(exc)
    else:
        raise AssertionError("outside image path should be rejected")


def setup_cleanup_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    image_dir = tmp_path / "data" / "images"
    (image_dir / "1").mkdir(parents=True)
    db_path = tmp_path / "cleanup.sqlite"
    type_a = image_dir / "1" / "page1_img1.png"
    type_c = image_dir / "1" / "page1_img2.png"
    type_a.write_bytes(b"type-a")
    type_c.write_bytes(b"type-c")
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
        connection.execute(
            "insert into chunks (id, document_id, chunk_type, source_image_path) "
            "values (1, 1, 'image_description', 'data/images/1/page1_img1.png')"
        )
        connection.execute(
            "insert into chunks (id, document_id, chunk_type, source_image_path) "
            "values (2, 1, 'image_description', 'data/images/1/page1_img2.png')"
        )
        connection.execute("insert into chunk_embeddings (id, chunk_id) values (1, 1)")
        connection.execute("insert into chunk_embeddings (id, chunk_id) values (2, 2)")
    return db_path, image_dir, type_a, type_c


def write_manifest(tmp_path: Path, type_a: Path, type_c: Path) -> Path:
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["document_id", "chunk_id", "source_image_path", "classification"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "document_id": 1,
                "chunk_id": 1,
                "source_image_path": type_a.relative_to(tmp_path).as_posix(),
                "classification": "type_a",
            }
        )
        writer.writerow(
            {
                "document_id": 1,
                "chunk_id": 2,
                "source_image_path": type_c.relative_to(tmp_path).as_posix(),
                "classification": "type_c",
            }
        )
        writer.writerow(
            {
                "document_id": 1,
                "chunk_id": 3,
                "source_image_path": "data/images/1/page1_img3.png",
                "classification": "type_b",
            }
        )
    return manifest
