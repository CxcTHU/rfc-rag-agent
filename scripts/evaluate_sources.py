from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.models import Source  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402


@dataclass(frozen=True)
class SourceRegistryMetrics:
    total_sources: int
    linked_documents: int
    merged_duplicates: int
    status_counts: dict[str, int]
    permission_counts: dict[str, int]
    trust_counts: dict[str, int]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate source registry coverage and governance fields.")
    parser.add_argument("--out", default="data/evaluation/source_registry_metrics.csv")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        metrics = collect_source_metrics(db)
    write_metrics(Path(args.out), metrics)
    print(format_metrics(metrics))


def collect_source_metrics(db: Session) -> SourceRegistryMetrics:
    total_sources = db.scalar(select(func.count(Source.id))) or 0
    linked_documents = db.scalar(select(func.count(Source.id)).where(Source.document_id.is_not(None))) or 0
    merged_duplicates = (
        db.scalar(select(func.count(Source.id)).where(Source.notes.like("%merged_duplicate_source_id=%")))
        or 0
    )
    return SourceRegistryMetrics(
        total_sources=total_sources,
        linked_documents=linked_documents,
        merged_duplicates=merged_duplicates,
        status_counts=count_by_field(db, Source.status),
        permission_counts=count_by_field(db, Source.fulltext_permission),
        trust_counts=count_by_field(db, Source.trust_level),
    )


def count_by_field(db: Session, column) -> dict[str, int]:
    rows = db.execute(select(column, func.count(Source.id)).group_by(column).order_by(column)).all()
    return {str(value): int(count) for value, count in rows}


def write_metrics(path: Path, metrics: SourceRegistryMetrics) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["scope", "key", "value"])
        writer.writeheader()
        for key, value in [
            ("total_sources", metrics.total_sources),
            ("linked_documents", metrics.linked_documents),
            ("merged_duplicates", metrics.merged_duplicates),
        ]:
            writer.writerow({"scope": "summary", "key": key, "value": value})
        for scope, values in [
            ("status", metrics.status_counts),
            ("fulltext_permission", metrics.permission_counts),
            ("trust_level", metrics.trust_counts),
        ]:
            for key, value in values.items():
                writer.writerow({"scope": scope, "key": key, "value": value})


def format_metrics(metrics: SourceRegistryMetrics) -> str:
    lines = [
        "source_registry_metrics",
        f"total_sources={metrics.total_sources}",
        f"linked_documents={metrics.linked_documents}",
        f"merged_duplicates={metrics.merged_duplicates}",
        "status_counts=" + format_counts(metrics.status_counts),
        "fulltext_permission_counts=" + format_counts(metrics.permission_counts),
        "trust_counts=" + format_counts(metrics.trust_counts),
    ]
    return "\n".join(lines)


def format_counts(values: dict[str, int]) -> str:
    return ";".join(f"{key}:{value}" for key, value in sorted(values.items()))


if __name__ == "__main__":
    main()
