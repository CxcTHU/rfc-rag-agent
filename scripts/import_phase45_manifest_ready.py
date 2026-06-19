"""Import Phase 45 ready manifest rows into local SQLite.

This script is intentionally manifest-driven: it imports only rows whose
manifest status is ``ready`` and skips duplicate/unreadable/manual-review rows.
It creates documents and text chunks through the existing ingestion service,
but it does not create embeddings or write to a cloud database.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.ingestion.service import (  # noqa: E402
    EmptyDocumentError,
    IngestionConfig,
    IngestionService,
)


DEFAULT_MANIFEST_PATH = ROOT / "data" / "incoming" / "phase45_literature" / "manifest.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "incoming" / "phase45_literature"
RESULT_FIELDS = [
    "file_name",
    "original_path",
    "manifest_status",
    "import_status",
    "document_id",
    "chunk_count",
    "content_hash",
    "error",
]


@dataclass(frozen=True)
class ImportRowResult:
    file_name: str
    original_path: str
    manifest_status: str
    import_status: str
    document_id: int | None = None
    chunk_count: int = 0
    content_hash: str = ""
    error: str = ""


@dataclass(frozen=True)
class ImportSummary:
    manifest_rows: int
    ready_rows: int
    imported: int
    duplicate: int
    skipped_not_ready: int
    empty: int
    failed: int
    new_chunks: int


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def import_ready_rows(
    manifest_rows: list[dict[str, str]],
    db: Session,
    raw_dir: Path | str = ROOT / "data" / "raw",
    source_type: str = "institutional_access_pdf",
    chunk_size: int = 900,
    chunk_overlap: int = 120,
) -> tuple[ImportSummary, list[ImportRowResult]]:
    service = IngestionService(
        db,
        IngestionConfig(raw_dir=raw_dir, chunk_size=chunk_size, chunk_overlap=chunk_overlap),
    )
    results: list[ImportRowResult] = []
    imported = duplicate = skipped_not_ready = empty = failed = new_chunks = ready_rows = 0

    for row in manifest_rows:
        manifest_status = row.get("status", "")
        file_name = row.get("file_name", "")
        original_path = row.get("original_path", "")
        if manifest_status != "ready":
            skipped_not_ready += 1
            results.append(
                ImportRowResult(
                    file_name=file_name,
                    original_path=original_path,
                    manifest_status=manifest_status,
                    import_status="skipped_not_ready",
                )
            )
            continue

        ready_rows += 1
        try:
            import_result = service.import_document(
                original_path,
                title=row.get("guessed_title") or None,
                source_path=original_path,
                file_name=file_name,
                source_type=source_type,
            )
        except EmptyDocumentError as exc:
            db.rollback()
            empty += 1
            results.append(
                ImportRowResult(
                    file_name=file_name,
                    original_path=original_path,
                    manifest_status=manifest_status,
                    import_status="empty",
                    error=str(exc),
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001 - keep batch alive
            db.rollback()
            failed += 1
            results.append(
                ImportRowResult(
                    file_name=file_name,
                    original_path=original_path,
                    manifest_status=manifest_status,
                    import_status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        if import_result.status == "duplicate":
            duplicate += 1
        else:
            imported += 1
            new_chunks += import_result.chunk_count
        results.append(
            ImportRowResult(
                file_name=file_name,
                original_path=original_path,
                manifest_status=manifest_status,
                import_status=import_result.status,
                document_id=import_result.document_id,
                chunk_count=import_result.chunk_count,
                content_hash=import_result.content_hash,
            )
        )

    summary = ImportSummary(
        manifest_rows=len(manifest_rows),
        ready_rows=ready_rows,
        imported=imported,
        duplicate=duplicate,
        skipped_not_ready=skipped_not_ready,
        empty=empty,
        failed=failed,
        new_chunks=new_chunks,
    )
    return summary, results


def write_import_outputs(summary: ImportSummary, results: list[ImportRowResult], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "phase11_import_summary.json"
    results_path = output_dir / "phase11_import_results.csv"
    summary_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with results_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(result) for result in results)
    return summary_path, results_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Phase 45 manifest ready rows into local SQLite.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--raw-dir", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--source-type", default="institutional_access_pdf")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise SystemExit(f"manifest not found: {manifest_path}")

    init_db()
    with SessionLocal() as db:
        summary, results = import_ready_rows(
            read_manifest(manifest_path),
            db=db,
            raw_dir=Path(args.raw_dir),
            source_type=args.source_type,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
    summary_path, results_path = write_import_outputs(summary, results, Path(args.output_dir))
    print(f"wrote {summary_path}")
    print(f"wrote {results_path}")
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))


if __name__ == "__main__":
    main()
