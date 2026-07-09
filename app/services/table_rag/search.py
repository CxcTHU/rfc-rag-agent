from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    DocumentTable,
    DocumentTableCell,
    DocumentTableColumn,
    TableRetrievalUnit,
)
from app.db.repositories import deserialize_metadata
from app.services.table_rag.models import (
    MatchedTableUnit,
    StructuredTableCitation,
    StructuredTableSearchResult,
    TableQueryPlan,
)
from app.services.table_rag.normalization import (
    normalize_lookup_text,
    parse_numbers,
    parse_units,
    short_preview,
)


CHINESE_SEGMENT_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}")
TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9%./℃°+-]{2,}")
ROUTE_WEIGHTS = {
    "table_summary": 2.8,
    "table_schema": 2.0,
    "row_pack": 1.4,
    "column_pack": 1.4,
    "cell_fact": 1.7,
    "caption_context": 2.8,
    "exact_header": 1.8,
    "exact_cell": 2.0,
    "numeric_unit": 0.6,
}


class TableQueryPlanner:
    def plan(self, query: str) -> TableQueryPlan:
        normalized = normalize_lookup_text(query)
        terms = tokenize_query(normalized)
        units = parse_units(query)
        numbers = parse_numbers(query)
        return TableQueryPlan(
            query=query,
            normalized_query=normalized,
            terms=terms,
            numbers=numbers,
            units=units,
            wants_table=contains_any(normalized, ("表", "table", "清单", "参数")),
            wants_row=contains_any(normalized, ("行", "材料", "项目", "构件", "row")),
            wants_column=contains_any(normalized, ("列", "字段", "指标", "单位", "column")),
            wants_cell=bool(numbers) or contains_any(normalized, ("多少", "数值", "用量", "比例", "cell")),
        )


class StructuredTableSearchService:
    def __init__(self, db: Session, planner: TableQueryPlanner | None = None) -> None:
        self.db = db
        self.planner = planner or TableQueryPlanner()

    def search(self, query: str, *, top_k: int = 5, document_id: int | None = None) -> list[StructuredTableSearchResult]:
        plan = self.planner.plan(query)
        if not table_retrieval_intent(plan):
            return []
        candidates: dict[int, TableCandidate] = defaultdict(TableCandidate)
        self._recall_retrieval_units(plan, candidates, document_id=document_id)
        self._recall_exact_headers(plan, candidates, document_id=document_id)
        self._recall_exact_cells(plan, candidates, document_id=document_id)
        self._recall_numeric_units(plan, candidates, document_id=document_id)
        ranked = sorted(candidates.items(), key=lambda item: item[1].score, reverse=True)[:top_k]
        return [
            self._hydrate_result(table_id, candidate)
            for table_id, candidate in ranked
            if candidate.score > 0
        ]

    def hydrate_table(
        self,
        table_id: int,
        *,
        matched_units: list[MatchedTableUnit] | None = None,
        score: float = 0.0,
    ) -> StructuredTableSearchResult | None:
        table = self.db.get(DocumentTable, table_id)
        if table is None:
            return None
        return hydrate_table(table, matched_units or [], score)

    def _recall_retrieval_units(
        self,
        plan: TableQueryPlan,
        candidates: dict[int, "TableCandidate"],
        *,
        document_id: int | None,
    ) -> None:
        statement = select(TableRetrievalUnit).join(DocumentTable).order_by(TableRetrievalUnit.id.asc())
        if document_id is not None:
            statement = statement.where(DocumentTable.document_id == document_id)
        filters = unit_prefilter_terms(plan)
        if filters:
            statement = statement.where(or_(*(TableRetrievalUnit.text.ilike(f"%{term}%") for term in filters)))
        units = list(self.db.scalars(statement.limit(20000)).all())
        scored: list[tuple[float, TableRetrievalUnit]] = []
        for unit in units:
            score = lexical_score(unit.text, plan)
            if score <= 0:
                continue
            score *= ROUTE_WEIGHTS.get(unit.unit_type, 1.0)
            scored.append((score, unit))
        scored.sort(key=lambda item: item[0], reverse=True)
        for rank, (score, unit) in enumerate(scored[:200], start=1):
            fused = score + 1.0 / (60 + rank)
            candidates[unit.table_id].add(
                fused,
                MatchedTableUnit(
                    type=unit.unit_type,
                    unit_id=unit.id,
                    score=round(fused, 4),
                    row_index=unit.source_row_index,
                    col_index=unit.source_col_index,
                    text_preview=short_preview(unit.text),
                    reason="retrieval_unit",
                ),
            )

    def _recall_exact_headers(
        self,
        plan: TableQueryPlan,
        candidates: dict[int, "TableCandidate"],
        *,
        document_id: int | None,
    ) -> None:
        if not plan.terms:
            return
        statement = select(DocumentTableColumn).join(DocumentTable)
        if document_id is not None:
            statement = statement.where(DocumentTable.document_id == document_id)
        filters = [DocumentTableColumn.normalized_header.ilike(f"%{term}%") for term in plan.terms if len(term) >= 2]
        if not filters:
            return
        columns = list(self.db.scalars(statement.where(or_(*filters)).limit(200)).all())
        for column in columns:
            score = ROUTE_WEIGHTS["exact_header"] + lexical_score(column.header, plan)
            candidates[column.table_id].add(
                score,
                MatchedTableUnit(
                    type="exact_header",
                    score=round(score, 4),
                    col_index=column.column_index,
                    text_preview=short_preview(column.header),
                    reason="header_match",
                ),
            )

    def _recall_exact_cells(
        self,
        plan: TableQueryPlan,
        candidates: dict[int, "TableCandidate"],
        *,
        document_id: int | None,
    ) -> None:
        if not plan.terms:
            return
        statement = select(DocumentTableCell).join(DocumentTable)
        if document_id is not None:
            statement = statement.where(DocumentTable.document_id == document_id)
        filters = [DocumentTableCell.normalized_text.ilike(f"%{term}%") for term in plan.terms if len(term) >= 2]
        if not filters:
            return
        cells = list(self.db.scalars(statement.where(or_(*filters)).limit(300)).all())
        for cell in cells:
            score = ROUTE_WEIGHTS["exact_cell"] + lexical_score(cell.text, plan)
            candidates[cell.table_id].add(
                score,
                MatchedTableUnit(
                    type="exact_cell",
                    score=round(score, 4),
                    row_index=cell.row_index,
                    col_index=cell.col_index,
                    text_preview=short_preview(cell.text),
                    reason="cell_match",
                ),
            )

    def _recall_numeric_units(
        self,
        plan: TableQueryPlan,
        candidates: dict[int, "TableCandidate"],
        *,
        document_id: int | None,
    ) -> None:
        if not plan.numbers and not plan.units:
            return
        statement = select(DocumentTableCell).join(DocumentTable).where(DocumentTableCell.is_header.is_(False))
        if document_id is not None:
            statement = statement.where(DocumentTable.document_id == document_id)
        if plan.units:
            statement = statement.where(DocumentTableCell.unit.in_(plan.units))
        cells = list(self.db.scalars(statement.limit(500)).all())
        for cell in cells:
            number_score = 0.0
            if plan.numbers and cell.numeric_value is not None:
                number_score = max(numeric_similarity(target, cell.numeric_value) for target in plan.numbers)
            unit_score = 1.0 if plan.units and cell.unit in plan.units else 0.0
            score = ROUTE_WEIGHTS["numeric_unit"] * (number_score + unit_score)
            if score <= 0:
                continue
            candidates[cell.table_id].add(
                score,
                MatchedTableUnit(
                    type="numeric_unit",
                    score=round(score, 4),
                    row_index=cell.row_index,
                    col_index=cell.col_index,
                    text_preview=short_preview(cell.text),
                    reason="numeric_or_unit_filter",
                ),
            )

    def _hydrate_result(self, table_id: int, candidate: "TableCandidate") -> StructuredTableSearchResult:
        table = self.db.get(DocumentTable, table_id)
        if table is None:
            raise ValueError(f"table_id={table_id} disappeared during hydrate")
        return hydrate_table(table, candidate.top_matches(), candidate.score)


@dataclass
class TableCandidate:
    score: float = 0.0
    matches: list[MatchedTableUnit] = field(default_factory=list)
    route_scores: dict[str, float] = field(default_factory=dict)

    def add(self, score: float, match: MatchedTableUnit) -> None:
        previous = self.route_scores.get(match.type, 0.0)
        if score > previous:
            self.route_scores[match.type] = score
            self.score += score - previous
        self.matches.append(match)

    def top_matches(self, limit: int = 12) -> list[MatchedTableUnit]:
        return sorted(self.matches, key=lambda match: match.score, reverse=True)[:limit]


def hydrate_table(
    table: DocumentTable,
    matches: list[MatchedTableUnit],
    score: float,
) -> StructuredTableSearchResult:
    headers = tuple(json_list(table.headers_json))
    raw_rows = tuple(tuple(str(cell) for cell in row) for row in json_list(table.normalized_rows_json))
    data_rows = tuple(row for index, row in enumerate(raw_rows) if index > 0)
    bbox = bbox_tuple(table.bbox_json)
    return StructuredTableSearchResult(
        table_id=table.id,
        score=round(score, 4),
        summary=summary_for_table(table),
        caption=table.caption,
        headers=headers,
        rows=data_rows,
        matched_units=tuple(matches),
        citation=StructuredTableCitation(
            document_id=table.document_id,
            chunk_id=table.source_table_chunk_id,
            page=table.page_number,
            bbox=bbox,
        ),
        metadata={
            "row_count": table.row_count,
            "col_count": table.col_count,
            "quality_score": table.quality_score,
            "semantic": deserialize_metadata(table.semantic_metadata_json),
        },
    )


def summary_for_table(table: DocumentTable) -> str:
    summary_unit = next((unit for unit in table.retrieval_units if unit.unit_type == "table_summary"), None)
    if summary_unit is not None:
        return short_preview(summary_unit.text, 500)
    return short_preview(table.caption or table.header_text or f"Table {table.id}", 500)


def tokenize_query(normalized_query: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for match in TOKEN_PATTERN.finditer(normalized_query):
        value = match.group(0).strip()
        if value and value not in tokens:
            tokens.append(value)
    for segment in CHINESE_SEGMENT_PATTERN.findall(normalized_query):
        for size in (2, 3, 4):
            for index in range(0, max(0, len(segment) - size + 1)):
                gram = segment[index : index + size]
                if gram and gram not in tokens:
                    tokens.append(gram)
    return tuple(tokens[:60])


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def table_retrieval_intent(plan: TableQueryPlan) -> bool:
    return bool(
        plan.wants_table
        or plan.wants_row
        or plan.wants_column
        or plan.wants_cell
        or plan.numbers
        or plan.units
    )


def unit_prefilter_terms(plan: TableQueryPlan, *, limit: int = 8) -> tuple[str, ...]:
    stop_terms = {"表格", "table", "字段", "行", "column", "row", "cell"}
    terms = [
        term
        for term in plan.terms
        if len(term) >= 2 and not term.isdigit() and term not in stop_terms
    ]
    terms.sort(key=lambda value: (len(value), value), reverse=True)
    selected: list[str] = []
    if len(plan.normalized_query) >= 4:
        selected.append(plan.normalized_query[:80])
    for term in terms:
        if term not in selected:
            selected.append(term)
        if len(selected) >= limit:
            break
    return tuple(selected)


def lexical_score(text: str, plan: TableQueryPlan) -> float:
    normalized = normalize_lookup_text(text)
    score = 0.0
    for phrase in phrase_boosts(plan):
        if phrase in normalized:
            score += min(80.0, 20.0 + len(phrase) * 0.8)
    matched_terms = 0
    for term in plan.terms:
        if term and term in normalized:
            matched_terms += 1
            score += 1.0 if len(term) <= 3 else 1.5
    if plan.terms:
        score += 4.0 * (matched_terms / len(plan.terms))
    for unit in plan.units:
        if normalize_lookup_text(unit) in normalized:
            score += 0.8
    for number in plan.numbers:
        if str(int(number)) in normalized or f"{number:g}" in normalized:
            score += 0.8
    return score


def phrase_boosts(plan: TableQueryPlan) -> tuple[str, ...]:
    phrases: list[str] = []
    raw = plan.normalized_query
    if len(raw) >= 4:
        phrases.append(raw)
    stripped = raw
    for prefix in ("表格 ", "table "):
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix) :]
    if len(stripped) >= 4 and stripped not in phrases:
        phrases.append(stripped)
    for marker in (" 字段 ", " 行 "):
        if marker in stripped:
            before, after = stripped.split(marker, 1)
            if len(before) >= 4 and before not in phrases:
                phrases.append(before)
            if len(after) >= 4 and after not in phrases:
                phrases.append(after)
    return tuple(phrases)


def numeric_similarity(target: float, value: float) -> float:
    if target == value:
        return 1.0
    denominator = max(abs(target), abs(value), 1.0)
    delta = abs(target - value) / denominator
    return max(0.0, 1.0 - delta)


def json_list(payload: str | None) -> list[Any]:
    if not payload:
        return []
    values = json.loads(payload)
    return values if isinstance(values, list) else []


def bbox_tuple(payload: str | None) -> tuple[float, float, float, float] | None:
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
