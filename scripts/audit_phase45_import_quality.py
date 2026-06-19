"""Audit Phase 45 imported literature quality and source metadata.

The audit records statistics only: page counts, text length, Chinese ratio,
chunk counts, metadata gaps, and review reasons. It does not export full text.
Optionally, it upserts minimal ``sources`` metadata for imported documents so
the local golden corpus has traceable source records before cloud migration.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_MANIFEST_PATH = ROOT / "data" / "incoming" / "phase45_literature" / "manifest.csv"
DEFAULT_IMPORT_RESULTS_PATH = ROOT / "data" / "incoming" / "phase45_literature" / "phase11_import_results.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "incoming" / "phase45_literature"
AUDIT_FIELDS = [
    "file_name",
    "manifest_status",
    "import_status",
    "document_id",
    "title",
    "page_count",
    "text_length",
    "chinese_ratio",
    "chunk_count",
    "avg_chunk_chars",
    "suspected_scanned",
    "year_guess",
    "venue_guess",
    "category_guess",
    "fulltext_permission",
    "metadata_missing",
    "review_status",
    "review_reasons",
]


@dataclass(frozen=True)
class QualityAuditRow:
    file_name: str
    manifest_status: str
    import_status: str
    document_id: int | None
    title: str
    page_count: int | None
    text_length: int
    chinese_ratio: float
    chunk_count: int
    avg_chunk_chars: float
    suspected_scanned: bool
    year_guess: str
    venue_guess: str
    category_guess: str
    fulltext_permission: str
    metadata_missing: str
    review_status: str
    review_reasons: str


@dataclass(frozen=True)
class QualityAuditSummary:
    total_rows: int
    imported_rows: int
    review_required: int
    cloud_candidate: int
    skipped_duplicate_or_not_ready: int
    empty_rows: int
    suspected_scanned: int
    sources_upserted: int


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def normalize_title(value: str) -> str:
    text = value.casefold()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
    return text


def clean_filename_title(file_name: str) -> str:
    stem = Path(file_name).stem
    title = re.sub(r"\s*\(\d+\)\s*$", "", stem)
    title = re.sub(r"_[^_]+$", "", title) if "_" in title else title
    return title.strip() or stem



def is_weak_title(title: str) -> bool:
    stripped = (title or "").strip()
    if not stripped:
        return True
    if re.fullmatch(r"(19|20)\d{2}", stripped):
        return True
    if re.fullmatch(r"\d+[-_]\d+", stripped):
        return True
    if re.fullmatch(r"\d{1,4}", stripped):
        return True
    if len(stripped) < 6:
        return True
    weak_markers = (
        "doi",
        "http",
        "www.",
        "issn",
        "cnki",
        "elsevier",
        "sciencedirect",
        "springer",
        "copyright",
        "volume",
        "vol.",
        "no.",
        "journal",
        "article",
        "文章编号",
        "收稿日期",
        "科技资讯",
        "low carbon world",
        "水利规划与设计",
        "国防交通工程与技术",
        "建材与装饰",
        "建筑技术",
    )
    lowered = stripped.casefold()
    if any(marker in lowered for marker in weak_markers):
        return True
    if re.search(r"第\s*\d+\s*(卷|期)", stripped) and len(stripped) < 40:
        return True
    if re.search(r"(19|20)\d{2}\s*年\s*第\s*\d+\s*期", stripped) and len(stripped) < 50:
        return True
    if re.search(r"\b(pp|pages?)\s*[:：]?\s*\d+", lowered):
        return True
    return False


def domain_title_score(title: str) -> int:
    lowered = title.casefold()
    terms = (
        "堆石混凝土",
        "自密实",
        "胶结颗粒料",
        "筑坝",
        "大坝",
        "坝体",
        "施工",
        "rock-filled",
        "rock filled",
        "hardfill",
        "rfc",
    )
    return sum(1 for term in terms if term in lowered)


def candidate_title_from_text(text: str) -> str:
    candidates: list[str] = []
    for raw_line in re.split(r"[\r\n。；;]", text[:4000]):
        line = re.sub(r"\s+", " ", raw_line).strip(" -—_")
        if 6 <= len(line) <= 90 and not is_weak_title(line):
            candidates.append(line)
    if not candidates:
        return ""
    candidates.sort(key=lambda value: (domain_title_score(value), -len(value)), reverse=True)
    return candidates[0]


def choose_best_title(document_title: str, manifest_title: str, file_name: str, text_sample: str = "") -> str:
    filename_title = clean_filename_title(file_name)
    text_title = candidate_title_from_text(text_sample)
    candidates = [document_title, manifest_title, filename_title, text_title]
    strong = [candidate.strip() for candidate in candidates if candidate and not is_weak_title(candidate)]
    if strong:
        strong.sort(key=lambda value: (domain_title_score(value), value == filename_title, -len(value)), reverse=True)
        return strong[0]
    return filename_title


def guess_year(text: str) -> str:
    match = re.search(r"(19|20)\d{2}", text or "")
    return match.group(0) if match else ""


def guess_category(title: str) -> str:
    lowered = title.casefold()
    if any(term in lowered for term in ("堆石混凝土", "自密实", "rock-filled", "rock filled", "rfc")):
        return "rfc_core"
    return "dam_engineering"


def guess_venue(title: str) -> str:
    if "会议" in title or "研讨会" in title:
        return "conference_or_news"
    if "标准" in title or "导则" in title or "规范" in title:
        return "standard_or_guideline"
    return ""


def chinese_ratio(text: str) -> float:
    if not text:
        return 0.0
    chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    visible_chars = sum(1 for char in text if not char.isspace())
    if visible_chars == 0:
        return 0.0
    return round(chinese_chars / visible_chars, 4)



def load_chunk_stats(connection: sqlite3.Connection, document_id: int) -> tuple[int, int, float, float, str]:
    rows = connection.execute(
        "select content, char_count from chunks where document_id = ? and chunk_type = 'text'",
        (document_id,),
    ).fetchall()
    text = "".join(str(row[0] or "") for row in rows)
    total_chars = sum(int(row[1] or 0) for row in rows)
    count = len(rows)
    avg = round(total_chars / count, 2) if count else 0.0
    return total_chars, count, chinese_ratio(text), avg, text[:4000]


def load_document(connection: sqlite3.Connection, document_id: int) -> dict[str, str] | None:
    row = connection.execute(
        "select id, title, content_hash, raw_path, source_path, file_name from documents where id = ?",
        (document_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": str(row[0]),
        "title": str(row[1] or ""),
        "content_hash": str(row[2] or ""),
        "raw_path": str(row[3] or ""),
        "source_path": str(row[4] or ""),
        "file_name": str(row[5] or ""),
    }


def audit_quality(
    manifest_rows: list[dict[str, str]],
    import_rows: list[dict[str, str]],
    connection: sqlite3.Connection,
) -> list[QualityAuditRow]:
    manifest_by_file = {row.get("file_name", ""): row for row in manifest_rows}
    audit_rows: list[QualityAuditRow] = []
    for import_row in import_rows:
        file_name = import_row.get("file_name", "")
        manifest = manifest_by_file.get(file_name, {})
        document_id = int(import_row["document_id"]) if import_row.get("document_id") else None
        document = load_document(connection, document_id) if document_id is not None else None
        page_count = int(manifest["page_count"]) if manifest.get("page_count") else None
        text_length = chunk_count = 0
        ratio = avg_chunk_chars = 0.0
        text_sample = ""
        if document_id is not None:
            text_length, chunk_count, ratio, avg_chunk_chars, text_sample = load_chunk_stats(connection, document_id)
        title = choose_best_title(
            (document or {}).get("title", ""),
            manifest.get("guessed_title", ""),
            file_name,
            text_sample,
        )

        reasons: list[str] = []
        if import_row.get("import_status") == "empty":
            reasons.append("empty_text")
        if page_count and text_length / max(page_count, 1) < 80:
            reasons.append("low_text_per_page")
        if chunk_count == 0 and import_row.get("import_status") == "imported":
            reasons.append("no_text_chunks")
        year = guess_year(" ".join([title, file_name, text_sample[:2000]]))
        category = guess_category(title or file_name)
        venue = guess_venue(title or file_name)
        missing: list[str] = []
        if not title:
            missing.append("title")
        missing.extend(["authors", "venue"] if not venue else ["authors"])
        if not year:
            missing.append("year")
        suspected_scanned = "empty_text" in reasons or "low_text_per_page" in reasons
        blocking_metadata_missing = any(item in {"title", "year"} for item in missing)
        if import_row.get("import_status") == "skipped_not_ready":
            review_status = "skipped"
        elif reasons or blocking_metadata_missing:
            review_status = "review_required"
        else:
            review_status = "cloud_candidate"

        audit_rows.append(
            QualityAuditRow(
                file_name=file_name,
                manifest_status=import_row.get("manifest_status", ""),
                import_status=import_row.get("import_status", ""),
                document_id=document_id,
                title=title,
                page_count=page_count,
                text_length=text_length,
                chinese_ratio=ratio,
                chunk_count=chunk_count,
                avg_chunk_chars=avg_chunk_chars,
                suspected_scanned=suspected_scanned,
                year_guess=year,
                venue_guess=venue,
                category_guess=category,
                fulltext_permission="institutional_access",
                metadata_missing=";".join(missing),
                review_status=review_status,
                review_reasons=";".join(reasons),
            )
        )
    return audit_rows


def upsert_sources(connection: sqlite3.Connection, audit_rows: list[QualityAuditRow]) -> int:
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for row in audit_rows:
        if row.document_id is None or row.import_status != "imported":
            continue
        document = load_document(connection, row.document_id)
        if document is None:
            continue
        if document["title"] != row.title:
            connection.execute("update documents set title = ? where id = ?", (row.title, row.document_id))
        source_id = f"phase45_0618_{document['content_hash'][:16]}"
        existing = connection.execute("select id from sources where source_id = ?", (source_id,)).fetchone()
        payload = {
            "source_id": source_id,
            "title": row.title or row.file_name,
            "normalized_title": normalize_title(row.title or row.file_name),
            "authors": None,
            "year": row.year_guess or None,
            "venue": row.venue_guess or None,
            "category": row.category_guess,
            "discovered_via": "phase45_papers_0618_manifest",
            "doi": None,
            "normalized_doi": None,
            "url": None,
            "normalized_url": None,
            "pdf_url": None,
            "abstract": None,
            "keywords": None,
            "language": "zh",
            "citation_count": None,
            "source_type": "institutional_access_pdf",
            "trust_level": "local_authorized",
            "access_rights": "institutional_access",
            "fulltext_permission": row.fulltext_permission,
            "license_or_terms": None,
            "local_path": document["raw_path"],
            "status": row.review_status,
            "notes": f"Phase 45 import quality: {row.review_status}; missing={row.metadata_missing}",
            "document_id": row.document_id,
            "updated_at": now,
        }
        if existing:
            connection.execute(
                """
                update sources set title=:title, normalized_title=:normalized_title, authors=:authors,
                year=:year, venue=:venue, category=:category, discovered_via=:discovered_via,
                doi=:doi, normalized_doi=:normalized_doi, url=:url, normalized_url=:normalized_url,
                pdf_url=:pdf_url, abstract=:abstract, keywords=:keywords, language=:language,
                citation_count=:citation_count, source_type=:source_type, trust_level=:trust_level,
                access_rights=:access_rights, fulltext_permission=:fulltext_permission,
                license_or_terms=:license_or_terms, local_path=:local_path, status=:status,
                notes=:notes, document_id=:document_id, updated_at=:updated_at
                where source_id=:source_id
                """,
                payload,
            )
        else:
            payload["created_at"] = now
            connection.execute(
                """
                insert into sources (
                    source_id, title, normalized_title, authors, year, venue, category,
                    discovered_via, doi, normalized_doi, url, normalized_url, pdf_url,
                    abstract, keywords, language, citation_count, source_type, trust_level,
                    access_rights, fulltext_permission, license_or_terms, local_path, status,
                    notes, document_id, created_at, updated_at
                ) values (
                    :source_id, :title, :normalized_title, :authors, :year, :venue, :category,
                    :discovered_via, :doi, :normalized_doi, :url, :normalized_url, :pdf_url,
                    :abstract, :keywords, :language, :citation_count, :source_type, :trust_level,
                    :access_rights, :fulltext_permission, :license_or_terms, :local_path, :status,
                    :notes, :document_id, :created_at, :updated_at
                )
                """,
                payload,
            )
        count += 1
    connection.commit()
    return count


def write_outputs(rows: list[QualityAuditRow], summary: QualityAuditSummary, output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "phase12_quality_audit.csv"
    review_path = output_dir / "phase12_review_queue.csv"
    summary_path = output_dir / "phase12_quality_summary.json"
    payload = [asdict(row) for row in rows]
    with audit_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(payload)
    with review_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(row for row in payload if row["review_status"] == "review_required")
    summary_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit_path, review_path, summary_path


def summarize(rows: list[QualityAuditRow], sources_upserted: int) -> QualityAuditSummary:
    return QualityAuditSummary(
        total_rows=len(rows),
        imported_rows=sum(1 for row in rows if row.import_status == "imported"),
        review_required=sum(1 for row in rows if row.review_status == "review_required"),
        cloud_candidate=sum(1 for row in rows if row.review_status == "cloud_candidate"),
        skipped_duplicate_or_not_ready=sum(1 for row in rows if row.review_status == "skipped"),
        empty_rows=sum(1 for row in rows if row.import_status == "empty"),
        suspected_scanned=sum(1 for row in rows if row.suspected_scanned),
        sources_upserted=sources_upserted,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Phase 45 imported literature quality.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--import-results", default=str(DEFAULT_IMPORT_RESULTS_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--upsert-sources", action="store_true")
    args = parser.parse_args()

    with sqlite3.connect(args.db_path) as connection:
        rows = audit_quality(read_csv(Path(args.manifest)), read_csv(Path(args.import_results)), connection)
        sources_upserted = upsert_sources(connection, rows) if args.upsert_sources else 0
    summary = summarize(rows, sources_upserted=sources_upserted)
    audit_path, review_path, summary_path = write_outputs(rows, summary, Path(args.output_dir))
    print(f"wrote {audit_path}")
    print(f"wrote {review_path}")
    print(f"wrote {summary_path}")
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))


if __name__ == "__main__":
    main()
