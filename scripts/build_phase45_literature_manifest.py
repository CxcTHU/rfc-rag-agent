"""Build the Phase 45 incoming literature manifest without importing files.

The manifest is a pre-ingestion audit artifact. It records file metadata,
openability, page count, a short inferred title, and duplicate candidates, but
it does not write to the application database, create chunks, or build
embeddings.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


DEFAULT_INPUT_DIR = Path(r"G:\Codex\program\papers_0618")
DEFAULT_OUTPUT_DIR = ROOT / "data" / "incoming" / "phase45_literature"
DEFAULT_SQLITE_PATH = ROOT / "data" / "app.sqlite"
MANIFEST_FIELDS = [
    "original_path",
    "relative_path",
    "file_name",
    "extension",
    "file_size_bytes",
    "sha256",
    "content_hash",
    "is_pdf_header",
    "is_openable",
    "page_count",
    "guessed_title",
    "status",
    "duplicate_reason",
    "existing_document_id",
]


@dataclass(frozen=True)
class ExistingDocument:
    document_id: int
    title: str
    content_hash: str


@dataclass(frozen=True)
class ManifestRow:
    original_path: str
    relative_path: str
    file_name: str
    extension: str
    file_size_bytes: int
    sha256: str
    content_hash: str
    is_pdf_header: bool
    is_openable: bool
    page_count: int | None
    guessed_title: str
    status: str
    duplicate_reason: str
    existing_document_id: int | None


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def has_pdf_header(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            return file.read(4) == b"%PDF"
    except OSError:
        return False


def normalize_title(value: str) -> str:
    text = value.casefold()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
    return text


def clean_filename_title(stem: str) -> str:
    title = re.sub(r"\s*\(\d+\)\s*$", "", stem)
    title = re.sub(r"_[^_]+$", "", title) if "_" in title else title
    return title.strip() or stem


def infer_pdf_title(path: Path) -> tuple[bool, int | None, str]:
    reader = PdfReader(str(path))
    page_count = len(reader.pages)
    metadata_title = ""
    if reader.metadata and reader.metadata.title:
        metadata_title = str(reader.metadata.title).strip()
    first_page_title = ""
    if page_count:
        first_page_text = reader.pages[0].extract_text() or ""
        first_page_title = first_meaningful_line(first_page_text)
    return True, page_count, metadata_title or first_page_title or clean_filename_title(path.stem)


def first_meaningful_line(text: str) -> str:
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) >= 4:
            return line[:120]
    return ""


def load_existing_documents(sqlite_path: Path) -> tuple[dict[str, ExistingDocument], dict[str, ExistingDocument]]:
    if not sqlite_path.exists():
        return {}, {}
    by_hash: dict[str, ExistingDocument] = {}
    by_title: dict[str, ExistingDocument] = {}
    with sqlite3.connect(sqlite_path) as connection:
        try:
            rows = connection.execute("select id, title, content_hash from documents").fetchall()
        except sqlite3.DatabaseError:
            return {}, {}
    for document_id, title, content_hash in rows:
        document = ExistingDocument(int(document_id), str(title or ""), str(content_hash or ""))
        if document.content_hash:
            by_hash[document.content_hash] = document
        normalized = normalize_title(document.title)
        if normalized:
            by_title.setdefault(normalized, document)
    return by_hash, by_title


def build_manifest(
    input_dir: Path,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    patterns: Iterable[str] = ("*.pdf", "*.caj"),
) -> list[ManifestRow]:
    existing_by_hash, existing_by_title = load_existing_documents(sqlite_path)
    seen_hashes: dict[str, Path] = {}
    seen_titles: dict[str, Path] = {}
    rows: list[ManifestRow] = []

    files: list[Path] = []
    for pattern in patterns:
        files.extend(input_dir.rglob(pattern))
    for path in sorted(set(files), key=lambda item: str(item).casefold()):
        sha256 = calculate_sha256(path)
        is_pdf = has_pdf_header(path)
        is_openable = False
        page_count: int | None = None
        guessed_title = clean_filename_title(path.stem)
        duplicate_reason = ""
        existing_document_id: int | None = None

        if is_pdf:
            try:
                is_openable, page_count, guessed_title = infer_pdf_title(path)
            except Exception as exc:  # noqa: BLE001 - manifest keeps scanning the batch
                duplicate_reason = f"open_failed:{type(exc).__name__}"
        elif path.suffix.lower() == ".caj":
            duplicate_reason = "unsupported_caj"
        else:
            duplicate_reason = "unsupported_extension"

        normalized_title = normalize_title(guessed_title)
        if sha256 in existing_by_hash:
            status = "duplicate_candidate"
            existing_document = existing_by_hash[sha256]
            duplicate_reason = "content_hash_matches_existing_document"
            existing_document_id = existing_document.document_id
        elif sha256 in seen_hashes:
            status = "duplicate_candidate"
            duplicate_reason = f"content_hash_matches_incoming:{seen_hashes[sha256].name}"
        elif normalized_title and normalized_title in existing_by_title:
            status = "duplicate_candidate"
            existing_document = existing_by_title[normalized_title]
            duplicate_reason = "title_matches_existing_document"
            existing_document_id = existing_document.document_id
        elif normalized_title and normalized_title in seen_titles:
            status = "duplicate_candidate"
            duplicate_reason = f"title_matches_incoming:{seen_titles[normalized_title].name}"
        elif not is_openable:
            status = "unreadable"
        elif not guessed_title:
            status = "needs_manual_metadata"
        else:
            status = "ready"

        seen_hashes.setdefault(sha256, path)
        if normalized_title:
            seen_titles.setdefault(normalized_title, path)

        rows.append(
            ManifestRow(
                original_path=str(path.resolve()),
                relative_path=str(path.relative_to(input_dir)),
                file_name=path.name,
                extension=path.suffix.lower(),
                file_size_bytes=path.stat().st_size,
                sha256=sha256,
                content_hash=sha256,
                is_pdf_header=is_pdf,
                is_openable=is_openable,
                page_count=page_count,
                guessed_title=guessed_title,
                status=status,
                duplicate_reason=duplicate_reason,
                existing_document_id=existing_document_id,
            )
        )
    return rows


def write_manifest(rows: list[ManifestRow], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "manifest.csv"
    json_path = output_dir / "manifest.json"
    payload = [asdict(row) for row in rows]

    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(payload)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return csv_path, json_path


def summarize(rows: list[ManifestRow]) -> dict[str, int]:
    summary: dict[str, int] = {"total": len(rows)}
    for row in rows:
        summary[row.status] = summary.get(row.status, 0) + 1
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 45 incoming literature manifest.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        raise SystemExit(f"input directory not found: {input_dir}")

    rows = build_manifest(input_dir=input_dir, sqlite_path=Path(args.sqlite_path))
    csv_path, json_path = write_manifest(rows, Path(args.output_dir))
    summary = summarize(rows)
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    print("summary:", " ".join(f"{key}={value}" for key, value in sorted(summary.items())))


if __name__ == "__main__":
    main()
