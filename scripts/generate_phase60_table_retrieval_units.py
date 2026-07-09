from __future__ import annotations

import argparse
from dataclasses import dataclass

from app.db.session import SessionLocal
from app.services.table_rag.extraction import draft_from_document_table
from app.services.table_rag.repository import StructuredTableRepository
from app.services.table_rag.retrieval_units import build_retrieval_units


@dataclass(frozen=True)
class RetrievalUnitGenerationResult:
    tables_seen: int
    tables_updated: int
    units_created: int


def generate_retrieval_units(
    *,
    document_id: int | None,
    limit: int | None,
    dry_run: bool,
) -> RetrievalUnitGenerationResult:
    with SessionLocal() as db:
        repository = StructuredTableRepository(db)
        tables = repository.list_tables(document_id=document_id, limit=limit)
        updated = 0
        unit_count = 0
        for table in tables:
            draft = draft_from_document_table(table)
            units = build_retrieval_units(draft)
            unit_count += len(units)
            if not dry_run:
                repository.replace_retrieval_units(table.id, units)
                updated += 1
        if not dry_run:
            db.commit()
        return RetrievalUnitGenerationResult(
            tables_seen=len(tables),
            tables_updated=updated if not dry_run else len(tables),
            units_created=unit_count,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Phase 60 table_retrieval_units from document_tables.")
    parser.add_argument("--document-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = generate_retrieval_units(
        document_id=args.document_id,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(
        "phase60 table retrieval units: "
        f"tables_seen={result.tables_seen} tables_updated={result.tables_updated} "
        f"units={result.units_created} dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    main()
