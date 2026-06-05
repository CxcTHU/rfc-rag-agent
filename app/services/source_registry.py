from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from app.db.models import Source
from app.db.repositories import SourceCreate, SourceRepository
from app.services.source_collection import (
    SourceCandidate,
    make_source_id,
    merge_semicolon_values,
    metadata_markdown,
    normalize_doi,
    normalize_title,
    read_candidates_csv,
    sanitize_filename,
)
from app.services.ingestion.service import ImportDocumentResult, IngestionConfig, IngestionService


SOURCE_STATUSES = {"candidate", "collected", "imported", "duplicate", "rejected"}
FULLTEXT_PERMISSIONS = {"open_access", "institutional_access", "metadata_only", "unknown"}
TRUST_LEVELS = {"high", "medium", "low", "unknown"}


@dataclass(frozen=True)
class SourceRegistryResult:
    source: Source
    created: bool
    duplicate_of_source_id: str | None = None


@dataclass(frozen=True)
class SourceRegistrySummary:
    total: int
    created: int
    updated: int
    duplicates: int


@dataclass(frozen=True)
class SourceReindexResult:
    source: Source
    import_result: ImportDocumentResult


class SourceNotFoundError(ValueError):
    pass


class SourceReindexError(ValueError):
    pass


class SourceRegistryService:
    def __init__(self, repository: SourceRepository) -> None:
        self.repository = repository

    def register_candidate(
        self,
        candidate: SourceCandidate,
        document_id: int | None = None,
    ) -> SourceRegistryResult:
        source_data = candidate_to_source_create(candidate, document_id=document_id)
        existing_source = self.repository.get_by_source_id(source_data.source_id)
        if existing_source is not None:
            merged_data = merge_source_data(existing_source, source_data)
            source = self.repository.update_source(existing_source, merged_data)
            return SourceRegistryResult(source=source, created=False)

        duplicate_source = self.repository.find_duplicate(
            normalized_doi=source_data.normalized_doi,
            normalized_url=source_data.normalized_url,
            normalized_title=source_data.normalized_title,
            exclude_source_id=source_data.source_id,
        )
        if duplicate_source is not None:
            merged_data = merge_source_data(
                duplicate_source,
                source_data,
                duplicate_source_id=source_data.source_id,
            )
            source = self.repository.update_source(duplicate_source, merged_data)
            return SourceRegistryResult(
                source=source,
                created=False,
                duplicate_of_source_id=duplicate_source.source_id,
            )

        source = self.repository.create_source(source_data)
        return SourceRegistryResult(source=source, created=True)

    def register_candidates(self, candidates: list[SourceCandidate]) -> SourceRegistrySummary:
        created = 0
        updated = 0
        duplicates = 0
        for candidate in candidates:
            result = self.register_candidate(candidate)
            if result.created:
                created += 1
            elif result.duplicate_of_source_id:
                duplicates += 1
            else:
                updated += 1
        return SourceRegistrySummary(
            total=len(candidates),
            created=created,
            updated=updated,
            duplicates=duplicates,
        )

    def reindex_source(
        self,
        source_id: str,
        ingestion_config: IngestionConfig | None = None,
        metadata_cards_dir: Path = Path("data/imports/metadata_corpus"),
    ) -> SourceReindexResult:
        source = self.repository.get_by_source_id(source_id)
        if source is None:
            raise SourceNotFoundError(f"Source {source_id} was not found.")

        import_path = resolve_reindex_path(source, metadata_cards_dir)
        ingestion_service = IngestionService(self.repository.db, ingestion_config)
        import_result = ingestion_service.import_document(
            import_path,
            title=source.title,
            source_path=source.url or source.pdf_url or source.doi or source.local_path or str(import_path),
            file_name=import_path.name,
            source_type=source.source_type,
        )
        source_data = source_to_source_create(
            source,
            document_id=import_result.document_id,
            status="imported",
            local_path=str(import_path) if not source.local_path else source.local_path,
        )
        updated_source = self.repository.update_source(source, source_data)
        return SourceReindexResult(source=updated_source, import_result=import_result)


def read_existing_source_candidates(
    candidate_csv_paths: list[Path] | None = None,
    fulltext_manifest_paths: list[Path] | None = None,
    metadata_csv_paths: list[Path] | None = None,
    metadata_cards_dirs: list[Path] | None = None,
) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    for path in candidate_csv_paths or []:
        candidates.extend(read_candidates_csv(path))
    for path in fulltext_manifest_paths or []:
        candidates.extend(read_candidates_csv(path))
    for path in metadata_csv_paths or []:
        candidates.extend(read_candidates_csv(path))
    for directory in metadata_cards_dirs or []:
        candidates.extend(read_metadata_cards(directory))
    return candidates


def read_metadata_cards(cards_dir: Path) -> list[SourceCandidate]:
    if not cards_dir.exists():
        return []
    return [
        candidate
        for candidate in (read_metadata_card(path) for path in sorted(cards_dir.glob("*.md")))
        if candidate is not None
    ]


def read_metadata_card(path: Path) -> SourceCandidate | None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    title = ""
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    active_section = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if active_section:
                sections.setdefault(active_section, []).append("")
            continue
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            active_section = normalize_card_key(line[3:])
            sections.setdefault(active_section, [])
            continue
        if line.startswith("- ") and ":" in line and not active_section:
            key, value = line[2:].split(":", 1)
            fields[normalize_card_key(key)] = value.strip()
            continue
        if active_section:
            sections.setdefault(active_section, []).append(raw_line.strip())

    title = title or fields.get("title", "")
    if not title:
        return None

    source_id = fields.get("source_id") or make_source_id(
        "metadata_card",
        title=title,
        doi=fields.get("doi", ""),
        url=fields.get("url", ""),
    )
    keywords = clean_section(sections.get("keywords", []))
    abstract = clean_section(sections.get("abstract", []))
    return SourceCandidate(
        source_id=source_id,
        title=title,
        authors=none_markers_to_empty(fields.get("authors", "")),
        year=none_markers_to_empty(fields.get("year", "")),
        venue=none_markers_to_empty(fields.get("venue", "")),
        category=none_markers_to_empty(fields.get("category", "")),
        discovered_via=none_markers_to_empty(fields.get("discovered_via", "Metadata card")),
        doi=none_markers_to_empty(fields.get("doi", "")),
        url=none_markers_to_empty(fields.get("url", "")),
        abstract=none_markers_to_empty(abstract),
        keywords=none_markers_to_empty(keywords),
        language=none_markers_to_empty(fields.get("language", "")),
        citation_count=none_markers_to_empty(fields.get("citation_count", "")),
        source_type="metadata_record",
        access_rights="metadata",
        local_path=str(path),
        status="collected",
        notes=f"metadata_card={path.name}",
    )


def resolve_reindex_path(source: Source, metadata_cards_dir: Path) -> Path:
    if source.local_path:
        local_path = Path(source.local_path)
        if local_path.exists():
            return local_path
        if source.fulltext_permission != "metadata_only" and source.source_type != "metadata_record":
            raise SourceReindexError(f"Local source file was not found: {local_path}")

    if can_generate_metadata_card(source):
        return write_source_metadata_card(source, metadata_cards_dir)
    raise SourceReindexError(f"Source {source.source_id} has no local file or metadata to reindex.")


def can_generate_metadata_card(source: Source) -> bool:
    return bool(source.title and (source.abstract or source.keywords or source.url or source.doi))


def write_source_metadata_card(source: Source, metadata_cards_dir: Path) -> Path:
    metadata_cards_dir.mkdir(parents=True, exist_ok=True)
    file_name = sanitize_filename(f"{source.year or 'unknown'}_{source.title}_{source.source_id}", 170)
    path = metadata_cards_dir / f"{file_name}.md"
    path.write_text(metadata_markdown(source_to_candidate(source)), encoding="utf-8")
    return path


def source_to_candidate(source: Source) -> SourceCandidate:
    return SourceCandidate(
        source_id=source.source_id,
        title=source.title,
        authors=source.authors or "",
        year=source.year or "",
        venue=source.venue or "",
        category=source.category or "",
        discovered_via=source.discovered_via or "",
        doi=source.doi or "",
        url=source.url or "",
        pdf_url=source.pdf_url or "",
        abstract=source.abstract or "",
        keywords=source.keywords or "",
        language=source.language or "",
        citation_count=str(source.citation_count) if source.citation_count is not None else "",
        source_type=source.source_type,
        access_rights=source.access_rights,
        license_or_terms=source.license_or_terms or "",
        local_path=source.local_path or "",
        status=source.status,
        notes=source.notes or "",
    )


def source_to_source_create(
    source: Source,
    document_id: int | None = None,
    status: str | None = None,
    local_path: str | None = None,
) -> SourceCreate:
    return SourceCreate(
        source_id=source.source_id,
        title=source.title,
        normalized_title=source.normalized_title,
        authors=source.authors,
        year=source.year,
        venue=source.venue,
        category=source.category,
        discovered_via=source.discovered_via,
        doi=source.doi,
        normalized_doi=source.normalized_doi,
        url=source.url,
        normalized_url=source.normalized_url,
        pdf_url=source.pdf_url,
        abstract=source.abstract,
        keywords=source.keywords,
        language=source.language,
        citation_count=source.citation_count,
        source_type=source.source_type,
        trust_level=source.trust_level,
        access_rights=source.access_rights,
        fulltext_permission=source.fulltext_permission,
        license_or_terms=source.license_or_terms,
        local_path=local_path if local_path is not None else source.local_path,
        status=status or source.status,
        notes=source.notes,
        document_id=document_id if document_id is not None else source.document_id,
    )
    keywords = clean_section(sections.get("keywords", []))
    abstract = clean_section(sections.get("abstract", []))
    return SourceCandidate(
        source_id=source_id,
        title=title,
        authors=none_markers_to_empty(fields.get("authors", "")),
        year=none_markers_to_empty(fields.get("year", "")),
        venue=none_markers_to_empty(fields.get("venue", "")),
        category=none_markers_to_empty(fields.get("category", "")),
        discovered_via=none_markers_to_empty(fields.get("discovered_via", "Metadata card")),
        doi=none_markers_to_empty(fields.get("doi", "")),
        url=none_markers_to_empty(fields.get("url", "")),
        abstract=none_markers_to_empty(abstract),
        keywords=none_markers_to_empty(keywords),
        language=none_markers_to_empty(fields.get("language", "")),
        citation_count=none_markers_to_empty(fields.get("citation_count", "")),
        source_type="metadata_record",
        access_rights="metadata",
        local_path=str(path),
        status="collected",
        notes=f"metadata_card={path.name}",
    )


def candidate_to_source_create(
    candidate: SourceCandidate,
    document_id: int | None = None,
) -> SourceCreate:
    title = clean_text(candidate.title)
    if not title:
        raise ValueError("source title is required")

    source_id = candidate.source_id or make_source_id(
        "source",
        title=title,
        doi=candidate.doi,
        url=candidate.url or candidate.pdf_url,
    )
    normalized_doi = empty_to_none(normalize_doi(candidate.doi))
    normalized_url = empty_to_none(normalize_url(candidate.url or candidate.pdf_url))
    normalized_title = normalize_title(title)
    return SourceCreate(
        source_id=source_id,
        title=title,
        normalized_title=normalized_title,
        authors=empty_to_none(candidate.authors),
        year=empty_to_none(candidate.year),
        venue=empty_to_none(candidate.venue),
        category=empty_to_none(candidate.category),
        discovered_via=empty_to_none(candidate.discovered_via),
        doi=empty_to_none(candidate.doi),
        normalized_doi=normalized_doi,
        url=empty_to_none(candidate.url),
        normalized_url=normalized_url,
        pdf_url=empty_to_none(candidate.pdf_url),
        abstract=empty_to_none(candidate.abstract),
        keywords=empty_to_none(candidate.keywords),
        language=empty_to_none(candidate.language),
        citation_count=parse_optional_int(candidate.citation_count),
        source_type=clean_text(candidate.source_type) or "candidate",
        trust_level=derive_trust_level(candidate),
        access_rights=clean_text(candidate.access_rights) or "unknown",
        fulltext_permission=derive_fulltext_permission(candidate),
        license_or_terms=empty_to_none(candidate.license_or_terms),
        local_path=empty_to_none(candidate.local_path),
        status=derive_status(candidate),
        notes=empty_to_none(candidate.notes),
        document_id=document_id,
    )


def normalize_url(url: str | None) -> str:
    value = clean_text(url or "")
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value.casefold()

    scheme = parsed.scheme.casefold()
    netloc = parsed.netloc.casefold()
    if (scheme == "http" and netloc.endswith(":80")) or (scheme == "https" and netloc.endswith(":443")):
        netloc = netloc.rsplit(":", 1)[0]
    path = urllib.parse.quote(urllib.parse.unquote(parsed.path or ""), safe="/-._~")
    if path != "/":
        path = path.rstrip("/")
    query_pairs = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
    ]
    query = urllib.parse.urlencode(sorted(query_pairs))
    return urllib.parse.urlunparse((scheme, netloc, path, "", query, ""))


def normalize_card_key(value: str) -> str:
    return re.sub(r"[\s_\-]+", "_", value.strip().casefold())


def clean_section(lines: list[str]) -> str:
    text = "\n".join(line for line in lines).strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def none_markers_to_empty(value: str) -> str:
    cleaned = clean_text(value)
    return "" if cleaned.casefold() in {"unknown", "none", "n/a", "no public abstract was found in the collected metadata."} else cleaned


def derive_trust_level(candidate: SourceCandidate) -> str:
    text = candidate_text(candidate)
    if any(term in text for term in ["rejected", "unknown source"]):
        return "low"
    if any(term in text for term in ["institutional_access_pdf", "open_access_pdf", "doi.org", "crossref", "openalex"]):
        return "high"
    if any(term in text for term in ["tsinghua.edu.cn", "mdpi.com", "engineering.org.cn", "sciencedirect.com"]):
        return "high"
    if normalize_doi(candidate.doi):
        return "high"
    if candidate.abstract or candidate.venue or candidate.url:
        return "medium"
    return "unknown"


def derive_fulltext_permission(candidate: SourceCandidate) -> str:
    text = candidate_text(candidate)
    if "institutional" in text or "cnki" in text:
        return "institutional_access"
    if "metadata_record" in text or "metadata_export" in text:
        return "metadata_only"
    if "metadata" == clean_text(candidate.access_rights).casefold() and not candidate.local_path:
        return "metadata_only"
    if "open_access_pdf" in text or "open access" in text or "open proceedings pdf" in text:
        return "open_access"
    if candidate.local_path and candidate.local_path.casefold().endswith(".pdf"):
        return "open_access" if "open" in text else "unknown"
    return "unknown"


def derive_status(candidate: SourceCandidate) -> str:
    status = clean_text(candidate.status).casefold()
    if status in {"imported", "duplicate", "rejected", "collected"}:
        return status
    if status in {"downloaded", "saved"}:
        return "collected"
    if candidate.local_path:
        return "collected"
    if status == "candidate":
        return "candidate"
    return "candidate"


def merge_source_data(
    existing_source: Source,
    incoming: SourceCreate,
    duplicate_source_id: str | None = None,
) -> SourceCreate:
    return SourceCreate(
        source_id=existing_source.source_id,
        title=pick(existing_source.title, incoming.title) or incoming.title,
        normalized_title=existing_source.normalized_title or incoming.normalized_title,
        authors=pick(existing_source.authors, incoming.authors),
        year=pick(existing_source.year, incoming.year),
        venue=pick(existing_source.venue, incoming.venue),
        category=merge_semicolon_values(existing_source.category or "", incoming.category or "") or None,
        discovered_via=merge_semicolon_values(existing_source.discovered_via or "", incoming.discovered_via or "") or None,
        doi=pick(existing_source.doi, incoming.doi),
        normalized_doi=pick(existing_source.normalized_doi, incoming.normalized_doi),
        url=pick(existing_source.url, incoming.url),
        normalized_url=pick(existing_source.normalized_url, incoming.normalized_url),
        pdf_url=pick(existing_source.pdf_url, incoming.pdf_url),
        abstract=pick_longer(existing_source.abstract, incoming.abstract),
        keywords=merge_semicolon_values(existing_source.keywords or "", incoming.keywords or "") or None,
        language=pick(existing_source.language, incoming.language),
        citation_count=pick_larger_int(existing_source.citation_count, incoming.citation_count),
        source_type=pick(existing_source.source_type, incoming.source_type) or "candidate",
        trust_level=pick_stronger_trust(existing_source.trust_level, incoming.trust_level),
        access_rights=pick(existing_source.access_rights, incoming.access_rights) or "unknown",
        fulltext_permission=pick_stronger_permission(
            existing_source.fulltext_permission,
            incoming.fulltext_permission,
        ),
        license_or_terms=pick(existing_source.license_or_terms, incoming.license_or_terms),
        local_path=pick(existing_source.local_path, incoming.local_path),
        status=pick_more_advanced_status(existing_source.status, incoming.status),
        notes=merge_notes(existing_source.notes, incoming.notes, duplicate_source_id),
        document_id=existing_source.document_id or incoming.document_id,
    )


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def empty_to_none(value: str | None) -> str | None:
    cleaned = clean_text(value)
    return cleaned or None


def parse_optional_int(value: str | None) -> int | None:
    cleaned = clean_text(value)
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def candidate_text(candidate: SourceCandidate) -> str:
    return " ".join(
        [
            candidate.source_id,
            candidate.title,
            candidate.venue,
            candidate.discovered_via,
            candidate.doi,
            candidate.url,
            candidate.pdf_url,
            candidate.source_type,
            candidate.access_rights,
            candidate.license_or_terms,
            candidate.local_path,
            candidate.status,
            candidate.notes,
        ]
    ).casefold()


def pick(left: str | None, right: str | None) -> str | None:
    return left or right


def pick_longer(left: str | None, right: str | None) -> str | None:
    left_value = left or ""
    right_value = right or ""
    return left_value if len(left_value) >= len(right_value) else right_value or None


def pick_larger_int(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def pick_stronger_trust(left: str, right: str) -> str:
    rank = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
    return left if rank.get(left, 0) >= rank.get(right, 0) else right


def pick_stronger_permission(left: str, right: str) -> str:
    rank = {"unknown": 0, "metadata_only": 1, "institutional_access": 2, "open_access": 3}
    return left if rank.get(left, 0) >= rank.get(right, 0) else right


def pick_more_advanced_status(left: str, right: str) -> str:
    rank = {"candidate": 0, "duplicate": 1, "rejected": 1, "collected": 2, "imported": 3}
    return left if rank.get(left, 0) >= rank.get(right, 0) else right


def merge_notes(left: str | None, right: str | None, duplicate_source_id: str | None) -> str | None:
    duplicate_note = f"merged_duplicate_source_id={duplicate_source_id}" if duplicate_source_id else None
    notes = [value for value in [left, right, duplicate_note] if value]
    return "; ".join(dict.fromkeys(notes)) or None
