import sqlite3
import struct
import zlib
from pathlib import Path

import fitz

from app.services.ingestion.caption_extractor import CaptionExtractionConfig
from scripts.backfill_phase46_captions import backfill_captions, read_image_chunks


def test_backfill_captions_updates_caption_only_when_apply(tmp_path: Path) -> None:
    pdf_path = tmp_path / "doc.pdf"
    write_pdf(pdf_path, caption="Fig. 1 Test caption")
    db_path = tmp_path / "captions.sqlite"
    seed_db(db_path, pdf_path, existing_caption="")

    with sqlite3.connect(db_path) as connection:
        rows = read_image_chunks(connection)
        dry_run = backfill_captions(connection, rows, config=CaptionExtractionConfig(), apply=False)
        stored_caption = connection.execute("select caption from chunks where id = 1").fetchone()[0]

    assert dry_run[0].status == "captioned"
    assert dry_run[0].caption == "Fig. 1 Test caption"
    assert stored_caption == ""

    with sqlite3.connect(db_path) as connection:
        rows = read_image_chunks(connection)
        applied = backfill_captions(connection, rows, config=CaptionExtractionConfig(), apply=True)
        connection.commit()
        stored_caption = connection.execute("select caption from chunks where id = 1").fetchone()[0]

    assert applied[0].status == "captioned"
    assert stored_caption == "Fig. 1 Test caption"


def test_backfill_captions_clears_caption_when_no_caption(tmp_path: Path) -> None:
    pdf_path = tmp_path / "doc.pdf"
    write_pdf(pdf_path, caption="ordinary text")
    db_path = tmp_path / "captions.sqlite"
    seed_db(db_path, pdf_path, existing_caption="old caption")

    with sqlite3.connect(db_path) as connection:
        rows = read_image_chunks(connection)
        applied = backfill_captions(connection, rows, config=CaptionExtractionConfig(), apply=True)
        connection.commit()
        stored_caption = connection.execute("select caption from chunks where id = 1").fetchone()[0]

    assert applied[0].status == "no_caption"
    assert stored_caption is None


def seed_db(db_path: Path, pdf_path: Path, *, existing_caption: str) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            create table documents (
                id integer primary key,
                raw_path text,
                file_extension text
            )
            """
        )
        connection.execute(
            """
            create table chunks (
                id integer primary key,
                document_id integer,
                chunk_type text,
                source_image_path text,
                caption text
            )
            """
        )
        connection.execute(
            "insert into documents (id, raw_path, file_extension) values (1, ?, '.pdf')",
            (pdf_path.as_posix(),),
        )
        connection.execute(
            "insert into chunks (id, document_id, chunk_type, source_image_path, caption) "
            "values (1, 1, 'image_description', 'data/images/1/page1_img1.png', ?)",
            (existing_caption,),
        )


def write_pdf(path: Path, *, caption: str) -> None:
    document = fitz.open()
    page = document.new_page(width=360, height=240)
    page.insert_image(fitz.Rect(40, 40, 180, 120), stream=make_png_bytes(120, 80, (30, 120, 220)))
    page.insert_text((45, 138), caption, fontsize=11)
    document.save(path)
    document.close()


def make_png_bytes(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw))
        + png_chunk(b"IEND", b"")
    )


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)
