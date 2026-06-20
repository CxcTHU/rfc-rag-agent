"""Re-render Type B fragment documents with page-level clips."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from app.services.ingestion.image_extractor import PdfImageExtractionConfig, PdfImageExtractor  # noqa: E402


DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_MANIFEST = ROOT / "data" / "evaluation" / "phase46_image_quality_manifest.csv"
DEFAULT_REPORT = ROOT / "data" / "evaluation" / "phase46_fragment_fix_report.csv"
DEFAULT_IMAGE_DIR = ROOT / "data" / "images"
PILOT_DOCUMENT_IDS = [140, 431, 349, 144, 16]
REPORT_FIELDS = [
    "document_id",
    "document_title",
    "status",
    "old_type_b_chunks",
    "deleted_chunks",
    "deleted_embeddings",
    "rendered_images",
    "error",
]


@dataclass(frozen=True)
class FragmentFixReportRow:
    document_id: int
    document_title: str
    status: str
    old_type_b_chunks: int
    deleted_chunks: int
    deleted_embeddings: int
    rendered_images: int
    error: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix Phase 46 Type B fragment images.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--image-output-dir", default=str(DEFAULT_IMAGE_DIR))
    parser.add_argument("--document-id", type=int, action="append", default=[])
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    document_ids = args.document_id or PILOT_DOCUMENT_IDS
    type_b_chunk_ids = read_type_b_chunk_ids(Path(args.manifest), set(document_ids))
    extractor = PdfImageExtractor(
        PdfImageExtractionConfig(
            output_dir=Path(args.image_output_dir),
            min_width=50,
            min_height=50,
            page_render_dpi=args.dpi,
        )
    )
    with sqlite3.connect(args.db_path) as connection:
        report_rows = fix_documents(
            connection,
            document_ids,
            type_b_chunk_ids,
            extractor=extractor,
            root=ROOT,
            apply=args.apply,
        )
    write_report(Path(args.report), report_rows)
    print(
        "summary:",
        f"documents={len(document_ids)}",
        f"rendered_images={sum(row.rendered_images for row in report_rows)}",
        f"deleted_chunks={sum(row.deleted_chunks for row in report_rows)}",
        f"deleted_embeddings={sum(row.deleted_embeddings for row in report_rows)}",
        f"dry_run={not args.apply}",
    )
    print(f"wrote {args.report}")


def read_type_b_chunk_ids(manifest_path: Path, document_ids: set[int]) -> dict[int, list[int]]:
    by_document: dict[int, list[int]] = {document_id: [] for document_id in document_ids}
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            document_id = int(row.get("document_id") or 0)
            chunk_id = int(row.get("chunk_id") or 0)
            if document_id in document_ids and row.get("classification") == "type_b" and chunk_id > 0:
                by_document.setdefault(document_id, []).append(chunk_id)
    return by_document


def fix_documents(
    connection: sqlite3.Connection,
    document_ids: list[int],
    type_b_chunk_ids: dict[int, list[int]],
    *,
    extractor: PdfImageExtractor,
    root: Path,
    apply: bool,
) -> list[FragmentFixReportRow]:
    rows: list[FragmentFixReportRow] = []
    try:
        for document_id in document_ids:
            rows.append(
                fix_document(
                    connection,
                    document_id,
                    type_b_chunk_ids.get(document_id, []),
                    extractor=extractor,
                    root=root,
                    apply=apply,
                )
            )
        if apply:
            connection.commit()
    except Exception:
        if apply:
            connection.rollback()
        raise
    return rows


def fix_document(
    connection: sqlite3.Connection,
    document_id: int,
    chunk_ids: list[int],
    *,
    extractor: PdfImageExtractor,
    root: Path,
    apply: bool,
) -> FragmentFixReportRow:
    document = connection.execute(
        "select title, raw_path from documents where id = ?",
        (document_id,),
    ).fetchone()
    if document is None:
        return report(document_id, "", "failed", len(chunk_ids), 0, 0, 0, "document_not_found")
    title = str(document[0] or "")
    raw_path = str(document[1] or "")
    pdf_path = (root / raw_path).resolve()
    if not pdf_path.exists():
        return report(document_id, title, "failed", len(chunk_ids), 0, 0, 0, f"pdf_not_found:{raw_path}")
    if not apply:
        return report(document_id, title, "dry_run", len(chunk_ids), 0, 0, 0, "")
    try:
        rendered = extractor.extract_images_page_render(pdf_path, document_id=document_id)
        deleted_embeddings = delete_embeddings(connection, chunk_ids)
        deleted_chunks = delete_chunks(connection, chunk_ids)
        return report(
            document_id,
            title,
            "fixed",
            len(chunk_ids),
            deleted_chunks,
            deleted_embeddings,
            len(rendered),
            "",
        )
    except Exception as exc:  # noqa: BLE001 - report per-document failure.
        return report(document_id, title, "failed", len(chunk_ids), 0, 0, 0, f"{type(exc).__name__}: {exc}")


def delete_embeddings(connection: sqlite3.Connection, chunk_ids: list[int]) -> int:
    if not chunk_ids:
        return 0
    placeholders = ",".join("?" for _ in chunk_ids)
    return int(
        connection.execute(
            f"delete from chunk_embeddings where chunk_id in ({placeholders})",
            chunk_ids,
        ).rowcount
        or 0
    )


def delete_chunks(connection: sqlite3.Connection, chunk_ids: list[int]) -> int:
    if not chunk_ids:
        return 0
    placeholders = ",".join("?" for _ in chunk_ids)
    return int(
        connection.execute(
            f"delete from chunks where id in ({placeholders}) and chunk_type = 'image_description'",
            chunk_ids,
        ).rowcount
        or 0
    )


def report(
    document_id: int,
    title: str,
    status: str,
    old_type_b_chunks: int,
    deleted_chunks: int,
    deleted_embeddings: int,
    rendered_images: int,
    error: str,
) -> FragmentFixReportRow:
    return FragmentFixReportRow(
        document_id=document_id,
        document_title=title,
        status=status,
        old_type_b_chunks=old_type_b_chunks,
        deleted_chunks=deleted_chunks,
        deleted_embeddings=deleted_embeddings,
        rendered_images=rendered_images,
        error=error,
    )


def write_report(path: Path, rows: list[FragmentFixReportRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


if __name__ == "__main__":
    main()
