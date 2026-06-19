import csv
import sqlite3
from pathlib import Path

import fitz

from scripts.build_phase45_literature_manifest import build_manifest, write_manifest


def test_phase45_manifest_marks_ready_duplicate_and_unreadable(tmp_path: Path) -> None:
    input_dir = tmp_path / "papers"
    input_dir.mkdir()
    ready_pdf = input_dir / "堆石混凝土施工技术.pdf"
    duplicate_pdf = input_dir / "重复论文.pdf"
    caj_file = input_dir / "待转换.caj"
    write_simple_pdf(ready_pdf, "堆石混凝土施工技术")
    write_simple_pdf(duplicate_pdf, "重复论文")
    caj_file.write_bytes(b"CAJ proprietary content")

    sqlite_path = tmp_path / "app.sqlite"
    duplicate_hash = duplicate_pdf.read_bytes()
    import hashlib

    content_hash = hashlib.sha256(duplicate_hash).hexdigest()
    with sqlite3.connect(sqlite_path) as connection:
        connection.execute("create table documents (id integer primary key, title text, content_hash text)")
        connection.execute(
            "insert into documents (id, title, content_hash) values (?, ?, ?)",
            (7, "重复论文", content_hash),
        )

    rows = build_manifest(input_dir=input_dir, sqlite_path=sqlite_path)
    by_name = {row.file_name: row for row in rows}

    assert by_name["堆石混凝土施工技术.pdf"].status == "ready"
    assert by_name["堆石混凝土施工技术.pdf"].is_openable is True
    assert by_name["堆石混凝土施工技术.pdf"].page_count == 1
    assert by_name["重复论文.pdf"].status == "duplicate_candidate"
    assert by_name["重复论文.pdf"].duplicate_reason == "content_hash_matches_existing_document"
    assert by_name["重复论文.pdf"].existing_document_id == 7
    assert by_name["待转换.caj"].status == "unreadable"
    assert by_name["待转换.caj"].duplicate_reason == "unsupported_caj"


def test_phase45_manifest_writes_csv_and_json(tmp_path: Path) -> None:
    input_dir = tmp_path / "papers"
    input_dir.mkdir()
    write_simple_pdf(input_dir / "测试论文.pdf", "测试论文")

    rows = build_manifest(input_dir=input_dir, sqlite_path=tmp_path / "missing.sqlite")
    csv_path, json_path = write_manifest(rows, tmp_path / "manifest")

    assert csv_path.exists()
    assert json_path.exists()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        csv_rows = list(csv.DictReader(file))
    assert csv_rows[0]["file_name"] == "测试论文.pdf"
    assert csv_rows[0]["content_hash"] == csv_rows[0]["sha256"]
    assert '"file_name": "测试论文.pdf"' in json_path.read_text(encoding="utf-8")


def write_simple_pdf(path: Path, title: str) -> None:
    document = fitz.open()
    page = document.new_page(width=360, height=240)
    page.insert_text((48, 72), title, fontsize=16)
    document.set_metadata({"title": title})
    document.save(path)
    document.close()
