from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.db.repositories import ChunkCreate, DocumentRepository
from app.db.session import SessionLocal
from app.services.ingestion.table_extractor import TableChunk, extract_tables_with_stats


@dataclass(frozen=True)
class TableBackfillResult:
    documents_seen: int
    documents_processed: int
    tables_created: int
    skipped_existing: int
    errors: tuple[str, ...]


def backfill_tables(
    db: Session,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    document_id: int | None = None,
) -> TableBackfillResult:
    query = db.query(Document).filter(Document.file_extension == ".pdf")
    if document_id is not None:
        query = query.filter(Document.id == document_id)
    documents = query.order_by(Document.id.asc()).limit(limit).all() if limit else query.all()

    processed = 0
    created = 0
    skipped_existing = 0
    errors: list[str] = []
    repository = DocumentRepository(db)

    for document in documents:
        if db.query(Chunk.id).filter(Chunk.document_id == document.id, Chunk.chunk_type == "table").first():
            skipped_existing += 1
            continue
        pdf_path = Path(document.raw_path or document.source_path or "")
        if not pdf_path.exists():
            errors.append(f"doc_id={document.id}: pdf not found at {pdf_path}")
            continue
        try:
            result = extract_tables_with_stats(str(pdf_path), document.id)
        except Exception as exc:  # noqa: BLE001 - batch scripts report and continue.
            errors.append(f"doc_id={document.id}: {exc}")
            continue
        processed += 1
        if not result.tables:
            continue
        if dry_run:
            created += len(result.tables)
            continue
        existing_count = db.query(Chunk).filter(Chunk.document_id == document.id).count()
        chunks = [
            chunk_create_from_table(table, chunk_index=existing_count + offset)
            for offset, table in enumerate(result.tables)
        ]
        repository.create_chunks(document, chunks, commit=False)
        created += len(chunks)

    if not dry_run:
        db.commit()

    return TableBackfillResult(
        documents_seen=len(documents),
        documents_processed=processed,
        tables_created=created,
        skipped_existing=skipped_existing,
        errors=tuple(errors),
    )


def chunk_create_from_table(table: TableChunk, *, chunk_index: int) -> ChunkCreate:
    metadata = {
        "page": table.page_number,
        "bbox": {
            "x0": table.bbox[0],
            "y0": table.bbox[1],
            "x1": table.bbox[2],
            "y1": table.bbox[3],
        },
        "confidence": "table_detector",
        "row_count": table.row_count,
        "col_count": table.col_count,
    }
    heading = table.header_text or f"Table on page {table.page_number}"
    content = f"{heading}\n\n{table.markdown_content}" if table.header_text else table.markdown_content
    return ChunkCreate(
        chunk_index=chunk_index,
        content=content,
        char_count=len(content),
        heading_path=heading,
        start_char=None,
        end_char=None,
        chunk_type="table",
        page_number=table.page_number,
        content_bbox_json=json.dumps(metadata, ensure_ascii=False),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Phase 47 table chunks from PDFs.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--document-id", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as db:
        result = backfill_tables(
            db,
            dry_run=args.dry_run,
            limit=args.limit,
            document_id=args.document_id,
        )
    print(
        "table backfill: "
        f"seen={result.documents_seen} processed={result.documents_processed} "
        f"tables={result.tables_created} skipped_existing={result.skipped_existing} "
        f"errors={len(result.errors)} dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    main()
