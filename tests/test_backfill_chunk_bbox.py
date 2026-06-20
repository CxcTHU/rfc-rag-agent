import json
import sqlite3
from dataclasses import dataclass

from scripts import backfill_phase47_chunk_bbox as backfill


@dataclass(frozen=True)
class FakeRect:
    x0: float
    y0: float
    x1: float
    y1: float


class FakePage:
    def __init__(self, matches_by_text: dict[str, list[FakeRect]]) -> None:
        self.matches_by_text = matches_by_text

    def search_for(self, text: str) -> list[FakeRect]:
        return self.matches_by_text.get(text, [])


class FakePdf:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages
        self.page_count = len(pages)

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def load_page(self, index: int) -> FakePage:
        return self.pages[index]


def make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        create table documents (
            id integer primary key,
            raw_path text not null,
            file_extension text not null
        );
        create table chunks (
            id integer primary key,
            document_id integer not null,
            chunk_index integer not null,
            chunk_type text not null,
            content text not null,
            page_number integer,
            content_bbox_json text
        );
        """
    )
    return connection


def insert_document(connection: sqlite3.Connection, *, raw_path: str) -> None:
    connection.execute(
        "insert into documents (id, raw_path, file_extension) values (1, ?, '.pdf')",
        (raw_path,),
    )


def test_backfill_chunk_bboxes_writes_exact_bbox_json(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF fake")
    connection = make_connection()
    insert_document(connection, raw_path=str(pdf_path))
    content = "A" * 80 + " trailing content"
    connection.execute(
        """
        insert into chunks
            (id, document_id, chunk_index, chunk_type, content, page_number, content_bbox_json)
        values (10, 1, 0, 'text', ?, 2, null)
        """,
        (content,),
    )
    fake_pdf = FakePdf(
        [
            FakePage({}),
            FakePage({"A" * 80: [FakeRect(72.0, 120.5, 540.0, 185.25)]}),
        ]
    )
    monkeypatch.setattr(backfill.fitz, "open", lambda _path: fake_pdf)

    summary = backfill.backfill_chunk_bboxes(connection, dry_run=False)

    assert summary.total_chunks == 1
    assert summary.exact_match == 1
    assert summary.updated_rows == 1
    payload = json.loads(
        connection.execute("select content_bbox_json from chunks where id = 10").fetchone()[0]
    )
    assert payload == {
        "page": 2,
        "bboxes": [{"x0": 72.0, "y0": 120.5, "x1": 540.0, "y1": 185.25}],
        "confidence": "exact",
    }


def test_backfill_chunk_bboxes_uses_page_only_when_text_layer_missing(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF fake")
    connection = make_connection()
    insert_document(connection, raw_path=str(pdf_path))
    connection.execute(
        """
        insert into chunks
            (id, document_id, chunk_index, chunk_type, content, page_number, content_bbox_json)
        values (11, 1, 0, 'text', 'scanned chunk text', 1, null)
        """
    )
    monkeypatch.setattr(backfill.fitz, "open", lambda _path: FakePdf([FakePage({})]))

    summary = backfill.backfill_chunk_bboxes(connection, dry_run=False)

    assert summary.page_only == 1
    payload = json.loads(
        connection.execute("select content_bbox_json from chunks where id = 11").fetchone()[0]
    )
    assert payload == {"page": 1, "bboxes": [], "confidence": "page_only"}


def test_backfill_chunk_bboxes_dry_run_does_not_update_database(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "dry-run.pdf"
    pdf_path.write_bytes(b"%PDF fake")
    connection = make_connection()
    insert_document(connection, raw_path=str(pdf_path))
    connection.execute(
        """
        insert into chunks
            (id, document_id, chunk_index, chunk_type, content, page_number, content_bbox_json)
        values (12, 1, 0, 'text', 'dry run text chunk', 1, null)
        """
    )
    fake_pdf = FakePdf([FakePage({"dry run text chunk": [FakeRect(1, 2, 3, 4)]})])
    monkeypatch.setattr(backfill.fitz, "open", lambda _path: fake_pdf)

    summary = backfill.backfill_chunk_bboxes(connection, dry_run=True)

    assert summary.exact_match == 1
    assert summary.updated_rows == 0
    assert connection.execute("select content_bbox_json from chunks where id = 12").fetchone()[0] is None
