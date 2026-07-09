from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
import logging
import math
from pathlib import Path
from typing import Any

from app.core.config import get_settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TableChunk:
    page_number: int
    bbox: tuple[float, float, float, float]
    markdown_content: str
    header_text: str | None
    row_count: int
    col_count: int
    rows: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class TableExtractionStats:
    processed_pages: int = 0
    extracted_tables: int = 0
    skipped_small: int = 0
    failed_pages: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class TableExtractionResult:
    doc_id: int
    pdf_path: str
    tables: list[TableChunk] = field(default_factory=list)
    stats: TableExtractionStats = field(default_factory=TableExtractionStats)


def extract_tables(pdf_path: str, doc_id: int) -> list[TableChunk]:
    return extract_tables_with_stats(pdf_path=pdf_path, doc_id=doc_id).tables


def extract_tables_with_stats(
    pdf_path: str,
    doc_id: int,
    *,
    min_rows: int | None = None,
) -> TableExtractionResult:
    path = Path(pdf_path)
    threshold = min_rows if min_rows is not None else get_settings().table_extraction_min_rows
    if threshold <= 0:
        raise ValueError("min_rows must be greater than 0")
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    fitz = import_module("fitz")
    tables: list[TableChunk] = []
    processed_pages = 0
    skipped_small = 0
    failed_pages = 0
    errors: list[str] = []

    with fitz.open(path) as pdf:
        for page_index, page in enumerate(pdf):
            processed_pages += 1
            page_number = page_index + 1
            try:
                page_tables, page_skipped = extract_tables_from_page(
                    page,
                    page_number=page_number,
                    min_rows=threshold,
                )
            except Exception as exc:  # noqa: BLE001 - table extraction is best-effort.
                failed_pages += 1
                message = f"doc_id={doc_id} page={page_number}: {exc}"
                errors.append(message)
                logger.warning("Table extraction failed for %s", message)
                continue
            tables.extend(page_tables)
            skipped_small += page_skipped

    return TableExtractionResult(
        doc_id=doc_id,
        pdf_path=str(path),
        tables=tables,
        stats=TableExtractionStats(
            processed_pages=processed_pages,
            extracted_tables=len(tables),
            skipped_small=skipped_small,
            failed_pages=failed_pages,
            errors=tuple(errors),
        ),
    )


def extract_tables_from_page(
    page: Any,
    *,
    page_number: int,
    min_rows: int,
) -> tuple[list[TableChunk], int]:
    finder = page.find_tables()
    raw_tables = list(getattr(finder, "tables", []) or [])
    extracted: list[TableChunk] = []
    skipped_small = 0

    for raw_table in raw_tables:
        rows = normalize_rows(raw_table.extract())
        row_count = len(rows)
        col_count = max((len(row) for row in rows), default=0)
        if row_count < min_rows or col_count == 0:
            skipped_small += 1
            continue
        normalized_rows = pad_rows(rows, col_count)
        if not has_table_structure(normalized_rows):
            skipped_small += 1
            continue
        bbox = rect_tuple(getattr(raw_table, "bbox", (0.0, 0.0, 0.0, 0.0)))
        extracted.append(
            TableChunk(
                page_number=page_number,
                bbox=bbox,
                markdown_content=rows_to_markdown(normalized_rows),
                header_text=find_header_text(page, bbox),
                row_count=row_count,
                col_count=col_count,
                rows=tuple(tuple(cell for cell in row) for row in normalized_rows),
            )
        )

    return extracted, skipped_small


def normalize_rows(rows: Any) -> list[list[str]]:
    if not isinstance(rows, list):
        return []
    normalized: list[list[str]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        cells = [normalize_cell(cell) for cell in row]
        if any(cells):
            normalized.append(cells)
    return normalized


def normalize_cell(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\r", "\n").split())


def pad_rows(rows: list[list[str]], col_count: int) -> list[list[str]]:
    return [row + [""] * (col_count - len(row)) for row in rows]


def has_table_structure(rows: list[list[str]]) -> bool:
    """Reject layout noise that collapses a row into one filled cell plus blanks."""

    if not rows:
        return False
    col_count = max((len(row) for row in rows), default=0)
    if col_count < 2:
        return False
    nonempty_counts = [sum(1 for cell in row if cell.strip()) for row in rows]
    multi_cell_rows = sum(1 for count in nonempty_counts if count >= 2)
    if multi_cell_rows < max(2, math.ceil(len(rows) * 0.5)):
        return False
    active_columns = {
        index
        for row in rows
        for index, cell in enumerate(row)
        if cell.strip()
    }
    if len(active_columns) < 2:
        return False
    return True


def rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    lines = [markdown_row(rows[0]), markdown_row(["---"] * len(rows[0]))]
    lines.extend(markdown_row(row) for row in rows[1:])
    return "\n".join(lines)


def markdown_row(cells: list[str]) -> str:
    return "| " + " | ".join(escape_markdown_cell(cell) for cell in cells) + " |"


def escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").strip()


def find_header_text(page: Any, table_bbox: tuple[float, float, float, float]) -> str | None:
    try:
        text = page.get_text("dict")
    except Exception:  # noqa: BLE001 - header association is optional metadata.
        return None
    blocks = text.get("blocks", []) if isinstance(text, dict) else []
    candidates: list[tuple[float, str]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_bbox = rect_tuple(block.get("bbox", (0.0, 0.0, 0.0, 0.0)))
        block_text = text_from_block(block)
        if not block_text or block_bbox[3] > table_bbox[1]:
            continue
        if horizontal_overlap_ratio(block_bbox, table_bbox) < 0.2:
            continue
        candidates.append((table_bbox[1] - block_bbox[3], block_text))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[0][1][:200]


def text_from_block(block: dict[str, Any]) -> str:
    parts: list[str] = []
    for line in block.get("lines", []) or []:
        if not isinstance(line, dict):
            continue
        for span in line.get("spans", []) or []:
            if isinstance(span, dict):
                text = str(span.get("text", "")).strip()
                if text:
                    parts.append(text)
    return " ".join(parts) if parts else str(block.get("text", "")).strip()


def rect_tuple(value: Any) -> tuple[float, float, float, float]:
    if all(hasattr(value, attr) for attr in ("x0", "y0", "x1", "y1")):
        return (float(value.x0), float(value.y0), float(value.x1), float(value.y1))
    try:
        x0, y0, x1, y1 = value
    except (TypeError, ValueError):
        return (0.0, 0.0, 0.0, 0.0)
    return (float(x0), float(y0), float(x1), float(y1))


def horizontal_overlap_ratio(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    left_width = max(0.0, left[2] - left[0])
    right_width = max(0.0, right[2] - right[0])
    if left_width == 0 or right_width == 0:
        return 0.0
    overlap = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    return overlap / min(left_width, right_width)
