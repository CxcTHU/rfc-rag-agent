"""Prepare Phase 45 cloud file-asset sync manifest.

This script does not copy files to a server. It lists the local raw PDFs and
extracted images referenced by Phase 45 cloud-candidate documents so the user
can review and authorize server sync later.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_AUDIT_PATH = ROOT / "data" / "incoming" / "phase45_literature" / "phase12_quality_audit.csv"
DEFAULT_OUTPUT = ROOT / "data" / "incoming" / "phase45_literature" / "phase17_asset_sync_manifest.json"


@dataclass(frozen=True)
class AssetSyncManifest:
    cloud_candidate_documents: int
    raw_pdf_files: int
    raw_pdf_missing: int
    extracted_image_files: int
    extracted_image_missing: int
    cloud_database_migration_command: str
    cloud_faiss_rebuild_command: str
    production_smoke_checklist: list[str]
    note: str


def read_candidate_document_ids(audit_path: Path) -> list[int]:
    with audit_path.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            int(row["document_id"])
            for row in csv.DictReader(file)
            if row.get("review_status") == "cloud_candidate" and row.get("document_id")
        ]


def build_manifest(db_path: Path, audit_path: Path) -> AssetSyncManifest:
    document_ids = read_candidate_document_ids(audit_path)
    with sqlite3.connect(db_path) as connection:
        raw_paths = [
            Path(row[0])
            for row in connection.execute(
                f"select raw_path from documents where id in ({','.join('?' for _ in document_ids)})",
                document_ids,
            ).fetchall()
        ] if document_ids else []
        image_paths = [
            Path(row[0])
            for row in connection.execute(
                f"""
                select source_image_path from chunks
                where chunk_type = 'image_description'
                and document_id in ({','.join('?' for _ in document_ids)})
                """,
                document_ids,
            ).fetchall()
            if row[0]
        ] if document_ids else []

    return AssetSyncManifest(
        cloud_candidate_documents=len(document_ids),
        raw_pdf_files=len(raw_paths),
        raw_pdf_missing=sum(1 for path in raw_paths if not path.exists()),
        extracted_image_files=len(image_paths),
        extracted_image_missing=sum(1 for path in image_paths if not path.exists()),
        cloud_database_migration_command=(
            "python scripts/migrate_sqlite_to_postgres.py "
            "--source-sqlite data/app.sqlite --target-database-url <AUTHORIZED_POSTGRES_URL>"
        ),
        cloud_faiss_rebuild_command=(
            "python scripts/build_faiss_index.py --database-url <AUTHORIZED_POSTGRES_URL> "
            "--provider paratera --model-name GLM-Embedding-3 --dimension 2048 --output-dir data/faiss"
        ),
        production_smoke_checklist=[
            "/health",
            "keyword search",
            "vector search",
            "hybrid search",
            "Agent Q&A",
            "image_description vector retrieval",
        ],
        note="No files were copied and no cloud command was executed; await human verification and authorization.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Phase 45 cloud asset sync manifest.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    manifest = build_manifest(Path(args.db_path), Path(args.audit))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(asdict(manifest), ensure_ascii=False, indent=2))
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
