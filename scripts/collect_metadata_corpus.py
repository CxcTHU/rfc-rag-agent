from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.db.models import Document  # noqa: E402
from app.services.ingestion.service import IngestionConfig, IngestionService  # noqa: E402
from app.services.source_collection import (  # noqa: E402
    SourceCandidate,
    classify_categories,
    compact_authors,
    dedupe_candidates,
    filter_relevant_candidates,
    infer_language,
    make_source_id,
    metadata_markdown,
    read_candidates_csv,
    sanitize_filename,
    strip_markup,
    write_candidates_csv,
    write_candidates_jsonl,
)
from scripts.collect_sources import (  # noqa: E402
    DEFAULT_QUERIES,
    collect_crossref,
    collect_openalex,
    collect_semantic_scholar,
)
from sqlalchemy import or_, select  # noqa: E402


FIELD_ALIASES = {
    "title": ["title", "paper title", "article title", "题名", "篇名", "文献题名", "标题"],
    "authors": ["authors", "author", "creators", "作者", "著者"],
    "year": ["year", "publication year", "date", "发表时间", "出版年", "年份", "年"],
    "venue": ["venue", "journal", "source", "publication", "container title", "刊名", "来源", "期刊", "会议"],
    "abstract": ["abstract", "summary", "摘要"],
    "keywords": ["keywords", "keyword", "key words", "关键词"],
    "doi": ["doi"],
    "url": ["url", "link", "链接", "全文链接", "来源链接"],
    "language": ["language", "语种", "语言"],
    "citation_count": ["citation count", "citations", "被引", "被引频次", "引用次数"],
}

RIS_TAGS = {
    "TI": "title",
    "T1": "title",
    "AU": "authors",
    "A1": "authors",
    "PY": "year",
    "Y1": "year",
    "DA": "year",
    "T2": "venue",
    "JO": "venue",
    "JF": "venue",
    "JA": "venue",
    "AB": "abstract",
    "N2": "abstract",
    "KW": "keywords",
    "DO": "doi",
    "UR": "url",
    "L1": "url",
    "L2": "url",
    "LA": "language",
}

PERCENT_TAGS = {
    "%T": "title",
    "%A": "authors",
    "%D": "year",
    "%J": "venue",
    "%B": "venue",
    "%X": "abstract",
    "%K": "keywords",
    "%R": "doi",
    "%U": "url",
    "%G": "language",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a large RFC metadata corpus from APIs and export files.")
    parser.add_argument("--query", action="append", dest="queries", help="Search query. Can be repeated.")
    parser.add_argument("--limit", type=int, default=80, help="Results per API per query.")
    parser.add_argument("--out", default="data/metadata/rfc_papers_metadata.csv")
    parser.add_argument("--jsonl-out", default="data/metadata/rfc_papers_metadata.jsonl")
    parser.add_argument("--cards-dir", default="data/imports/metadata_corpus")
    parser.add_argument("--import-export", action="append", default=[], help="CSV/TSV/RIS/EndNote export file to merge.")
    parser.add_argument("--no-api", action="store_true", help="Only parse export files; skip public API collection.")
    parser.add_argument("--skip-openalex", action="store_true", help="Skip OpenAlex collection.")
    parser.add_argument("--skip-semantic-scholar", action="store_true", help="Skip Semantic Scholar collection.")
    parser.add_argument("--skip-crossref", action="store_true", help="Skip Crossref collection.")
    parser.add_argument("--no-rfc-filter", action="store_true", help="Keep adjacent/non-RFC records.")
    parser.add_argument("--max-records", type=int, default=500, help="Maximum records to write/import.")
    parser.add_argument("--import-to-db", action="store_true", help="Generate markdown cards and import them as metadata records.")
    parser.add_argument("--mailto", default="", help="Email for polite OpenAlex/Crossref API use.")
    parser.add_argument("--semantic-scholar-api-key", default="", help="Optional Semantic Scholar API key.")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=80)
    args = parser.parse_args()

    queries = args.queries or DEFAULT_QUERIES
    candidates: list[SourceCandidate] = []

    if not args.no_api:
        for query in queries:
            if not args.skip_openalex:
                candidates.extend(collect_openalex(query, args.limit, args.mailto))
            if not args.skip_semantic_scholar:
                candidates.extend(collect_semantic_scholar(query, args.limit, args.semantic_scholar_api_key))
            if not args.skip_crossref:
                candidates.extend(collect_crossref(query, args.limit, args.mailto))
            time.sleep(1)

    for export_file in args.import_export:
        candidates.extend(read_export_candidates(Path(export_file)))

    merged = dedupe_candidates([*read_candidates_csv(Path(args.out)), *candidates])
    if not args.no_rfc_filter:
        before_filter = len(merged)
        merged = filter_relevant_candidates(merged)
        print(f"rfc_filter kept {len(merged)} of {before_filter} records")

    limited = sorted(
        merged,
        key=lambda item: (has_text(item.abstract), int_or_zero(item.citation_count), item.year or ""),
        reverse=True,
    )[: args.max_records]
    limited = sorted(limited, key=lambda item: (item.year or "9999", item.title))

    write_candidates_csv(Path(args.out), limited)
    write_candidates_jsonl(Path(args.jsonl_out), limited)
    print(f"wrote {len(limited)} metadata records to {args.out}")
    print(f"records_with_abstract={sum(1 for item in limited if item.abstract)}")

    if args.import_to_db:
        card_rows = write_metadata_cards(limited, Path(args.cards_dir))
        import_metadata_cards(
            card_rows,
            raw_dir=args.raw_dir,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )


def read_export_candidates(path: Path) -> list[SourceCandidate]:
    if not path.exists():
        print(f"export file not found: {path}")
        return []
    if path.suffix.lower() in {".ris", ".enw"}:
        return read_ris_export(path)
    if path.suffix.lower() in {".txt"}:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if "%T" in text or "%A" in text:
            return read_percent_export(path)
        if "  -" in text:
            return read_ris_export(path)
    return read_tabular_export(path)


def read_tabular_export(path: Path) -> list[SourceCandidate]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=delimiter)
        return [candidate_from_mapping(row, path.stem, f"Export:{path.name}") for row in reader]


def read_ris_export(path: Path) -> list[SourceCandidate]:
    records: list[dict[str, list[str]]] = []
    current: dict[str, list[str]] = {}
    last_field = ""
    for raw_line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        match = re.match(r"^([A-Z0-9]{2})\s{2}-\s?(.*)$", line)
        if match:
            tag, value = match.groups()
            if tag == "ER":
                if current:
                    records.append(current)
                current = {}
                last_field = ""
                continue
            field = RIS_TAGS.get(tag)
            if field:
                current.setdefault(field, []).append(value.strip())
                last_field = field
            continue
        if last_field and line.startswith(" "):
            current[last_field][-1] += " " + line.strip()
    if current:
        records.append(current)
    return [candidate_from_lists(record, path.stem, f"Export:{path.name}") for record in records]


def read_percent_export(path: Path) -> list[SourceCandidate]:
    records: list[dict[str, list[str]]] = []
    current: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        if not line.strip():
            if current:
                records.append(current)
                current = {}
            continue
        tag = line[:2]
        field = PERCENT_TAGS.get(tag)
        if field:
            current.setdefault(field, []).append(line[2:].strip())
    if current:
        records.append(current)
    return [candidate_from_lists(record, path.stem, f"Export:{path.name}") for record in records]


def candidate_from_mapping(row: dict[str, str], source_prefix: str, discovered_via: str) -> SourceCandidate:
    values = {
        field: first_row_value(row, aliases)
        for field, aliases in FIELD_ALIASES.items()
    }
    return build_export_candidate(values, source_prefix, discovered_via)


def candidate_from_lists(record: dict[str, list[str]], source_prefix: str, discovered_via: str) -> SourceCandidate:
    values = {
        field: "; ".join(items)
        for field, items in record.items()
    }
    return build_export_candidate(values, source_prefix, discovered_via)


def build_export_candidate(values: dict[str, str], source_prefix: str, discovered_via: str) -> SourceCandidate:
    title = clean_cell(values.get("title", ""))
    abstract = strip_markup(clean_cell(values.get("abstract", "")))
    keywords = normalize_multi_value(clean_cell(values.get("keywords", "")))
    authors = normalize_multi_value(clean_cell(values.get("authors", "")))
    venue = clean_cell(values.get("venue", ""))
    doi = clean_cell(values.get("doi", ""))
    url = clean_cell(values.get("url", ""))
    year = extract_year(clean_cell(values.get("year", "")))
    language = clean_cell(values.get("language", "")) or infer_language(title, abstract)
    text_for_category = " ".join([title, abstract, keywords, venue])
    return SourceCandidate(
        source_id=make_source_id(f"export_{sanitize_filename(source_prefix, 30)}", title, doi, url),
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        category=classify_categories(text_for_category),
        discovered_via=discovered_via,
        doi=doi,
        url=url,
        abstract=abstract,
        keywords=keywords,
        language=language,
        citation_count=clean_cell(values.get("citation_count", "")),
        source_type="metadata_export",
        access_rights="metadata",
        notes=f"export_source={source_prefix}",
    )


def first_row_value(row: dict[str, str], aliases: list[str]) -> str:
    normalized_row = {normalize_header(key): value for key, value in row.items()}
    for alias in aliases:
        value = normalized_row.get(normalize_header(alias), "")
        if value:
            return value
    return ""


def normalize_header(value: str) -> str:
    return re.sub(r"[\s_:/\\\-（）()]+", "", value or "").casefold()


def normalize_multi_value(value: str) -> str:
    return "; ".join(part.strip() for part in re.split(r"[;；\n]+", value) if part.strip())


def clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def extract_year(value: str) -> str:
    match = re.search(r"(19|20)\d{2}", value)
    return match.group(0) if match else value[:4]


def write_metadata_cards(candidates: list[SourceCandidate], cards_dir: Path) -> list[tuple[SourceCandidate, Path]]:
    cards_dir.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[SourceCandidate, Path]] = []
    for candidate in candidates:
        base = sanitize_filename(
            f"{candidate.year or 'unknown'}_{candidate.title}_{candidate.source_id}",
            max_length=170,
        )
        path = cards_dir / f"{base}.md"
        path.write_text(metadata_markdown(candidate), encoding="utf-8")
        rows.append((candidate, path))
    print(f"wrote {len(rows)} markdown metadata cards to {cards_dir}")
    return rows


def import_metadata_cards(
    card_rows: list[tuple[SourceCandidate, Path]],
    raw_dir: str,
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    init_db()
    with SessionLocal() as db:
        service = IngestionService(
            db,
            IngestionConfig(raw_dir=raw_dir, chunk_size=chunk_size, chunk_overlap=chunk_overlap),
        )
        for candidate, path in card_rows:
            source_path = candidate.url or candidate.doi or str(path)
            existing = db.scalar(
                select(Document).where(
                    Document.source_type == "metadata_record",
                    or_(Document.source_path == source_path, Document.title == candidate.title),
                )
            )
            if existing is not None:
                print(f"duplicate\tdocument_id={existing.id}\tchunks=skip\t{candidate.title}")
                continue
            result = service.import_document(
                path,
                title=candidate.title,
                source_path=source_path,
                file_name=path.name,
                source_type="metadata_record",
            )
            print(f"{result.status}\tdocument_id={result.document_id}\tchunks={result.chunk_count}\t{candidate.title}")


def has_text(value: str) -> int:
    return 1 if value else 0


def int_or_zero(value: str) -> int:
    try:
        return int(value or "0")
    except ValueError:
        return 0


if __name__ == "__main__":
    main()
