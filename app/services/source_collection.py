import csv
import hashlib
import html
import json
import re
import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CSV_FIELDS = [
    "source_id",
    "title",
    "authors",
    "year",
    "venue",
    "category",
    "discovered_via",
    "doi",
    "url",
    "pdf_url",
    "abstract",
    "keywords",
    "language",
    "citation_count",
    "source_type",
    "access_rights",
    "license_or_terms",
    "local_path",
    "status",
    "notes",
]

MDPI_ISSN_TO_SLUG = {
    "1996-1944": "materials",
    "2076-3417": "applsci",
    "2075-5309": "buildings",
    "2412-3811": "infrastructures",
}


@dataclass(frozen=True)
class SourceCandidate:
    source_id: str
    title: str
    authors: str = ""
    year: str = ""
    venue: str = ""
    category: str = ""
    discovered_via: str = ""
    doi: str = ""
    url: str = ""
    pdf_url: str = ""
    abstract: str = ""
    keywords: str = ""
    language: str = ""
    citation_count: str = ""
    source_type: str = "open_access_candidate"
    access_rights: str = "unknown"
    license_or_terms: str = ""
    local_path: str = ""
    status: str = "candidate"
    notes: str = ""

    def to_row(self) -> dict[str, str]:
        return {field: getattr(self, field) for field in CSV_FIELDS}


def make_source_id(prefix: str, title: str, doi: str = "", url: str = "") -> str:
    seed = "|".join([prefix, normalize_doi(doi), normalize_title(title), url])
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def normalize_doi(doi: str | None) -> str:
    if not doi:
        return ""
    value = doi.strip().lower()
    value = value.removeprefix("https://doi.org/")
    value = value.removeprefix("http://doi.org/")
    value = value.removeprefix("doi:")
    return value.strip()


def normalize_title(title: str | None) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().casefold())


def compact_authors(authors: Iterable[str], limit: int = 8) -> str:
    names = [author.strip() for author in authors if author and author.strip()]
    if len(names) > limit:
        return "; ".join(names[:limit]) + "; et al."
    return "; ".join(names)


def classify_categories(text: str) -> str:
    normalized = text.casefold()
    rules = [
        ("review", ["review", "综述", "prospect", "literature"]),
        ("filling_capacity", ["filling capacity", "flowing", "flow", "填充", "充填", "自密实"]),
        ("thermal_control", ["hydration heat", "adiabatic", "temperature", "水化热", "温升", "温控"]),
        ("mechanical_properties", ["elastic modulus", "compressive", "strength", "力学", "抗压", "弹性模量"]),
        ("seismic_response", ["seismic", "earthquake", "抗震", "地震"]),
        ("numerical_modeling", ["simulation", "finite element", "mesoscopic", "peridynamics", "lattice boltzmann", "dem", "数值"]),
        ("dam_engineering", ["dam", "大坝", "筑坝", "construction", "施工"]),
    ]
    categories = [name for name, terms in rules if any(term in normalized for term in terms)]
    return ";".join(dict.fromkeys(categories))


def is_relevant_rfc_text(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.casefold())
    false_friend_terms = [
        "concrete-faced rock-fill dam",
        "concrete faced rock-fill dam",
        "concrete-faced rockfill dam",
        "concrete face rockfill dam",
        "混凝土面板堆石坝",
    ]
    if any(term in normalized for term in false_friend_terms):
        return False

    strong_terms = [
        "rock-filled concrete",
        "rock filled concrete",
        "rock-fill concrete",
        "rockfill concrete",
        "self-compacting rock-fill concrete",
        "self-compacted rock-fill concrete",
        "堆石混凝土",
        "自密实堆石混凝土",
    ]
    if any(term in normalized for term in strong_terms):
        return True

    if "self-compacting concrete" in normalized and "prepacked rock" in normalized:
        return True
    if "自密实混凝土" in normalized and ("堆石体" in normalized or "块石" in normalized):
        return True
    if re.search(r"\brfc\b", normalized) and any(
        re.search(pattern, normalized)
        for pattern in [r"\bconcrete\b", r"\bdam\b", r"\bself-compacting\b"]
    ):
        return True

    return False


def filter_relevant_candidates(candidates: Iterable[SourceCandidate]) -> list[SourceCandidate]:
    return [
        candidate
        for candidate in candidates
        if is_relevant_rfc_text(
            " ".join(
                [
                    candidate.title,
                    candidate.venue,
                    candidate.category,
                    candidate.abstract,
                    candidate.keywords,
                ]
            )
        )
    ]


def dedupe_candidates(candidates: Iterable[SourceCandidate]) -> list[SourceCandidate]:
    merged: dict[str, SourceCandidate] = {}
    for candidate in candidates:
        key = normalize_doi(candidate.doi) or normalize_title(candidate.title)
        if not key:
            key = candidate.url or candidate.pdf_url or candidate.source_id
        existing = merged.get(key)
        if existing is None:
            merged[key] = candidate
            continue
        merged[key] = merge_candidate(existing, candidate)
    return sorted(merged.values(), key=lambda item: (item.year or "9999", item.title))


def merge_candidate(left: SourceCandidate, right: SourceCandidate) -> SourceCandidate:
    def pick(a: str, b: str) -> str:
        return a or b

    def pick_longer(a: str, b: str) -> str:
        return a if len(a) >= len(b) else b

    def pick_larger_number(a: str, b: str) -> str:
        try:
            return str(max(int(a or "0"), int(b or "0")))
        except ValueError:
            return pick(a, b)

    discovered = merge_semicolon_values(left.discovered_via, right.discovered_via)
    categories = merge_semicolon_values(left.category, right.category)
    keywords = merge_semicolon_values(left.keywords, right.keywords)
    return SourceCandidate(
        source_id=left.source_id,
        title=pick(left.title, right.title),
        authors=pick(left.authors, right.authors),
        year=pick(left.year, right.year),
        venue=pick(left.venue, right.venue),
        category=categories,
        discovered_via=discovered,
        doi=pick(left.doi, right.doi),
        url=pick(left.url, right.url),
        pdf_url=pick(left.pdf_url, right.pdf_url),
        abstract=pick_longer(left.abstract, right.abstract),
        keywords=keywords,
        language=pick(left.language, right.language),
        citation_count=pick_larger_number(left.citation_count, right.citation_count),
        source_type=pick(left.source_type, right.source_type),
        access_rights=pick(left.access_rights, right.access_rights),
        license_or_terms=pick(left.license_or_terms, right.license_or_terms),
        local_path=pick(left.local_path, right.local_path),
        status=pick(left.status, right.status),
        notes="; ".join(filter(None, [left.notes, right.notes])),
    )


def merge_semicolon_values(*values: str) -> str:
    parts: list[str] = []
    for value in values:
        parts.extend(part.strip() for part in value.split(";") if part.strip())
    return ";".join(dict.fromkeys(parts))


def read_candidates_csv(path: Path) -> list[SourceCandidate]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        return [SourceCandidate(**{field: row.get(field, "") for field in CSV_FIELDS}) for row in csv.DictReader(file)]


def write_candidates_csv(path: Path, candidates: Iterable[SourceCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(candidate.to_row())


def write_candidates_jsonl(path: Path, candidates: Iterable[SourceCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for candidate in candidates:
            file.write(json.dumps(candidate.to_row(), ensure_ascii=False) + "\n")


def decode_openalex_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""
    positioned: list[tuple[int, str]] = []
    for word, indexes in inverted_index.items():
        for index in indexes:
            positioned.append((index, word))
    positioned.sort(key=lambda item: item[0])
    return " ".join(word for _index, word in positioned)


def strip_markup(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def infer_language(*values: str) -> str:
    text = " ".join(value for value in values if value)
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return ""


def metadata_markdown(candidate: SourceCandidate) -> str:
    lines = [
        f"# {candidate.title}",
        "",
        f"- source_id: {candidate.source_id}",
        f"- authors: {candidate.authors or 'unknown'}",
        f"- year: {candidate.year or 'unknown'}",
        f"- venue: {candidate.venue or 'unknown'}",
        f"- category: {candidate.category or 'uncategorized'}",
        f"- discovered_via: {candidate.discovered_via or 'unknown'}",
        f"- doi: {candidate.doi or 'unknown'}",
        f"- url: {candidate.url or 'unknown'}",
        f"- language: {candidate.language or infer_language(candidate.title, candidate.abstract)}",
        f"- citation_count: {candidate.citation_count or 'unknown'}",
        "",
    ]
    if candidate.keywords:
        lines.extend(["## Keywords", "", candidate.keywords, ""])
    lines.extend(["## Abstract", "", candidate.abstract or "No public abstract was found in the collected metadata.", ""])
    return "\n".join(lines).strip() + "\n"


def sanitize_filename(value: str, max_length: int = 120) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value, flags=re.UNICODE)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return (cleaned or "document")[:max_length]


def pdf_filename(candidate: SourceCandidate) -> str:
    year = candidate.year or "unknown"
    base = sanitize_filename(candidate.title)
    return f"{year}_{base}.pdf"


def is_pdf_file(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 5:
        return False
    with path.open("rb") as file:
        return file.read(5).startswith(b"%PDF")


def download_pdf(candidate: SourceCandidate, destination_dir: Path, timeout: int = 40) -> tuple[bool, str]:
    pdf_url = normalize_pdf_url(candidate.pdf_url)
    if not pdf_url:
        return False, "missing pdf_url"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / pdf_filename(candidate)
    request = urllib.request.Request(
        pdf_url,
        headers={"User-Agent": "RFC-RAG-Agent/0.1 academic open-access collector"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            with destination.open("wb") as output:
                shutil.copyfileobj(response, output)
    except Exception as exc:  # pragma: no cover - network-specific
        return False, f"download failed: {exc}"

    if not is_pdf_file(destination):
        destination.unlink(missing_ok=True)
        return False, "downloaded response is not a PDF"
    return True, str(destination)


def normalize_pdf_url(url: str) -> str:
    if not url:
        return ""
    mdpi_static_url = mdpi_static_pdf_url(url)
    return mdpi_static_url or url


def mdpi_static_pdf_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if "mdpi.com" not in parsed.netloc:
        return ""
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 5 or path_parts[-1] != "pdf":
        return ""
    issn, volume, _issue, article = path_parts[:4]
    journal_slug = MDPI_ISSN_TO_SLUG.get(issn)
    if not journal_slug:
        return ""
    try:
        volume_code = str(int(volume)).zfill(2)
        article_code = str(int(article)).zfill(5)
    except ValueError:
        return ""
    filename = f"{journal_slug}-{volume_code}-{article_code}.pdf"
    return f"https://mdpi-res.com/d_attachment/{journal_slug}/{filename[:-4]}/article_deploy/{filename}"


def build_query_url(base_url: str, params: dict[str, str | int]) -> str:
    return f"{base_url}?{urllib.parse.urlencode(params)}"
