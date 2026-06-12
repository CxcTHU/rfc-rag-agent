from __future__ import annotations

import hashlib
import urllib.parse
from html.parser import HTMLParser
from dataclasses import dataclass
from pathlib import Path

from app.db.repositories import SourceRepository
from app.services.crawling.extractor import WebContentExtractor
from app.services.crawling.fetcher import WebFetcher
from app.services.crawling.url_manager import CrawlSeed, CrawlUrlManager
from app.services.ingestion.service import IngestionService
from app.services.source_collection import SourceCandidate, make_source_id, sanitize_filename
from app.services.source_registry import SourceRegistryService


@dataclass(frozen=True)
class CrawlPipelineResult:
    url: str
    status: str
    title: str = ""
    document_id: int | None = None
    source_id: str = ""
    content_hash: str = ""
    error: str = ""
    discovered_urls: tuple[str, ...] = ()


class WebCrawlIngestionPipeline:
    def __init__(
        self,
        url_manager: CrawlUrlManager,
        fetcher: WebFetcher,
        extractor: WebContentExtractor,
        ingestion_service: IngestionService,
        source_registry_service: SourceRegistryService,
        output_dir: str | Path = "data/raw/web_crawl",
    ) -> None:
        self.url_manager = url_manager
        self.fetcher = fetcher
        self.extractor = extractor
        self.ingestion_service = ingestion_service
        self.source_registry_service = source_registry_service
        self.output_dir = Path(output_dir)

    @classmethod
    def from_db(
        cls,
        db,
        seed_csv: str | Path,
        results_csv: str | Path,
        output_dir: str | Path = "data/raw/web_crawl",
        delay_seconds: float = 2.0,
        timeout_seconds: float = 20.0,
    ) -> "WebCrawlIngestionPipeline":
        return cls(
            url_manager=CrawlUrlManager(seed_csv=seed_csv, results_csv=results_csv),
            fetcher=WebFetcher(delay_seconds=delay_seconds, timeout_seconds=timeout_seconds),
            extractor=WebContentExtractor(),
            ingestion_service=IngestionService(db),
            source_registry_service=SourceRegistryService(SourceRepository(db)),
            output_dir=output_dir,
        )

    def run(
        self,
        max_urls: int | None = None,
        dry_run: bool = False,
        discover_links: bool = False,
        max_discovered_per_page: int = 0,
    ) -> list[CrawlPipelineResult]:
        results: list[CrawlPipelineResult] = []
        queue = self.url_manager.pending_seeds(max_urls=max_urls)
        seen_urls = {seed.url for seed in queue} | set(self.url_manager.read_results())
        index = 0
        while index < len(queue):
            seed = queue[index]
            index += 1
            result = self.process_seed(seed, dry_run=dry_run)
            results.append(result)
            if max_urls is not None and len(results) >= max_urls:
                break
            if not discover_links:
                continue
            for discovered_url in result.discovered_urls[:max_discovered_per_page]:
                if discovered_url in seen_urls:
                    continue
                seen_urls.add(discovered_url)
                queue.append(
                    CrawlSeed(
                        url=discovered_url,
                        category=seed.category,
                        trust_level=seed.trust_level,
                        notes=f"discovered from {seed.url}",
                    )
                )
        return results

    def process_seed(self, seed: CrawlSeed, dry_run: bool = False) -> CrawlPipelineResult:
        if dry_run:
            result = CrawlPipelineResult(url=seed.url, status="dry_run")
            self._record(seed, result)
            return result

        fetch_result = self.fetcher.fetch(seed.url)
        if fetch_result.status != "fetched":
            result = CrawlPipelineResult(
                url=seed.url,
                status=fetch_result.status,
                error=fetch_result.error,
            )
            self._record(seed, result, http_status=fetch_result.status_code)
            return result

        extracted = self.extractor.extract(fetch_result.html, url=seed.url)
        discovered_urls = discover_public_links(fetch_result.html, seed.url)
        if extracted.status != "extracted":
            result = CrawlPipelineResult(
                url=seed.url,
                status=extracted.status,
                title=extracted.title,
                error=extracted.error,
                discovered_urls=discovered_urls,
            )
            self._record(seed, result, http_status=fetch_result.status_code)
            return result

        markdown_path = self._write_markdown(seed, extracted.title, extracted.markdown)
        try:
            import_result = self.ingestion_service.import_document(
                markdown_path,
                title=extracted.title,
                source_path=seed.url,
                file_name=markdown_path.name,
                source_type="web_page",
            )
            source_id = make_source_id("crawl", extracted.title, url=seed.url)
            self.source_registry_service.register_candidate(
                SourceCandidate(
                    source_id=source_id,
                    title=extracted.title,
                    authors=extracted.author,
                    year=extracted.date[:4] if extracted.date else "",
                    category=seed.category,
                    discovered_via="stage28_web_crawl",
                    url=seed.url,
                    abstract=extracted.description,
                    source_type="web_page",
                    access_rights="open_access" if seed.trust_level == "high" else "unknown",
                    local_path=str(markdown_path),
                    status="imported",
                    notes=seed.notes,
                ),
                document_id=import_result.document_id,
            )
        except Exception as exc:
            result = CrawlPipelineResult(
                url=seed.url,
                status="ingest_failed",
                title=extracted.title,
                error=str(exc),
                discovered_urls=discovered_urls,
            )
            self._record(seed, result, http_status=fetch_result.status_code)
            return result

        result_status = "duplicate" if import_result.status == "duplicate" else "imported"
        result = CrawlPipelineResult(
            url=seed.url,
            status=result_status,
            title=import_result.title,
            document_id=import_result.document_id,
            source_id=source_id,
            content_hash=import_result.content_hash,
            discovered_urls=discovered_urls,
        )
        self._record(seed, result, http_status=fetch_result.status_code)
        return result

    def _write_markdown(self, seed: CrawlSeed, title: str, markdown: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(seed.url.encode("utf-8")).hexdigest()[:10]
        filename = f"web_{digest}_{sanitize_filename(title or seed.url)[:80]}.md"
        path = self.output_dir / filename
        path.write_text(markdown, encoding="utf-8")
        return path

    def _record(
        self,
        seed: CrawlSeed,
        result: CrawlPipelineResult,
        http_status: int | None = None,
    ) -> None:
        self.url_manager.upsert_result(
            {
                "url": seed.url,
                "category": seed.category,
                "trust_level": seed.trust_level,
                "status": result.status,
                "http_status": http_status,
                "title": result.title,
                "document_id": result.document_id,
                "source_id": result.source_id,
                "content_hash": result.content_hash,
                "error": result.error,
            }
        )


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)


def discover_public_links(html: str, base_url: str) -> tuple[str, ...]:
    collector = LinkCollector()
    collector.feed(html)
    base = urllib.parse.urlparse(base_url)
    discovered: list[str] = []
    seen: set[str] = set()
    for href in collector.links:
        absolute_url = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(absolute_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc != base.netloc:
            continue
        if should_skip_discovered_url(parsed.path):
            continue
        normalized = urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, "")
        )
        if normalized == base_url or normalized in seen:
            continue
        seen.add(normalized)
        discovered.append(normalized)
    return tuple(discovered)


def should_skip_discovered_url(path: str) -> bool:
    lowered = path.casefold()
    blocked_suffixes = (
        ".css",
        ".js",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".ico",
        ".zip",
        ".rar",
        ".7z",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".pdf",
    )
    return lowered.endswith(blocked_suffixes)
