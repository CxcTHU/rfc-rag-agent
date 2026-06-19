"""Build a manifest for local literature files not yet present in SQLite."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_phase45_literature_manifest import (  # noqa: E402
    MANIFEST_FIELDS,
    ManifestRow,
    clean_filename_title,
    has_pdf_header,
    infer_pdf_title,
)


DEFAULT_INPUT_DIRS = [
    Path(r"G:\Codex\program\papers_0616"),
    Path(r"G:\Codex\program\papers_0618"),
    Path(r"G:\Codex\program\papers_0609"),
]
DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "incoming" / "phase45_missing_literature"


@dataclass(frozen=True)
class MissingManifestSummary:
    scanned_files: int
    scanned_unique_hashes: int
    already_in_db_unique_hashes: int
    missing_unique_hashes: int
    ready: int
    unreadable: int
    unsupported_caj: int
    duplicate_local_files: int


def main() -> None:
    parser = argparse.ArgumentParser(description="Build manifest for literature files missing from SQLite.")
    parser.add_argument("--input-dir", action="append", default=[])
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    input_dirs = [Path(value) for value in args.input_dir] or DEFAULT_INPUT_DIRS
    rows, summary = build_missing_manifest(input_dirs, Path(args.db_path))
    output_dir = Path(args.output_dir)
    csv_path, json_path = write_manifest(rows, output_dir)
    summary_path = output_dir / "missing_manifest_summary.json"
    summary_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    print(f"wrote {summary_path}")
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))


def build_missing_manifest(input_dirs: list[Path], db_path: Path) -> tuple[list[ManifestRow], MissingManifestSummary]:
    db_hashes = read_db_hashes(db_path)
    seen_local_hashes: set[str] = set()
    duplicate_local_files = 0
    rows: list[ManifestRow] = []
    scanned_files = 0
    already_in_db_unique_hashes = 0

    for path in iter_literature_files(input_dirs):
        scanned_files += 1
        digest = calculate_sha256(path)
        if digest in seen_local_hashes:
            duplicate_local_files += 1
            continue
        seen_local_hashes.add(digest)
        if digest in db_hashes:
            already_in_db_unique_hashes += 1
            continue
        rows.append(build_manifest_row(path, digest))

    summary = MissingManifestSummary(
        scanned_files=scanned_files,
        scanned_unique_hashes=len(seen_local_hashes),
        already_in_db_unique_hashes=already_in_db_unique_hashes,
        missing_unique_hashes=len(rows),
        ready=sum(1 for row in rows if row.status == "ready"),
        unreadable=sum(1 for row in rows if row.status == "unreadable"),
        unsupported_caj=sum(1 for row in rows if row.duplicate_reason == "unsupported_caj"),
        duplicate_local_files=duplicate_local_files,
    )
    return rows, summary


def iter_literature_files(input_dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for input_dir in input_dirs:
        files.extend(path for path in input_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".pdf", ".caj"})
    return sorted(files, key=lambda path: str(path).casefold())


def read_db_hashes(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path, timeout=5) as connection:
        return {str(row[0]) for row in connection.execute("select content_hash from documents where content_hash is not null")}


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest_row(path: Path, digest: str) -> ManifestRow:
    extension = path.suffix.lower()
    is_pdf = has_pdf_header(path)
    is_openable = False
    page_count: int | None = None
    guessed_title = clean_filename_title(path.stem)
    duplicate_reason = ""
    if is_pdf:
        try:
            is_openable, page_count, guessed_title = infer_pdf_title(path)
        except Exception as exc:  # noqa: BLE001 - keep scanning
            duplicate_reason = f"open_failed:{type(exc).__name__}"
    elif extension == ".caj":
        duplicate_reason = "unsupported_caj"
    else:
        duplicate_reason = "unsupported_extension"

    if not is_openable:
        status = "unreadable"
    elif not guessed_title:
        status = "needs_manual_metadata"
    else:
        status = "ready"

    return ManifestRow(
        original_path=str(path.resolve()),
        relative_path=path.name,
        file_name=path.name,
        extension=extension,
        file_size_bytes=path.stat().st_size,
        sha256=digest,
        content_hash=digest,
        is_pdf_header=is_pdf,
        is_openable=is_openable,
        page_count=page_count,
        guessed_title=guessed_title,
        status=status,
        duplicate_reason=duplicate_reason,
        existing_document_id=None,
    )


def write_manifest(rows: list[ManifestRow], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "missing_manifest.csv"
    json_path = output_dir / "missing_manifest.json"
    payload = [asdict(row) for row in rows]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(payload)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return csv_path, json_path


if __name__ == "__main__":
    main()
