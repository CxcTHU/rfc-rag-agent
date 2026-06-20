"""Backfill text chunk PDF bboxes for Phase 47 citation location."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
EXACT_SNIPPET_CHARS = 80
PARTIAL_SNIPPET_CHARS = 40


@dataclass(frozen=True)
class ChunkBboxRow:
    chunk_id: int
    document_id: int
    raw_path: str
    file_extension: str
    chunk_type: str
    content: str
    page_number: int | None


@dataclass(frozen=True)
class ChunkBboxResult:
    chunk_id: int
    status: str
    payload_json: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ChunkBboxSummary:
    total_chunks: int
    exact_match: int
    partial_match: int
    page_only: int
    failed: int
    skipped_image: int
    updated_rows: int
    dry_run: bool
    elapsed_seconds: float = 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill chunk PDF bbox JSON.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--doc-id", type=int, default=0)
    args = parser.parse_args()

    started = time.perf_counter()
    with sqlite3.connect(args.db_path, timeout=30) as connection:
        summary = backfill_chunk_bboxes(
            connection,
            dry_run=args.dry_run,
            limit=args.limit or None,
            doc_id=args.doc_id or None,
        )
        if not args.dry_run:
            connection.commit()

    summary = ChunkBboxSummary(
        **{
            **asdict(summary),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    )
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))


def backfill_chunk_bboxes(
    connection: sqlite3.Connection,
    *,
    dry_run: bool,
    limit: int | None = None,
    doc_id: int | None = None,
) -> ChunkBboxSummary:
    ensure_content_bbox_column(connection)
    rows = read_candidate_chunks(connection, limit=limit, doc_id=doc_id)
    results: list[ChunkBboxResult] = []
    for document_id, document_rows in group_by_document(rows):
        text_rows = [row for row in document_rows if "image" not in row.chunk_type.casefold()]
        image_rows = [row for row in document_rows if "image" in row.chunk_type.casefold()]
        results.extend(ChunkBboxResult(row.chunk_id, "skipped_image") for row in image_rows)
        if not text_rows:
            continue
        pdf_path = resolve_pdf_path(text_rows[0].raw_path)
        if text_rows[0].file_extension.casefold() != ".pdf" or not pdf_path.exists():
            results.extend(
                ChunkBboxResult(row.chunk_id, "failed", error="pdf_not_found")
                for row in text_rows
            )
            continue
        try:
            with fitz.open(pdf_path) as pdf:
                for row in text_rows:
                    results.append(locate_chunk_bbox(pdf, row))
        except Exception as exc:  # noqa: BLE001 - keep long backfills moving.
            results.extend(
                ChunkBboxResult(
                    row.chunk_id,
                    "failed",
                    error=f"{type(exc).__name__}: {exc}",
                )
                for row in text_rows
            )

    updated_rows = 0
    if not dry_run:
        for result in results:
            if result.payload_json is None:
                continue
            connection.execute(
                "update chunks set content_bbox_json = ? where id = ?",
                (result.payload_json, result.chunk_id),
            )
            updated_rows += 1

    return ChunkBboxSummary(
        total_chunks=len(rows),
        exact_match=sum(1 for result in results if result.status == "exact"),
        partial_match=sum(1 for result in results if result.status == "partial"),
        page_only=sum(1 for result in results if result.status == "page_only"),
        failed=sum(1 for result in results if result.status == "failed"),
        skipped_image=sum(1 for result in results if result.status == "skipped_image"),
        updated_rows=updated_rows,
        dry_run=dry_run,
    )


def read_candidate_chunks(
    connection: sqlite3.Connection,
    *,
    limit: int | None,
    doc_id: int | None,
) -> list[ChunkBboxRow]:
    query = """
        select c.id, c.document_id, d.raw_path, d.file_extension,
               c.chunk_type, c.content, c.page_number
        from chunks c
        join documents d on d.id = c.document_id
        where c.content_bbox_json is null
    """
    params: list[int] = []
    if doc_id is not None:
        query += " and c.document_id = ?"
        params.append(doc_id)
    query += " order by c.document_id, c.chunk_index, c.id"
    if limit is not None:
        query += " limit ?"
        params.append(limit)
    rows = connection.execute(query, params).fetchall()
    return [
        ChunkBboxRow(
            chunk_id=int(row[0]),
            document_id=int(row[1]),
            raw_path=str(row[2] or ""),
            file_extension=str(row[3] or ""),
            chunk_type=str(row[4] or "text"),
            content=str(row[5] or ""),
            page_number=int(row[6]) if row[6] is not None else None,
        )
        for row in rows
    ]


def group_by_document(rows: list[ChunkBboxRow]) -> list[tuple[int, list[ChunkBboxRow]]]:
    groups: list[tuple[int, list[ChunkBboxRow]]] = []
    current_document_id: int | None = None
    current_rows: list[ChunkBboxRow] = []
    for row in rows:
        if current_document_id is None or row.document_id == current_document_id:
            current_document_id = row.document_id
            current_rows.append(row)
            continue
        groups.append((current_document_id, current_rows))
        current_document_id = row.document_id
        current_rows = [row]
    if current_document_id is not None:
        groups.append((current_document_id, current_rows))
    return groups


def locate_chunk_bbox(pdf: Any, row: ChunkBboxRow) -> ChunkBboxResult:
    page_indexes = candidate_page_indexes(pdf, row.page_number)
    for confidence, limit in (("exact", EXACT_SNIPPET_CHARS), ("partial", PARTIAL_SNIPPET_CHARS)):
        snippet = chunk_search_snippet(row.content, limit)
        if not snippet:
            continue
        for page_index in page_indexes:
            page = pdf.load_page(page_index)
            rects = list(page.search_for(snippet))
            if rects:
                payload = bbox_payload(
                    page=page_index + 1,
                    rects=rects,
                    confidence=confidence,
                )
                return ChunkBboxResult(
                    chunk_id=row.chunk_id,
                    status=confidence,
                    payload_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                )

    if row.page_number is not None and 1 <= row.page_number <= page_count(pdf):
        payload = {
            "page": row.page_number,
            "bboxes": [],
            "confidence": "page_only",
        }
        return ChunkBboxResult(
            chunk_id=row.chunk_id,
            status="page_only",
            payload_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )
    return ChunkBboxResult(row.chunk_id, "failed", error="no_text_match_or_page")


def candidate_page_indexes(pdf: Any, page_number: int | None) -> list[int]:
    total_pages = page_count(pdf)
    if page_number is not None and 1 <= page_number <= total_pages:
        return [page_number - 1]
    return list(range(total_pages))


def page_count(pdf: Any) -> int:
    value = getattr(pdf, "page_count", None)
    if isinstance(value, int):
        return value
    return len(pdf)


def chunk_search_snippet(content: str, limit: int) -> str:
    normalized = " ".join(content.split())
    if not normalized:
        return ""
    return normalized[:limit]


def bbox_payload(page: int, rects: list[Any], confidence: str) -> dict[str, object]:
    return {
        "page": page,
        "bboxes": [
            {
                "x0": round(float(rect.x0), 3),
                "y0": round(float(rect.y0), 3),
                "x1": round(float(rect.x1), 3),
                "y1": round(float(rect.y1), 3),
            }
            for rect in rects
        ],
        "confidence": confidence,
    }


def resolve_pdf_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def ensure_content_bbox_column(connection: sqlite3.Connection) -> None:
    columns = {
        str(row[1])
        for row in connection.execute("pragma table_info(chunks)").fetchall()
    }
    if "content_bbox_json" not in columns:
        raise RuntimeError("chunks.content_bbox_json is missing; run alembic upgrade head first")


if __name__ == "__main__":
    main()
