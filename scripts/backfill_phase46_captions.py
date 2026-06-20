"""Backfill captions for image_description chunks from PDF text blocks."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ingestion.caption_extractor import (  # noqa: E402
    CaptionExtractionConfig,
    find_caption_candidates,
    find_top_of_page_caption_candidates,
    locate_image_bbox,
    parse_image_reference,
)


DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_OUTPUT_CSV = ROOT / "data" / "evaluation" / "phase46_caption_coverage.csv"
DEFAULT_SUMMARY_JSON = ROOT / "data" / "evaluation" / "phase46_caption_coverage_summary.json"
FIELDS = [
    "chunk_id",
    "document_id",
    "source_image_path",
    "status",
    "caption",
    "caption_page_num",
    "error",
]


@dataclass(frozen=True)
class ImageChunkRow:
    chunk_id: int
    document_id: int
    raw_path: str
    source_image_path: str


@dataclass(frozen=True)
class CaptionCoverageRow:
    chunk_id: int
    document_id: int
    source_image_path: str
    status: str
    caption: str = ""
    caption_page_num: int = 0
    error: str = ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill image chunk captions from source PDFs.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY_JSON))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    config = CaptionExtractionConfig()
    with sqlite3.connect(args.db_path, timeout=30) as connection:
        rows = read_image_chunks(connection, limit=args.limit or None)
        coverage_rows = backfill_captions(connection, rows, config=config, apply=args.apply)
        if args.apply:
            connection.commit()
    summary = summarize(coverage_rows, elapsed_seconds=round(time.perf_counter() - started, 3), apply=args.apply)
    write_outputs(Path(args.output_csv), Path(args.summary_json), coverage_rows, summary)
    print("summary:", " ".join(f"{key}={value}" for key, value in summary.items()))
    print(f"wrote {args.output_csv}")
    print(f"wrote {args.summary_json}")


def read_image_chunks(connection: sqlite3.Connection, limit: int | None = None) -> list[ImageChunkRow]:
    query = """
        select c.id, c.document_id, d.raw_path, c.source_image_path
        from chunks c
        join documents d on d.id = c.document_id
        where c.chunk_type = 'image_description'
          and c.source_image_path is not null
          and c.source_image_path != ''
          and d.file_extension = '.pdf'
        order by c.document_id, c.source_image_path, c.id
    """
    if limit is not None:
        query += " limit ?"
        db_rows = connection.execute(query, (limit,)).fetchall()
    else:
        db_rows = connection.execute(query).fetchall()
    return [
        ImageChunkRow(
            chunk_id=int(row[0]),
            document_id=int(row[1]),
            raw_path=str(row[2] or ""),
            source_image_path=str(row[3] or ""),
        )
        for row in db_rows
    ]


def backfill_captions(
    connection: sqlite3.Connection,
    rows: list[ImageChunkRow],
    *,
    config: CaptionExtractionConfig,
    apply: bool,
) -> list[CaptionCoverageRow]:
    coverage: list[CaptionCoverageRow] = []
    for document_id, document_rows in group_by_document(rows):
        raw_path = document_rows[0].raw_path
        pdf_path = (ROOT / raw_path).resolve()
        if not pdf_path.exists():
            coverage.extend(
                CaptionCoverageRow(row.chunk_id, row.document_id, row.source_image_path, "failed", error="pdf_not_found")
                for row in document_rows
            )
            continue
        with fitz.open(pdf_path) as pdf:
            for row in document_rows:
                coverage_row = extract_caption_row(pdf, row, config)
                coverage.append(coverage_row)
                if apply and coverage_row.status == "captioned":
                    connection.execute(
                        "update chunks set caption = ? where id = ?",
                        (coverage_row.caption, row.chunk_id),
                    )
                elif apply and coverage_row.status == "no_caption":
                    connection.execute("update chunks set caption = null where id = ?", (row.chunk_id,))
    return coverage


def group_by_document(rows: list[ImageChunkRow]) -> list[tuple[int, list[ImageChunkRow]]]:
    groups: list[tuple[int, list[ImageChunkRow]]] = []
    current_document_id: int | None = None
    current_rows: list[ImageChunkRow] = []
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


def extract_caption_row(
    pdf: fitz.Document,
    row: ImageChunkRow,
    config: CaptionExtractionConfig,
) -> CaptionCoverageRow:
    try:
        image_ref = parse_image_reference(row.source_image_path)
        page = pdf.load_page(image_ref.page_num - 1)
        image_bbox = locate_image_bbox(page, image_ref, config)
        candidates = find_caption_candidates(page, image_bbox, config)
        caption_page_num = image_ref.page_num
        if not candidates and image_bbox.y1 >= page.rect.y1 - config.search_below_points:
            next_page_index = image_ref.page_num
            if next_page_index < pdf.page_count:
                next_page = pdf.load_page(next_page_index)
                candidates = find_top_of_page_caption_candidates(next_page, image_bbox, config)
                caption_page_num = next_page_index + 1
        if not candidates:
            return CaptionCoverageRow(row.chunk_id, row.document_id, row.source_image_path, "no_caption")
        caption = candidates[0].text
        return CaptionCoverageRow(
            row.chunk_id,
            row.document_id,
            row.source_image_path,
            "captioned",
            caption=caption,
            caption_page_num=caption_page_num,
        )
    except Exception as exc:  # noqa: BLE001 - keep full backfill moving.
        return CaptionCoverageRow(
            row.chunk_id,
            row.document_id,
            row.source_image_path,
            "failed",
            error=f"{type(exc).__name__}: {exc}",
        )


def summarize(rows: list[CaptionCoverageRow], *, elapsed_seconds: float, apply: bool) -> dict[str, int | float | bool]:
    return {
        "total_images": len(rows),
        "captioned": sum(1 for row in rows if row.status == "captioned"),
        "no_caption": sum(1 for row in rows if row.status == "no_caption"),
        "failed": sum(1 for row in rows if row.status == "failed"),
        "apply": apply,
        "elapsed_seconds": elapsed_seconds,
    }


def write_outputs(
    output_csv: Path,
    summary_json: Path,
    rows: list[CaptionCoverageRow],
    summary: dict[str, int | float | bool],
) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
