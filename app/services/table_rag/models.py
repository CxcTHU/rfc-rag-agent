from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StructuredTableDraft:
    document_id: int
    table_index: int
    page_number: int | None
    bbox: tuple[float, float, float, float] | None
    caption: str | None
    header_text: str | None
    raw_rows: tuple[tuple[str, ...], ...]
    normalized_rows: tuple[tuple[str, ...], ...]
    headers: tuple[str, ...]
    units: dict[str, str]
    quality_score: float
    structure_hash: str
    source_table_chunk_id: int | None = None
    extraction_run_id: int | None = None
    semantic_metadata: dict[str, Any] = field(default_factory=dict)
    processing_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TableRetrievalUnitDraft:
    unit_type: str
    unit_index: int
    text: str
    metadata: dict[str, Any]
    source_row_index: int | None = None
    source_col_index: int | None = None
    content_hash: str = ""


@dataclass(frozen=True)
class TableQueryPlan:
    query: str
    normalized_query: str
    terms: tuple[str, ...]
    numbers: tuple[float, ...]
    units: tuple[str, ...]
    wants_table: bool
    wants_row: bool
    wants_column: bool
    wants_cell: bool


@dataclass(frozen=True)
class MatchedTableUnit:
    type: str
    score: float
    unit_id: int | None = None
    row_index: int | None = None
    col_index: int | None = None
    text_preview: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class StructuredTableCitation:
    document_id: int
    chunk_id: int | None
    page: int | None
    bbox: tuple[float, float, float, float] | None


@dataclass(frozen=True)
class StructuredTableSearchResult:
    table_id: int
    score: float
    summary: str
    caption: str | None
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    matched_units: tuple[MatchedTableUnit, ...]
    citation: StructuredTableCitation
    metadata: dict[str, Any] = field(default_factory=dict)
