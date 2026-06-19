"""Build a reusable image-level manifest for unfinished Phase 45 multimodal work."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.ingestion.image_extractor import PdfImageExtractionConfig, PdfImageExtractor  # noqa: E402
from scripts.process_multimodal import read_document_ids_file, sanitize_error  # noqa: E402


MANIFEST_FIELDS = [
    "document_id",
    "document_title",
    "page_num",
    "source_image_path",
    "width",
    "height",
    "status",
    "error",
]


@dataclass(frozen=True)
class ImageManifestRow:
    document_id: int
    document_title: str
    page_num: int
    source_image_path: str
    width: int
    height: int
    status: str
    error: str = ""


@dataclass(frozen=True)
class ImageManifestSummary:
    selected_documents: int
    processed_documents: int
    failed_documents: int
    extracted_images: int
    pending_images: int
    existing_images: int
    elapsed_seconds: float


def main() -> None:
    parser = argparse.ArgumentParser(description="Build image-level remaining manifest for Phase 45.")
    parser.add_argument("--document-ids-file", action="append", required=True)
    parser.add_argument("--db-path", default=str(ROOT / "data" / "app.sqlite"))
    parser.add_argument("--image-output-dir", default="data/images")
    parser.add_argument("--min-width", type=int, default=100)
    parser.add_argument("--min-height", type=int, default=100)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-summary", required=True)
    parser.add_argument("--split-output-dir", default="")
    parser.add_argument("--split-count", type=int, default=0)
    args = parser.parse_args()

    started = time.perf_counter()
    document_ids = read_all_ids([Path(value) for value in args.document_ids_file])
    if args.offset:
        document_ids = document_ids[args.offset :]
    if args.limit:
        document_ids = document_ids[: args.limit]
    with sqlite3.connect(args.db_path, timeout=10) as connection:
        documents = read_documents(connection, document_ids)
        existing_image_paths = read_existing_image_paths(connection)
    extractor = PdfImageExtractor(
        PdfImageExtractionConfig(
            output_dir=Path(args.image_output_dir),
            min_width=args.min_width,
            min_height=args.min_height,
        )
    )

    rows: list[ImageManifestRow] = []
    processed_documents = failed_documents = 0
    for document_id in document_ids:
        document = documents.get(document_id)
        if document is None:
            failed_documents += 1
            rows.append(ImageManifestRow(document_id, "", 0, "", 0, 0, "extract_failed", "document_not_found_or_not_pdf"))
            continue
        title, raw_path = document
        try:
            images = extractor.extract_images(raw_path, document_id=document_id)
        except Exception as exc:  # noqa: BLE001 - keep manifest build alive
            failed_documents += 1
            rows.append(ImageManifestRow(document_id, title, 0, "", 0, 0, "extract_failed", sanitize_error(exc)))
            continue
        processed_documents += 1
        for image in images:
            status = "existing" if image.image_path in existing_image_paths else "pending"
            rows.append(
                ImageManifestRow(
                    document_id=document_id,
                    document_title=title,
                    page_num=image.page_num,
                    source_image_path=image.image_path,
                    width=image.width,
                    height=image.height,
                    status=status,
                )
            )

    summary = ImageManifestSummary(
        selected_documents=len(document_ids),
        processed_documents=processed_documents,
        failed_documents=failed_documents,
        extracted_images=sum(1 for row in rows if row.source_image_path),
        pending_images=sum(1 for row in rows if row.status == "pending"),
        existing_images=sum(1 for row in rows if row.status == "existing"),
        elapsed_seconds=round(time.perf_counter() - started, 3),
    )
    output_csv = Path(args.output_csv)
    output_summary = Path(args.output_summary)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    write_manifest(output_csv, rows)
    output_summary.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.split_output_dir and args.split_count:
        split_pending_rows(rows, Path(args.split_output_dir), args.split_count)
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))


def read_all_ids(paths: list[Path]) -> list[int]:
    ids: list[int] = []
    for path in paths:
        ids.extend(read_document_ids_file(path))
    return list(dict.fromkeys(ids))


def read_documents(connection: sqlite3.Connection, document_ids: list[int]) -> dict[int, tuple[str, str]]:
    if not document_ids:
        return {}
    placeholders = ",".join("?" for _ in document_ids)
    rows = connection.execute(
        f"select id, title, raw_path from documents where file_extension = '.pdf' and id in ({placeholders})",
        document_ids,
    ).fetchall()
    return {int(row[0]): (str(row[1] or ""), str(row[2] or "")) for row in rows if row[2]}


def read_existing_image_paths(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "select source_image_path from chunks where chunk_type = 'image_description' and source_image_path is not null"
    ).fetchall()
    return {str(row[0]) for row in rows}


def write_manifest(path: Path, rows: list[ImageManifestRow]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def split_pending_rows(rows: list[ImageManifestRow], output_dir: Path, split_count: int) -> None:
    if split_count <= 0:
        raise ValueError("split_count must be greater than 0")
    output_dir.mkdir(parents=True, exist_ok=True)
    buckets: list[list[ImageManifestRow]] = [[] for _ in range(split_count)]
    pending = [row for row in rows if row.status == "pending"]
    for index, row in enumerate(pending):
        buckets[index % split_count].append(row)
    for index, bucket in enumerate(buckets, start=1):
        write_manifest(output_dir / f"image_route_{index}.csv", bucket)


if __name__ == "__main__":
    main()
