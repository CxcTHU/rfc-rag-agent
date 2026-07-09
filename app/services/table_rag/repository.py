from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    DocumentTable,
    DocumentTableCell,
    DocumentTableColumn,
    DocumentTableRow,
    TableExtractionRun,
    TableRetrievalUnit,
)
from app.db.repositories import serialize_metadata
from app.services.table_rag.models import StructuredTableDraft, TableRetrievalUnitDraft
from app.services.table_rag.normalization import content_hash, extract_unit, first_numeric_value, normalize_lookup_text


class StructuredTableRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_extraction_run(
        self,
        *,
        document_id: int | None,
        source: str,
        dry_run: bool,
        metadata: dict[str, object] | None = None,
    ) -> TableExtractionRun:
        run = TableExtractionRun(
            document_id=document_id,
            source=source,
            status="running",
            dry_run=dry_run,
            tables_seen=0,
            tables_created=0,
            tables_skipped=0,
            error_count=0,
            metadata_json=serialize_metadata(metadata),
        )
        self.db.add(run)
        self.db.flush()
        return run

    def finish_extraction_run(
        self,
        run: TableExtractionRun,
        *,
        status: str,
        tables_seen: int,
        tables_created: int,
        tables_skipped: int,
        errors: Sequence[str],
    ) -> None:
        run.status = status
        run.tables_seen = tables_seen
        run.tables_created = tables_created
        run.tables_skipped = tables_skipped
        run.error_count = len(errors)
        run.error_json = json.dumps(list(errors), ensure_ascii=False, separators=(",", ":")) if errors else None
        self.db.flush()

    def find_existing(self, draft: StructuredTableDraft) -> DocumentTable | None:
        statement = select(DocumentTable).where(
            DocumentTable.document_id == draft.document_id,
            DocumentTable.page_number == draft.page_number,
            DocumentTable.table_index == draft.table_index,
            DocumentTable.structure_hash == draft.structure_hash,
        )
        return self.db.scalar(statement)

    def save_table(self, draft: StructuredTableDraft, *, replace_existing: bool = False) -> tuple[DocumentTable, bool]:
        existing = self.find_existing(draft)
        if existing is not None and not replace_existing:
            return existing, False
        if existing is not None:
            self.db.delete(existing)
            self.db.flush()

        table = DocumentTable(
            document_id=draft.document_id,
            source_table_chunk_id=draft.source_table_chunk_id,
            extraction_run_id=draft.extraction_run_id,
            table_index=draft.table_index,
            page_number=draft.page_number,
            bbox_json=bbox_json(draft.bbox),
            caption=draft.caption,
            header_text=draft.header_text,
            row_count=len(draft.normalized_rows),
            col_count=max((len(row) for row in draft.normalized_rows), default=0),
            raw_rows_json=rows_json(draft.raw_rows),
            normalized_rows_json=rows_json(draft.normalized_rows),
            headers_json=json.dumps(list(draft.headers), ensure_ascii=False, separators=(",", ":")),
            units_json=json.dumps(draft.units, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            quality_score=draft.quality_score,
            structure_hash=draft.structure_hash,
            semantic_metadata_json=serialize_metadata(draft.semantic_metadata),
            processing_metadata_json=serialize_metadata(draft.processing_metadata),
        )
        self.db.add(table)
        self.db.flush()

        columns = [
            DocumentTableColumn(
                table_id=table.id,
                column_index=index,
                header=header,
                normalized_header=normalize_lookup_text(header),
                unit=draft.units.get(str(index)),
                metadata_json=serialize_metadata({"source": "header_row"}),
            )
            for index, header in enumerate(draft.headers)
        ]
        self.db.add_all(columns)
        rows = [
            DocumentTableRow(
                table_id=table.id,
                row_index=index,
                raw_cells_json=json.dumps(list(row), ensure_ascii=False, separators=(",", ":")),
                normalized_cells_json=json.dumps(list(row), ensure_ascii=False, separators=(",", ":")),
                metadata_json=serialize_metadata({"is_header": index == 0}),
            )
            for index, row in enumerate(draft.normalized_rows)
        ]
        self.db.add_all(rows)
        self.db.flush()

        row_by_index = {row.row_index: row for row in rows}
        column_by_index = {column.column_index: column for column in columns}
        cells: list[DocumentTableCell] = []
        for row_index, row in enumerate(draft.normalized_rows):
            for col_index, value in enumerate(row):
                column_unit = draft.units.get(str(col_index))
                cells.append(
                    DocumentTableCell(
                        table_id=table.id,
                        row_id=row_by_index.get(row_index).id if row_by_index.get(row_index) else None,
                        column_id=column_by_index.get(col_index).id if column_by_index.get(col_index) else None,
                        row_index=row_index,
                        col_index=col_index,
                        text=value,
                        normalized_text=normalize_lookup_text(value),
                        numeric_value=first_numeric_value(value),
                        unit=column_unit or extract_unit(value),
                        is_header=row_index == 0,
                    )
                )
        self.db.add_all(cells)
        self.db.flush()
        return table, True

    def replace_retrieval_units(
        self,
        table_id: int,
        units: Sequence[TableRetrievalUnitDraft],
    ) -> list[TableRetrievalUnit]:
        self.db.query(TableRetrievalUnit).filter(TableRetrievalUnit.table_id == table_id).delete(
            synchronize_session=False
        )
        persisted = [
            TableRetrievalUnit(
                table_id=table_id,
                unit_type=unit.unit_type,
                unit_index=unit.unit_index,
                text=unit.text,
                metadata_json=serialize_metadata(unit.metadata),
                source_row_index=unit.source_row_index,
                source_col_index=unit.source_col_index,
                content_hash=unit.content_hash or content_hash(unit.text),
            )
            for unit in units
        ]
        self.db.add_all(persisted)
        self.db.flush()
        return persisted

    def get_table(self, table_id: int) -> DocumentTable | None:
        return self.db.get(DocumentTable, table_id)

    def list_tables(self, *, document_id: int | None = None, limit: int | None = None) -> list[DocumentTable]:
        statement = select(DocumentTable).order_by(DocumentTable.id.asc())
        if document_id is not None:
            statement = statement.where(DocumentTable.document_id == document_id)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.db.scalars(statement).all())


def rows_json(rows: Sequence[Sequence[str]]) -> str:
    return json.dumps([list(row) for row in rows], ensure_ascii=False, separators=(",", ":"))


def bbox_json(bbox: tuple[float, float, float, float] | None) -> str | None:
    if bbox is None:
        return None
    return json.dumps(
        {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3]},
        ensure_ascii=False,
        separators=(",", ":"),
    )
