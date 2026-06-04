from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.ingestion.service import IngestionConfig, IngestionService  # noqa: E402
from app.services.source_collection import CSV_FIELDS  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Import discovered/fulltext PDFs into SQLite.")
    parser.add_argument("--manifest", action="append", default=[], help="CSV manifest/candidate file.")
    parser.add_argument("--scan-dir", action="append", default=[], help="Directory to scan for PDFs.")
    parser.add_argument("--source-type", default="open_access_pdf", help="Source type for scanned files.")
    parser.add_argument("--raw-dir", default="data/raw", help="Raw copy directory.")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    args = parser.parse_args()

    init_db()
    rows = []
    for manifest in args.manifest:
        rows.extend(read_rows(Path(manifest)))
    for scan_dir in args.scan_dir:
        rows.extend(rows_from_directory(Path(scan_dir), args.source_type))

    with SessionLocal() as db:
        service = IngestionService(
            db,
            IngestionConfig(
                raw_dir=args.raw_dir,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
            ),
        )
        for row in rows:
            local_path = Path(row.get("local_path", ""))
            if not local_path.exists() or local_path.suffix.lower() != ".pdf":
                continue
            result = service.import_document(
                local_path,
                title=row.get("title") or local_path.stem,
                source_path=row.get("url") or row.get("pdf_url") or str(local_path),
                file_name=local_path.name,
                source_type=row.get("source_type") or args.source_type,
            )
            print(
                f"{result.status}\tdocument_id={result.document_id}\tchunks={result.chunk_count}\t{result.title}"
            )


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return [{field: row.get(field, "") for field in CSV_FIELDS} for row in reader]


def rows_from_directory(directory: Path, source_type: str) -> list[dict[str, str]]:
    if not directory.exists():
        return []
    rows = []
    for path in sorted(directory.rglob("*.pdf")):
        rows.append(
            {
                field: ""
                for field in CSV_FIELDS
            }
            | {
                "title": path.stem,
                "local_path": str(path),
                "source_type": source_type,
                "access_rights": "local_file",
                "status": "downloaded",
            }
        )
    return rows


if __name__ == "__main__":
    main()
