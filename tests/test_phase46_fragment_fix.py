import csv
import sqlite3
from pathlib import Path

from app.services.ingestion.image_extractor import ExtractedPdfImage
from scripts.fix_phase46_fragment_images import (
    fix_documents,
    read_type_b_chunk_ids,
)


class FakeExtractor:
    def extract_images_page_render(self, pdf_path: Path, document_id: int):
        return [ExtractedPdfImage(1, f"data/images/{document_id}/page1_render1.png", 300, 200)]


def test_read_type_b_chunk_ids_filters_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["document_id", "chunk_id", "classification"])
        writer.writeheader()
        writer.writerow({"document_id": 10, "chunk_id": 1, "classification": "type_b"})
        writer.writerow({"document_id": 10, "chunk_id": 2, "classification": "type_a"})
        writer.writerow({"document_id": 11, "chunk_id": 3, "classification": "type_b"})

    result = read_type_b_chunk_ids(manifest, {10})

    assert result == {10: [1]}


def test_fix_documents_dry_run_and_apply(tmp_path: Path) -> None:
    db_path = tmp_path / "fragment.sqlite"
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-placeholder")
    with sqlite3.connect(db_path) as connection:
        create_schema(connection)
        connection.execute(
            "insert into documents (id, title, raw_path) values (10, 'doc ten', 'doc.pdf')"
        )
        connection.execute(
            "insert into chunks (id, document_id, chunk_type) values (1, 10, 'image_description')"
        )
        connection.execute("insert into chunk_embeddings (id, chunk_id) values (1, 1)")
        dry_run = fix_documents(
            connection,
            [10],
            {10: [1]},
            extractor=FakeExtractor(),
            root=tmp_path,
            apply=False,
        )
        chunk_count_after_dry_run = connection.execute("select count(1) from chunks").fetchone()[0]
        applied = fix_documents(
            connection,
            [10],
            {10: [1]},
            extractor=FakeExtractor(),
            root=tmp_path,
            apply=True,
        )
        chunk_count_after_apply = connection.execute("select count(1) from chunks").fetchone()[0]
        embedding_count_after_apply = connection.execute("select count(1) from chunk_embeddings").fetchone()[0]

    assert dry_run[0].status == "dry_run"
    assert chunk_count_after_dry_run == 1
    assert applied[0].status == "fixed"
    assert applied[0].rendered_images == 1
    assert applied[0].deleted_chunks == 1
    assert applied[0].deleted_embeddings == 1
    assert chunk_count_after_apply == 0
    assert embedding_count_after_apply == 0


def create_schema(connection: sqlite3.Connection) -> None:
    connection.execute("create table documents (id integer primary key, title text, raw_path text)")
    connection.execute("create table chunks (id integer primary key, document_id integer, chunk_type text)")
    connection.execute("create table chunk_embeddings (id integer primary key, chunk_id integer)")
