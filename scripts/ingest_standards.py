from __future__ import annotations

import argparse
import csv
import hashlib
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories import SourceRepository  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.ingestion.service import IngestionService  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from app.services.retrieval.vector_index import VectorIndexService  # noqa: E402
from app.services.source_collection import SourceCandidate, make_source_id, sanitize_filename  # noqa: E402
from app.services.source_registry import SourceRegistryService  # noqa: E402


DEFAULT_USER_AGENT = "RFC-RAG-Agent/0.1 (+https://github.com/local/rfc-rag-agent; public standards ingestion)"
DEFAULT_MAX_BYTES = 20 * 1024 * 1024
CSV_FIELDS = ["title", "url", "category", "trust_level", "notes"]
RESULT_FIELDS = [
    "title",
    "url",
    "category",
    "status",
    "bytes_downloaded",
    "local_path",
    "document_id",
    "source_id",
    "content_hash",
    "error",
]


@dataclass(frozen=True)
class StandardDocument:
    title: str
    url: str
    category: str = ""
    trust_level: str = "high"
    notes: str = ""


@dataclass(frozen=True)
class DownloadResult:
    status: str
    url: str
    local_path: Path | None = None
    bytes_downloaded: int = 0
    error: str = ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download public standards/manual PDFs and import them.")
    parser.add_argument("--standards-csv", default="data/crawl/standards_urls.csv")
    parser.add_argument("--output-dir", default="data/raw/standards")
    parser.add_argument("--results-csv", default="data/crawl/standards_results.csv")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-mb", type=float, default=20.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--max-documents", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--rebuild-index", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.delay < 2.0:
        raise SystemExit("--delay must be at least 2 seconds")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be greater than 0")
    if args.max_mb <= 0:
        raise SystemExit("--max-mb must be greater than 0")
    if args.max_documents is not None and args.max_documents < 0:
        raise SystemExit("--max-documents must not be negative")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must not be negative")

    standards = read_standards_csv(Path(args.standards_csv))
    if args.max_documents is not None:
        standards = standards[: args.max_documents]

    if args.dry_run:
        rows = [dry_run_row(standard) for standard in standards]
        write_results(Path(args.results_csv), rows)
        for row in rows:
            if not args.quiet:
                print(f"dry_run: {row['title']}")
        print(f"processed={len(rows)}")
        return 0

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = int(args.max_mb * 1024 * 1024)
    rows: list[dict[str, str]] = []

    init_db()
    with SessionLocal() as db:
        ingestion_service = IngestionService(db)
        source_registry = SourceRegistryService(SourceRepository(db))

        for standard in standards:
            row = ingest_standard(
                standard=standard,
                output_dir=output_dir,
                max_bytes=max_bytes,
                delay_seconds=args.delay,
                timeout_seconds=args.timeout,
                max_retries=args.max_retries,
                ingestion_service=ingestion_service,
                source_registry=source_registry,
            )
            rows.append(row)
            if not args.quiet:
                detail = f" document_id={row['document_id']}" if row["document_id"] else ""
                print(f"{row['status']}: {standard.title}{detail}")

        if args.rebuild_index:
            provider = create_embedding_provider(provider_name="deterministic")
            index_result = VectorIndexService(db, provider).build_index()
            print(
                "index rebuilt: "
                f"total={index_result.total_chunks} "
                f"indexed={index_result.indexed_chunks} "
                f"updated={index_result.updated_chunks} "
                f"skipped={index_result.skipped_chunks}"
            )

    write_results(Path(args.results_csv), rows)
    print(f"processed={len(rows)}")
    return 0


def read_standards_csv(path: Path) -> list[StandardDocument]:
    if not path.exists():
        raise FileNotFoundError(f"Standards CSV was not found: {path}")
    standards: list[StandardDocument] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = [field for field in CSV_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Standards CSV missing fields: {', '.join(missing)}")
        for row in reader:
            title = (row.get("title") or "").strip()
            url = (row.get("url") or "").strip()
            if not title or not url:
                continue
            standards.append(
                StandardDocument(
                    title=title,
                    url=url,
                    category=(row.get("category") or "").strip(),
                    trust_level=(row.get("trust_level") or "high").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return standards


def ingest_standard(
    *,
    standard: StandardDocument,
    output_dir: Path,
    max_bytes: int,
    delay_seconds: float,
    timeout_seconds: float,
    max_retries: int,
    ingestion_service: IngestionService,
    source_registry: SourceRegistryService,
) -> dict[str, str]:
    download = download_pdf(
        standard=standard,
        output_dir=output_dir,
        max_bytes=max_bytes,
        delay_seconds=delay_seconds,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )
    row = {
        "title": standard.title,
        "url": standard.url,
        "category": standard.category,
        "status": download.status,
        "bytes_downloaded": str(download.bytes_downloaded),
        "local_path": str(download.local_path or ""),
        "document_id": "",
        "source_id": "",
        "content_hash": "",
        "error": download.error,
    }
    if download.status != "downloaded" or download.local_path is None:
        return row

    try:
        import_result = ingestion_service.import_document(
            download.local_path,
            title=standard.title,
            source_path=standard.url,
            file_name=download.local_path.name,
            source_type="standard_document",
        )
        source_id = make_source_id("standard", standard.title, url=standard.url)
        source_registry.register_candidate(
            SourceCandidate(
                source_id=source_id,
                title=standard.title,
                venue=publisher_from_url(standard.url),
                category=standard.category,
                discovered_via="stage28_public_standard_pdf",
                url=standard.url,
                pdf_url=standard.url,
                keywords="dam safety; concrete; hydraulic structures; public standard",
                language="en",
                source_type="standard_document",
                access_rights="open_access",
                license_or_terms="Public PDF; extracted text used for local RAG corpus",
                local_path=str(download.local_path),
                status="imported" if import_result.status != "duplicate" else "duplicate",
                notes=standard.notes,
            ),
            document_id=import_result.document_id,
        )
    except Exception as exc:
        row["status"] = "ingest_failed"
        row["error"] = str(exc)
        return row

    row.update(
        {
            "status": "duplicate" if import_result.status == "duplicate" else "imported",
            "document_id": str(import_result.document_id),
            "source_id": source_id,
            "content_hash": import_result.content_hash,
            "error": "",
        }
    )
    return row


def download_pdf(
    *,
    standard: StandardDocument,
    output_dir: Path,
    max_bytes: int = DEFAULT_MAX_BYTES,
    delay_seconds: float = 2.0,
    timeout_seconds: float = 30.0,
    max_retries: int = 2,
    sleep: Callable[[float], None] = time.sleep,
    user_agent: str = DEFAULT_USER_AGENT,
) -> DownloadResult:
    if "Mozilla/" in user_agent or "Chrome/" in user_agent:
        raise ValueError("User-Agent must identify this project, not a browser")

    last_error = ""
    for attempt in range(max_retries + 1):
        sleep(delay_seconds)
        request = urllib.request.Request(
            standard.url,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/pdf,*/*;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > max_bytes:
                    return DownloadResult(
                        status="skipped_too_large",
                        url=standard.url,
                        bytes_downloaded=0,
                        error=f"Content-Length {content_length} exceeds {max_bytes} bytes",
                    )

                path = output_dir / standard_filename(standard)
                temp_path = path.with_suffix(path.suffix + ".part")
                bytes_downloaded = 0
                with temp_path.open("wb") as file:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        bytes_downloaded += len(chunk)
                        if bytes_downloaded > max_bytes:
                            file.close()
                            temp_path.unlink(missing_ok=True)
                            return DownloadResult(
                                status="skipped_too_large",
                                url=standard.url,
                                bytes_downloaded=bytes_downloaded,
                                error=f"Downloaded bytes exceed {max_bytes}",
                            )
                        file.write(chunk)
                temp_path.replace(path)
                return DownloadResult(
                    status="downloaded",
                    url=standard.url,
                    local_path=path,
                    bytes_downloaded=bytes_downloaded,
                )
        except urllib.error.HTTPError as exc:
            return DownloadResult(
                status="download_failed",
                url=standard.url,
                error=f"HTTP {exc.code}: {exc.reason}",
            )
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
            if attempt >= max_retries:
                break
    return DownloadResult(
        status="download_failed",
        url=standard.url,
        error=last_error,
    )


def standard_filename(standard: StandardDocument) -> str:
    digest = hashlib.sha1(standard.url.encode("utf-8")).hexdigest()[:10]
    return f"standard_{digest}_{sanitize_filename(standard.title)[:90]}.pdf"


def publisher_from_url(url: str) -> str:
    lowered = url.casefold()
    if "usace.army.mil" in lowered:
        return "U.S. Army Corps of Engineers"
    if "usbr.gov" in lowered:
        return "U.S. Bureau of Reclamation"
    if "fema.gov" in lowered:
        return "FEMA"
    if "ferc.gov" in lowered:
        return "FERC / FEMA archive"
    if "damsafety.org" in lowered:
        return "Association of State Dam Safety Officials"
    return ""


def dry_run_row(standard: StandardDocument) -> dict[str, str]:
    return {
        "title": standard.title,
        "url": standard.url,
        "category": standard.category,
        "status": "dry_run",
        "bytes_downloaded": "",
        "local_path": "",
        "document_id": "",
        "source_id": "",
        "content_hash": "",
        "error": "",
    }


def write_results(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


if __name__ == "__main__":
    raise SystemExit(main())
