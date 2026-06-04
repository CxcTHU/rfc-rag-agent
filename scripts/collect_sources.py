from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.source_collection import (  # noqa: E402
    SourceCandidate,
    build_query_url,
    classify_categories,
    compact_authors,
    decode_openalex_abstract,
    dedupe_candidates,
    download_pdf,
    filter_relevant_candidates,
    infer_language,
    make_source_id,
    normalize_doi,
    normalize_pdf_url,
    read_candidates_csv,
    strip_markup,
    write_candidates_csv,
    write_candidates_jsonl,
)


DEFAULT_QUERIES = [
    "rock-filled concrete",
    "rock filled concrete",
    "rock-filled concrete dam",
    "rockfill concrete dam",
    "self-compacting rock-filled concrete",
    "self-compacting concrete prepacked rock",
    "hydration heat rock-filled concrete",
    "elastic modulus rock-filled concrete",
    "seismic behavior rock-filled concrete dam",
    "堆石混凝土",
    "自密实堆石混凝土",
    "堆石混凝土 大坝",
    "金峰 堆石混凝土",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover RFC papers through scholarly metadata APIs.")
    parser.add_argument("--query", action="append", dest="queries", help="Search query. Can be repeated.")
    parser.add_argument("--limit", type=int, default=50, help="Results per API per query.")
    parser.add_argument("--out", default="data/source_candidates.csv", help="Candidate CSV output path.")
    parser.add_argument("--jsonl-out", default="", help="Optional JSONL output path.")
    parser.add_argument("--download", action="store_true", help="Download open-access PDF candidates.")
    parser.add_argument("--download-dir", default="data/fulltext/open_access_auto", help="PDF download directory.")
    parser.add_argument("--max-downloads", type=int, default=20, help="Maximum PDFs to download this run.")
    parser.add_argument("--mailto", default=os.getenv("OPENALEX_MAILTO", ""), help="Email for polite OpenAlex/Crossref API use.")
    parser.add_argument("--unpaywall-email", default=os.getenv("UNPAYWALL_EMAIL", ""), help="Email required by Unpaywall API.")
    parser.add_argument("--semantic-scholar-api-key", default=os.getenv("SEMANTIC_SCHOLAR_API_KEY", ""), help="Optional Semantic Scholar API key.")
    parser.add_argument("--no-rfc-filter", action="store_true", help="Keep adjacent/non-RFC candidates instead of filtering them out.")
    args = parser.parse_args()

    queries = args.queries or DEFAULT_QUERIES
    candidates: list[SourceCandidate] = []
    for query in queries:
        candidates.extend(collect_openalex(query, args.limit, args.mailto))
        candidates.extend(collect_semantic_scholar(query, args.limit, args.semantic_scholar_api_key))
        candidates.extend(collect_crossref(query, args.limit, args.mailto))
        time.sleep(1)

    merged = dedupe_candidates([*read_candidates_csv(Path(args.out)), *candidates])
    if not args.no_rfc_filter:
        before_filter = len(merged)
        merged = filter_relevant_candidates(merged)
        print(f"rfc_filter kept {len(merged)} of {before_filter} candidates")
    if args.unpaywall_email:
        merged = enrich_with_unpaywall(merged, args.unpaywall_email)

    if args.download:
        merged = download_candidates(merged, Path(args.download_dir), args.max_downloads)

    write_candidates_csv(Path(args.out), merged)
    if args.jsonl_out:
        write_candidates_jsonl(Path(args.jsonl_out), merged)
    print(f"wrote {len(merged)} candidates to {args.out}")
    with_abstract = sum(1 for item in merged if item.abstract)
    downloadable = sum(1 for item in merged if item.pdf_url)
    downloaded = sum(1 for item in merged if item.status == "downloaded")
    print(f"candidates_with_abstract={with_abstract} candidates_with_pdf_url={downloadable} downloaded={downloaded}")


def request_json(url: str, timeout: int = 30, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "RFC-RAG-Agent/0.1 academic metadata collector",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def collect_openalex(query: str, limit: int, mailto: str) -> list[SourceCandidate]:
    params: dict[str, str | int] = {
        "search": query,
        "per-page": min(limit, 200),
    }
    if mailto:
        params["mailto"] = mailto
    url = build_query_url("https://api.openalex.org/works", params)
    try:
        data = request_json(url)
    except Exception as exc:
        print(f"openalex failed for {query!r}: {exc}")
        return []

    candidates: list[SourceCandidate] = []
    for work in data.get("results", []):
        title = work.get("title") or work.get("display_name") or ""
        if not title:
            continue
        authors = compact_authors(
            (authorship.get("author") or {}).get("display_name", "")
            for authorship in work.get("authorships", [])
        )
        primary = work.get("primary_location") or {}
        locations = work.get("locations") or []
        pdf_url = normalize_pdf_url(primary.get("pdf_url") or first_pdf_url(locations))
        source = primary.get("source") or {}
        license_text = primary.get("license") or ""
        doi = normalize_doi(work.get("doi") or "")
        open_access = work.get("open_access") or {}
        oa_status = open_access.get("oa_status") or ""
        landing_url = open_access.get("oa_url") or work.get("doi") or work.get("id") or ""
        abstract = decode_openalex_abstract(work.get("abstract_inverted_index"))
        keywords = compact_authors(
            (concept.get("display_name") or "") for concept in work.get("concepts", [])
        )
        text_for_category = " ".join([title, abstract, keywords, source.get("display_name") or "", query])
        candidates.append(
            SourceCandidate(
                source_id=make_source_id("openalex", title, doi, landing_url),
                title=title,
                authors=authors,
                year=str(work.get("publication_year") or ""),
                venue=source.get("display_name") or "",
                category=classify_categories(text_for_category),
                discovered_via="OpenAlex",
                doi=doi,
                url=landing_url,
                pdf_url=pdf_url or "",
                abstract=abstract,
                keywords=keywords,
                language=work.get("language") or infer_language(title, abstract),
                citation_count=str(work.get("cited_by_count") or ""),
                access_rights=oa_status or "unknown",
                license_or_terms=license_text or "",
                notes=f"query={query}",
            )
        )
    return candidates


def first_pdf_url(locations: list[dict[str, Any]]) -> str:
    for location in locations:
        pdf_url = location.get("pdf_url")
        if pdf_url:
            return pdf_url
    return ""


def collect_semantic_scholar(query: str, limit: int, api_key: str = "") -> list[SourceCandidate]:
    params = {
        "query": query,
        "limit": min(limit, 100),
        "fields": "title,year,authors,venue,url,abstract,externalIds,openAccessPdf,isOpenAccess,citationCount,fieldsOfStudy",
    }
    url = build_query_url("https://api.semanticscholar.org/graph/v1/paper/search", params)
    try:
        headers = {"x-api-key": api_key} if api_key else {}
        data = request_json(url, headers=headers)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            print(f"semantic scholar rate-limited for {query!r}; retrying after 10 seconds")
            time.sleep(10)
            try:
                headers = {"x-api-key": api_key} if api_key else {}
                data = request_json(url, headers=headers)
            except Exception as retry_exc:
                print(f"semantic scholar failed for {query!r}: {retry_exc}")
                return []
        else:
            print(f"semantic scholar failed for {query!r}: {exc}")
            return []
    except Exception as exc:
        print(f"semantic scholar failed for {query!r}: {exc}")
        return []

    candidates: list[SourceCandidate] = []
    for paper in data.get("data", []):
        title = paper.get("title") or ""
        if not title:
            continue
        external = paper.get("externalIds") or {}
        doi = normalize_doi(external.get("DOI") or "")
        pdf = paper.get("openAccessPdf") or {}
        pdf_url = normalize_pdf_url(pdf.get("url") or "")
        access = "open" if paper.get("isOpenAccess") else "unknown"
        abstract = strip_markup(paper.get("abstract") or "")
        keywords = compact_authors(paper.get("fieldsOfStudy") or [])
        text_for_category = " ".join([title, abstract, keywords, query])
        candidates.append(
            SourceCandidate(
                source_id=make_source_id("s2", title, doi, paper.get("url") or ""),
                title=title,
                authors=compact_authors(author.get("name", "") for author in paper.get("authors", [])),
                year=str(paper.get("year") or ""),
                venue=paper.get("venue") or "",
                category=classify_categories(text_for_category),
                discovered_via="Semantic Scholar",
                doi=doi,
                url=paper.get("url") or "",
                pdf_url=pdf_url,
                abstract=abstract,
                keywords=keywords,
                language=infer_language(title, abstract),
                citation_count=str(paper.get("citationCount") or ""),
                access_rights=access,
                license_or_terms=pdf.get("status") or "",
                notes=f"query={query}",
            )
        )
    return candidates


def collect_crossref(query: str, limit: int, mailto: str) -> list[SourceCandidate]:
    params: dict[str, str | int] = {
        "query.bibliographic": query,
        "rows": min(limit, 1000),
        "select": "DOI,title,author,issued,container-title,URL,link,license,abstract",
    }
    if mailto:
        params["mailto"] = mailto
    url = build_query_url("https://api.crossref.org/works", params)
    try:
        data = request_json(url)
    except Exception as exc:
        print(f"crossref failed for {query!r}: {exc}")
        return []

    candidates: list[SourceCandidate] = []
    for item in (data.get("message") or {}).get("items", []):
        title = " ".join(item.get("title") or []).strip()
        if not title:
            continue
        doi = normalize_doi(item.get("DOI") or "")
        issued = item.get("issued") or {}
        year = ""
        if issued.get("date-parts") and issued["date-parts"][0]:
            year = str(issued["date-parts"][0][0])
        authors = compact_authors(format_crossref_author(author) for author in item.get("author", []))
        links = item.get("link") or []
        pdf_url = normalize_pdf_url(first_crossref_pdf(links))
        licenses = item.get("license") or []
        license_text = "; ".join(license_item.get("URL", "") for license_item in licenses if license_item.get("URL"))
        venue = "; ".join(item.get("container-title") or [])
        abstract = strip_markup(item.get("abstract") or "")
        text_for_category = " ".join([title, abstract, query])
        candidates.append(
            SourceCandidate(
                source_id=make_source_id("crossref", title, doi, item.get("URL") or ""),
                title=title,
                authors=authors,
                year=year,
                venue=venue,
                category=classify_categories(text_for_category),
                discovered_via="Crossref",
                doi=doi,
                url=item.get("URL") or "",
                pdf_url=pdf_url,
                abstract=abstract,
                language=item.get("language") or infer_language(title, abstract),
                access_rights="metadata",
                license_or_terms=license_text,
                notes=f"query={query}",
            )
        )
    return candidates


def format_crossref_author(author: dict[str, Any]) -> str:
    given = author.get("given") or ""
    family = author.get("family") or ""
    return " ".join(part for part in [given, family] if part)


def first_crossref_pdf(links: list[dict[str, Any]]) -> str:
    for link in links:
        content_type = (link.get("content-type") or "").casefold()
        if "pdf" in content_type and link.get("URL"):
            return link["URL"]
    return ""


def enrich_with_unpaywall(candidates: list[SourceCandidate], email: str) -> list[SourceCandidate]:
    enriched: list[SourceCandidate] = []
    for candidate in candidates:
        if candidate.pdf_url or not candidate.doi:
            enriched.append(candidate)
            continue
        doi_path = urllib.parse.quote(candidate.doi, safe="")
        url = f"https://api.unpaywall.org/v2/{doi_path}?email={urllib.parse.quote(email)}"
        try:
            data = request_json(url)
        except Exception:
            enriched.append(candidate)
            continue
        best = data.get("best_oa_location") or {}
        pdf_url = normalize_pdf_url(best.get("url_for_pdf") or "")
        if not pdf_url:
            enriched.append(candidate)
            continue
        enriched.append(
            SourceCandidate(
                **{
                    **candidate.to_row(),
                    "pdf_url": pdf_url,
                    "access_rights": data.get("oa_status") or candidate.access_rights,
                    "license_or_terms": best.get("license") or candidate.license_or_terms,
                    "discovered_via": candidate.discovered_via + ";Unpaywall",
                }
            )
        )
        time.sleep(0.2)
    return enriched


def download_candidates(
    candidates: list[SourceCandidate],
    destination_dir: Path,
    max_downloads: int,
) -> list[SourceCandidate]:
    downloaded = 0
    updated: list[SourceCandidate] = []
    for candidate in candidates:
        if candidate.local_path or candidate.status == "downloaded":
            updated.append(candidate)
            continue
        if not candidate.pdf_url or downloaded >= max_downloads:
            updated.append(candidate)
            continue
        ok, result = download_pdf(candidate, destination_dir)
        if ok:
            downloaded += 1
            updated.append(SourceCandidate(**{**candidate.to_row(), "local_path": result, "status": "downloaded"}))
        else:
            updated.append(SourceCandidate(**{**candidate.to_row(), "status": "download_failed", "notes": f"{candidate.notes}; {result}"}))
        time.sleep(1)
    return updated


if __name__ == "__main__":
    main()
