import csv
import sqlite3
import struct
import zlib
from pathlib import Path

from scripts.classify_phase46_problem_images import (
    build_inventory,
    classify_rows,
    write_manifest,
)


def test_classifies_type_c_type_a_type_b_and_normal_images(tmp_path: Path) -> None:
    rows = [
        make_row(1, "data/images/1/page1_img1.png", size=0, width=0, height=0),
        make_row(1, "data/images/1/page1_img2.png", size=4000, width=80, height=120),
        make_row(2, "data/images/2/page1_img1.png", size=6000, width=40, height=160),
        make_row(2, "data/images/2/page1_img2.png", size=6000, width=120, height=120),
        make_row(2, "data/images/2/page1_img3.png", size=6000, width=120, height=120),
        make_row(3, "data/images/3/page1_img1.png", size=6000, width=90, height=90),
        make_row(3, "data/images/3/page2_img1.png", size=6000, width=90, height=90),
        make_row(3, "data/images/3/page3_img1.png", size=6000, width=90, height=90),
        make_row(4, "data/images/4/page1_img1.png", size=6000, width=120, height=120),
    ]

    classified = classify_rows(
        rows,
        small_file_bytes=5 * 1024,
        small_dimension=100,
        decoration_page_threshold=3,
        fragment_page_image_threshold=3,
        fragment_aspect_ratio=3.0,
    )
    by_path = {row.source_image_path: row for row in classified}

    assert by_path["data/images/1/page1_img1.png"].classification == "type_c"
    assert by_path["data/images/1/page1_img2.png"].classification == "type_c"
    assert by_path["data/images/2/page1_img1.png"].classification == "type_b"
    assert by_path["data/images/2/page1_img2.png"].classification == "type_b"
    assert by_path["data/images/3/page1_img1.png"].classification == "type_a"
    assert by_path["data/images/4/page1_img1.png"].classification == "normal"


def test_build_inventory_merges_db_chunks_and_disk_only_images(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    image_dir = root / "data" / "images"
    (image_dir / "10").mkdir(parents=True)
    (image_dir / "11").mkdir(parents=True)
    (image_dir / "10" / "page1_img1.png").write_bytes(make_png_bytes(120, 90))
    (image_dir / "11" / "page2_img1.png").write_bytes(make_png_bytes(80, 80))

    db_path = tmp_path / "phase46.sqlite"
    with sqlite3.connect(db_path) as connection:
        create_schema(connection)
        connection.execute("insert into documents (id, title) values (10, 'doc ten')")
        connection.execute(
            "insert into chunks (id, document_id, chunk_index, chunk_type, source_image_path) "
            "values (5, 10, 99, 'image_description', 'data/images/10/page1_img1.png')"
        )
        connection.execute("insert into chunk_embeddings (id, chunk_id) values (1, 5)")
        rows = build_inventory(connection, image_dir, root)

    by_path = {row.source_image_path: row for row in rows}
    assert by_path["data/images/10/page1_img1.png"].chunk_id == 5
    assert by_path["data/images/10/page1_img1.png"].embedding_count == 1
    assert by_path["data/images/10/page1_img1.png"].width == 120
    assert by_path["data/images/11/page2_img1.png"].document_id == 11
    assert by_path["data/images/11/page2_img1.png"].chunk_id == 0


def test_write_manifest_outputs_expected_columns(tmp_path: Path) -> None:
    rows = classify_rows(
        [make_row(1, "data/images/1/page1_img1.png", size=6000, width=120, height=120)],
        small_file_bytes=5 * 1024,
        small_dimension=100,
        decoration_page_threshold=3,
        fragment_page_image_threshold=3,
        fragment_aspect_ratio=3.0,
    )
    output = tmp_path / "manifest.csv"

    write_manifest(output, rows)

    with output.open("r", encoding="utf-8-sig", newline="") as file:
        loaded = list(csv.DictReader(file))
    assert loaded[0]["classification"] == "normal"
    assert loaded[0]["source_image_path"] == "data/images/1/page1_img1.png"


def make_row(document_id: int, path: str, *, size: int, width: int, height: int):
    from scripts.classify_phase46_problem_images import ImageInventoryRow

    return ImageInventoryRow(
        document_id=document_id,
        document_title=f"doc {document_id}",
        chunk_id=document_id * 10,
        chunk_index=1,
        embedding_count=1,
        source_image_path=path,
        exists_on_disk=True,
        file_size_bytes=size,
        width=width,
        height=height,
        page_num=int(path.split("/page", 1)[1].split("_", 1)[0]),
        image_num=int(path.rsplit("_img", 1)[1].split(".", 1)[0]),
    )


def create_schema(connection: sqlite3.Connection) -> None:
    connection.execute("create table documents (id integer primary key, title text)")
    connection.execute(
        """
        create table chunks (
            id integer primary key,
            document_id integer,
            chunk_index integer,
            chunk_type text,
            source_image_path text
        )
        """
    )
    connection.execute("create table chunk_embeddings (id integer primary key, chunk_id integer)")


def make_png_bytes(width: int, height: int) -> bytes:
    raw = b"".join(b"\x00" + b"\x20\x80\xc8" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw))
        + png_chunk(b"IEND", b"")
    )


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)
