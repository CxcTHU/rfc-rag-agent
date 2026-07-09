from __future__ import annotations

import json
from typing import Any

from app.db.models import Chunk
from app.db.models import DocumentTable
from app.services.ingestion.table_extractor import TableChunk
from app.services.table_rag.models import StructuredTableDraft
from app.services.table_rag.normalization import (
    headers_from_rows,
    normalize_rows,
    parse_markdown_table,
    quality_score,
    structure_hash,
    units_from_headers,
)


def draft_from_table_chunk(
    table: TableChunk,
    *,
    document_id: int,
    table_index: int,
    source_table_chunk_id: int | None = None,
    extraction_run_id: int | None = None,
) -> StructuredTableDraft:
    rows = table.rows or parse_markdown_table(table.markdown_content)
    return draft_from_rows(
        rows,
        document_id=document_id,
        table_index=table_index,
        page_number=table.page_number,
        bbox=table.bbox,
        caption=table.header_text,
        header_text=table.header_text,
        source_table_chunk_id=source_table_chunk_id,
        extraction_run_id=extraction_run_id,
        source="pymupdf_find_tables",
    )


def draft_from_markdown_chunk(
    chunk: Chunk,
    *,
    table_index: int,
    extraction_run_id: int | None = None,
) -> StructuredTableDraft | None:
    rows = parse_markdown_table(chunk.content)
    if not rows:
        return None
    page, bbox = page_and_bbox_from_chunk(chunk)
    return draft_from_rows(
        rows,
        document_id=chunk.document_id,
        table_index=table_index,
        page_number=chunk.page_number or page,
        bbox=bbox,
        caption=chunk.heading_path,
        header_text=chunk.heading_path,
        source_table_chunk_id=chunk.id,
        extraction_run_id=extraction_run_id,
        source="markdown_chunk_fallback",
    )


def draft_from_document_table(table: DocumentTable) -> StructuredTableDraft:
    rows = tuple(tuple(str(cell) for cell in row) for row in json.loads(table.normalized_rows_json or "[]"))
    headers = tuple(str(header) for header in json.loads(table.headers_json or "[]"))
    units = json.loads(table.units_json or "{}")
    semantic = json.loads(table.semantic_metadata_json or "{}") if table.semantic_metadata_json else {}
    processing = json.loads(table.processing_metadata_json or "{}") if table.processing_metadata_json else {}
    return StructuredTableDraft(
        document_id=table.document_id,
        table_index=table.table_index,
        page_number=table.page_number,
        bbox=bbox_from_json(table.bbox_json),
        caption=table.caption,
        header_text=table.header_text,
        raw_rows=rows,
        normalized_rows=rows,
        headers=headers,
        units={str(key): str(value) for key, value in units.items()} if isinstance(units, dict) else {},
        quality_score=table.quality_score,
        structure_hash=table.structure_hash,
        source_table_chunk_id=table.source_table_chunk_id,
        extraction_run_id=table.extraction_run_id,
        semantic_metadata=dict(semantic) if isinstance(semantic, dict) else {},
        processing_metadata=dict(processing) if isinstance(processing, dict) else {},
    )


def draft_from_rows(
    rows: Any,
    *,
    document_id: int,
    table_index: int,
    page_number: int | None,
    bbox: tuple[float, float, float, float] | None,
    caption: str | None,
    header_text: str | None,
    source_table_chunk_id: int | None,
    extraction_run_id: int | None,
    source: str,
) -> StructuredTableDraft:
    normalized = normalize_rows(rows)
    headers = headers_from_rows(normalized)
    units = units_from_headers(headers)
    table_hash = structure_hash(normalized, headers)
    return StructuredTableDraft(
        document_id=document_id,
        table_index=table_index,
        page_number=page_number,
        bbox=bbox,
        caption=caption,
        header_text=header_text,
        raw_rows=normalized,
        normalized_rows=normalized,
        headers=headers,
        units=units,
        quality_score=quality_score(normalized),
        structure_hash=table_hash,
        source_table_chunk_id=source_table_chunk_id,
        extraction_run_id=extraction_run_id,
        semantic_metadata=semantic_metadata(caption, headers, normalized, units),
        processing_metadata={"source": source},
    )


def semantic_metadata(
    caption: str | None,
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    units: dict[str, str],
) -> dict[str, object]:
    row_entities: list[str] = []
    for row in rows[1:8]:
        if row and row[0].strip():
            row_entities.append(row[0].strip())
    return {
        "topic": caption or (headers[0] if headers else "structured table"),
        "entities": row_entities[:12],
        "measures": [header for header in headers if header][:12],
        "units": sorted(set(units.values())),
        "query_intents": ["表格", "行列查询", "数值提取", "单位对比"],
    }


def page_and_bbox_from_chunk(chunk: Chunk) -> tuple[int | None, tuple[float, float, float, float] | None]:
    if not chunk.content_bbox_json:
        return None, None
    try:
        payload = json.loads(chunk.content_bbox_json)
    except json.JSONDecodeError:
        return None, None
    page = payload.get("page") if isinstance(payload, dict) else None
    bbox_payload = payload.get("bbox") if isinstance(payload, dict) else None
    if not isinstance(bbox_payload, dict):
        return int(page) if isinstance(page, int) else None, None
    bbox = (
        float(bbox_payload.get("x0", 0.0)),
        float(bbox_payload.get("y0", 0.0)),
        float(bbox_payload.get("x1", 0.0)),
        float(bbox_payload.get("y1", 0.0)),
    )
    return int(page) if isinstance(page, int) else None, bbox


def bbox_from_json(payload: str | None) -> tuple[float, float, float, float] | None:
    if not payload:
        return None
    try:
        values = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(values, dict):
        return None
    return (
        float(values.get("x0", 0.0)),
        float(values.get("y0", 0.0)),
        float(values.get("x1", 0.0)),
        float(values.get("y1", 0.0)),
    )
