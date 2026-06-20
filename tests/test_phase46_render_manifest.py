import sqlite3
import struct
import zlib
from pathlib import Path

from scripts.build_phase46_render_manifest import build_manifest


def test_build_render_manifest_marks_pending_and_existing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    image_dir = root / "data" / "images"
    (image_dir / "10").mkdir(parents=True)
    pending = image_dir / "10" / "page1_render1.png"
    existing = image_dir / "10" / "page2_render1.png"
    ignored = image_dir / "10" / "page3_img1.png"
    pending.write_bytes(make_png_bytes(120, 80))
    existing.write_bytes(make_png_bytes(90, 70))
    ignored.write_bytes(make_png_bytes(60, 60))
    db_path = tmp_path / "manifest.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("create table documents (id integer primary key, title text)")
        connection.execute(
            "create table chunks (id integer primary key, chunk_type text, source_image_path text)"
        )
        connection.execute("insert into documents (id, title) values (10, 'doc ten')")
        connection.execute(
            "insert into chunks (id, chunk_type, source_image_path) "
            "values (1, 'image_description', 'data/images/10/page2_render1.png')"
        )
        rows = build_manifest(connection, image_dir, root)

    by_path = {row.source_image_path: row for row in rows}
    assert len(rows) == 2
    assert by_path["data/images/10/page1_render1.png"].status == "pending"
    assert by_path["data/images/10/page1_render1.png"].width == 120
    assert by_path["data/images/10/page2_render1.png"].status == "existing"
    assert by_path["data/images/10/page1_render1.png"].document_title == "doc ten"


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
