from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


DEFAULT_OUT = ROOT / "data" / "evaluation" / "original_pdf_open_eval.csv"
DEFAULT_LOCAL_SOURCE_TYPES = (
    "institutional_access_pdf",
)
CSV_FIELDS = [
    "run_at",
    "case_id",
    "document_id",
    "source_type",
    "file_extension",
    "open_url_present",
    "http_status",
    "content_type",
    "pdf_header_ok",
    "status",
    "latency_ms",
    "error_summary",
]


@dataclass(frozen=True)
class DocumentCase:
    case_id: str
    document_id: int
    source_type: str
    file_extension: str
    open_url: str | None


@dataclass(frozen=True)
class OpenResult:
    http_status: int | None
    content_type: str
    pdf_header_ok: bool
    latency_ms: float
    error_summary: str


def main() -> None:
    args = parse_args()
    rows = evaluate_original_pdf_open(
        base_url=args.base_url,
        out=Path(args.out),
        limit=args.limit,
        per_source=args.per_source,
        include_document_ids=parse_int_list(args.include_document_id),
        source_types=parse_source_types(args.source_types),
        timeout_seconds=args.timeout_seconds,
    )
    failed = [row for row in rows if row["status"] == "failed"]
    skipped = [row for row in rows if row["status"] == "skipped"]
    print(f"original PDF open eval rows={len(rows)} failed={len(failed)} skipped={len(skipped)}")
    print(f"wrote {args.out}")
    if failed:
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate whether document open URLs resolve to local CPU PDF files."
    )
    parser.add_argument("--base-url", default="http://36.103.199.132:8044")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--per-source", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument(
        "--source-types",
        default=",".join(DEFAULT_LOCAL_SOURCE_TYPES),
        help="Comma-separated document source_type values treated as local-PDF candidates.",
    )
    parser.add_argument(
        "--include-document-id",
        action="append",
        default=["2073"],
        help="Document id to force into the eval set. May be passed multiple times.",
    )
    return parser.parse_args()


def evaluate_original_pdf_open(
    *,
    base_url: str,
    out: Path,
    limit: int,
    per_source: int,
    include_document_ids: set[int],
    source_types: set[str],
    timeout_seconds: float,
) -> list[dict[str, object]]:
    documents = fetch_documents(base_url, timeout_seconds)
    cases = build_cases(
        documents,
        limit=limit,
        per_source=per_source,
        include_document_ids=include_document_ids,
        source_types=source_types,
    )
    run_at = datetime.now(timezone.utc).isoformat()
    rows = [
        evaluate_case(base_url, case, run_at=run_at, timeout_seconds=timeout_seconds)
        for case in cases
    ]
    write_csv(out, rows)
    return rows


def fetch_documents(base_url: str, timeout_seconds: float) -> list[dict[str, Any]]:
    url = join_url(base_url, "/documents")
    request = urllib.request.Request(url, headers={"User-Agent": "rfc-rag-open-pdf-eval/1.0"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise ValueError("/documents response did not include a documents list")
    return [document for document in documents if isinstance(document, dict)]


def build_cases(
    documents: list[dict[str, Any]],
    *,
    limit: int,
    per_source: int,
    include_document_ids: set[int],
    source_types: set[str],
) -> list[DocumentCase]:
    by_id = {int(document["id"]): document for document in documents if document.get("id") is not None}
    selected: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    for document_id in sorted(include_document_ids):
        document = by_id.get(document_id)
        if document is not None and is_pdf_candidate(document, source_types):
            selected.append(document)
            seen_ids.add(document_id)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in sorted(documents, key=lambda item: int(item.get("id") or 0)):
        document_id = int(document.get("id") or 0)
        if document_id in seen_ids or not is_pdf_candidate(document, source_types):
            continue
        grouped[str(document.get("source_type") or "")].append(document)

    for source_type in sorted(grouped):
        for document in grouped[source_type][:per_source]:
            if len(selected) >= limit:
                break
            selected.append(document)
            seen_ids.add(int(document["id"]))
        if len(selected) >= limit:
            break

    return [
        DocumentCase(
            case_id=f"open_pdf_{index + 1:02d}",
            document_id=int(document["id"]),
            source_type=str(document.get("source_type") or ""),
            file_extension=str(document.get("file_extension") or ""),
            open_url=document.get("open_url") if isinstance(document.get("open_url"), str) else None,
        )
        for index, document in enumerate(selected[:limit])
    ]


def is_pdf_candidate(document: dict[str, Any], source_types: set[str]) -> bool:
    source_type = str(document.get("source_type") or "")
    extension = str(document.get("file_extension") or "").lower().lstrip(".")
    file_name = str(document.get("file_name") or "").lower()
    return source_type in source_types and (extension == "pdf" or file_name.endswith(".pdf"))


def evaluate_case(
    base_url: str,
    case: DocumentCase,
    *,
    run_at: str,
    timeout_seconds: float,
) -> dict[str, object]:
    if not case.open_url:
        result = OpenResult(
            http_status=None,
            content_type="",
            pdf_header_ok=False,
            latency_ms=0.0,
            error_summary="missing_open_url",
        )
    else:
        result = open_pdf_head(join_url(base_url, case.open_url), timeout_seconds)

    passed = (
        result.http_status in {200, 206}
        and "application/pdf" in result.content_type.lower()
        and result.pdf_header_ok
    )
    skipped = result.http_status in {301, 302, 303, 307, 308}
    return {
        "run_at": run_at,
        "case_id": case.case_id,
        "document_id": case.document_id,
        "source_type": case.source_type,
        "file_extension": case.file_extension,
        "open_url_present": str(bool(case.open_url)).lower(),
        "http_status": result.http_status or "",
        "content_type": result.content_type,
        "pdf_header_ok": str(result.pdf_header_ok).lower(),
        "status": "passed" if passed else "skipped" if skipped else "failed",
        "latency_ms": f"{result.latency_ms:.3f}",
        "error_summary": result.error_summary,
    }


def open_pdf_head(url: str, timeout_seconds: float) -> OpenResult:
    request = urllib.request.Request(
        url,
        headers={
            "Range": "bytes=0-4",
            "User-Agent": "rfc-rag-open-pdf-eval/1.0",
        },
    )
    started = time.perf_counter()
    opener = urllib.request.build_opener(NoRedirectHandler)
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            body = response.read(5)
            latency_ms = (time.perf_counter() - started) * 1000
            return OpenResult(
                http_status=response.status,
                content_type=response.headers.get("content-type", ""),
                pdf_header_ok=body.startswith(b"%PDF"),
                latency_ms=latency_ms,
                error_summary="",
            )
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        is_redirect = exc.code in {301, 302, 303, 307, 308}
        location = exc.headers.get("location", "") if exc.headers else ""
        return OpenResult(
            http_status=exc.code,
            content_type=exc.headers.get("content-type", "") if exc.headers else "",
            pdf_header_ok=False,
            latency_ms=latency_ms,
            error_summary="external_redirect" if is_redirect and is_http_url(location) else short_error(str(exc)),
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return OpenResult(
            http_status=None,
            content_type="",
            pdf_header_ok=False,
            latency_ms=latency_ms,
            error_summary=short_error(str(exc)),
        )


def join_url(base_url: str, path_or_url: str) -> str:
    parsed = urllib.parse.urlparse(path_or_url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return path_or_url
    base = urllib.parse.urlparse(base_url)
    service_root = urllib.parse.urlunparse((base.scheme, base.netloc, "", "", "", ""))
    return urllib.parse.urljoin(service_root.rstrip("/") + "/", path_or_url.lstrip("/"))


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def is_http_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def parse_int_list(values: list[str]) -> set[int]:
    ids: set[int] = set()
    for value in values:
        for item in value.split(","):
            item = item.strip()
            if item:
                ids.add(int(item))
    return ids


def parse_source_types(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def short_error(value: str, limit: int = 160) -> str:
    clean = " ".join(value.split())
    return clean[:limit]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
