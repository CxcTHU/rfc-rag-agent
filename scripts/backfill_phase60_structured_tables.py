from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from app.services.ingestion.table_extractor import extract_tables_with_stats
from app.services.table_rag.extraction import draft_from_markdown_chunk, draft_from_table_chunk
from app.services.table_rag.repository import StructuredTableRepository
from app.services.table_rag.retrieval_units import build_retrieval_units


@dataclass(frozen=True)
class Phase60BackfillResult:
    documents_seen: int
    documents_processed: int
    tables_seen: int
    tables_created: int
    tables_skipped: int
    units_created: int
    dry_run_hashes: tuple[str, ...]
    errors: tuple[str, ...]


def backfill_structured_tables(
    db: Session,
    *,
    dry_run: bool,
    limit: int | None,
    document_id: int | None,
    resume: bool,
    from_markdown_fallback: bool,
) -> Phase60BackfillResult:
    query = db.query(Document).filter(Document.file_extension == ".pdf")
    if document_id is not None:
        query = query.filter(Document.id == document_id)
    documents = query.order_by(Document.id.asc()).limit(limit).all() if limit else query.order_by(Document.id.asc()).all()
    repository = StructuredTableRepository(db)

    processed = 0
    tables_seen = 0
    tables_created = 0
    tables_skipped = 0
    units_created = 0
    dry_run_hashes: list[str] = []
    errors: list[str] = []

    for document in documents:
        run = None
        if not dry_run:
            run = repository.create_extraction_run(
                document_id=document.id,
                source="phase60_structured_table_backfill",
                dry_run=False,
                metadata={"resume": resume, "from_markdown_fallback": from_markdown_fallback},
            )
        document_seen = 0
        document_created = 0
        document_skipped = 0
        document_errors: list[str] = []
        try:
            drafts = []
            pdf_path = Path(document.raw_path or document.source_path or "")
            if pdf_path.exists():
                result = extract_tables_with_stats(str(pdf_path), document.id)
                table_chunks_by_page = existing_table_chunks_by_page(db, document.id)
                for index, table in enumerate(result.tables):
                    source_chunk = pop_page_chunk(table_chunks_by_page, table.page_number)
                    drafts.append(
                        draft_from_table_chunk(
                            table,
                            document_id=document.id,
                            table_index=index,
                            source_table_chunk_id=source_chunk.id if source_chunk is not None else None,
                            extraction_run_id=run.id if run is not None else None,
                        )
                    )
            elif from_markdown_fallback:
                table_chunks = existing_table_chunks(db, document.id)
                for index, chunk in enumerate(table_chunks):
                    draft = draft_from_markdown_chunk(
                        chunk,
                        table_index=index,
                        extraction_run_id=run.id if run is not None else None,
                    )
                    if draft is not None:
                        drafts.append(draft)
            else:
                document_errors.append(f"doc_id={document.id}: pdf not found at {pdf_path}")

            if drafts:
                processed += 1
            for draft in drafts:
                tables_seen += 1
                document_seen += 1
                if dry_run:
                    tables_created += 1
                    dry_run_hashes.append(draft.structure_hash)
                    units_created += len(build_retrieval_units(draft))
                    continue
                table, created = repository.save_table(draft, replace_existing=not resume)
                if created:
                    tables_created += 1
                    document_created += 1
                else:
                    tables_skipped += 1
                    document_skipped += 1
                units = repository.replace_retrieval_units(table.id, build_retrieval_units(draft))
                units_created += len(units)
        except Exception as exc:  # noqa: BLE001 - batch scripts report and continue.
            document_errors.append(f"doc_id={document.id}: {exc}")
        finally:
            errors.extend(document_errors)
            if run is not None:
                repository.finish_extraction_run(
                    run,
                    status="failed" if document_errors else "completed",
                    tables_seen=document_seen,
                    tables_created=document_created,
                    tables_skipped=document_skipped,
                    errors=document_errors,
                )

    if not dry_run:
        db.commit()

    return Phase60BackfillResult(
        documents_seen=len(documents),
        documents_processed=processed,
        tables_seen=tables_seen,
        tables_created=tables_created,
        tables_skipped=tables_skipped,
        units_created=units_created,
        dry_run_hashes=tuple(dry_run_hashes[:10]),
        errors=tuple(errors),
    )


def existing_table_chunks(db: Session, document_id: int) -> list[Chunk]:
    return (
        db.query(Chunk)
        .filter(Chunk.document_id == document_id, Chunk.chunk_type == "table")
        .order_by(Chunk.chunk_index.asc())
        .all()
    )


def existing_table_chunks_by_page(db: Session, document_id: int) -> dict[int, list[Chunk]]:
    chunks_by_page: dict[int, list[Chunk]] = {}
    for chunk in existing_table_chunks(db, document_id):
        if chunk.page_number is None:
            continue
        chunks_by_page.setdefault(chunk.page_number, []).append(chunk)
    return chunks_by_page


def pop_page_chunk(chunks_by_page: dict[int, list[Chunk]], page_number: int) -> Chunk | None:
    chunks = chunks_by_page.get(page_number)
    if not chunks:
        return None
    return chunks.pop(0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Phase 60 structured TableRAG sidecar tables.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--document-id", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--from-markdown-fallback", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as db:
        result = backfill_structured_tables(
            db,
            dry_run=args.dry_run,
            limit=args.limit,
            document_id=args.document_id,
            resume=args.resume,
            from_markdown_fallback=args.from_markdown_fallback,
        )
    print(
        "phase60 structured table backfill: "
        f"seen_docs={result.documents_seen} processed_docs={result.documents_processed} "
        f"tables_seen={result.tables_seen} tables_created={result.tables_created} "
        f"tables_skipped={result.tables_skipped} units={result.units_created} "
        f"errors={len(result.errors)} dry_run={args.dry_run}"
    )
    if args.dry_run and result.dry_run_hashes:
        print("dry_run_structure_hashes=" + ",".join(result.dry_run_hashes))


if __name__ == "__main__":
    main()
