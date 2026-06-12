from dataclasses import dataclass

from app.services.crawling.extractor import ExtractedWebContent
from app.services.crawling.fetcher import FetchResult
from app.services.crawling.pipeline import WebCrawlIngestionPipeline, discover_public_links
from app.services.crawling.url_manager import CrawlSeed, CrawlUrlManager


@dataclass(frozen=True)
class FakeImportResult:
    document_id: int = 7
    title: str = "Rock-Filled Concrete Web Page"
    chunk_count: int = 2
    status: str = "imported"
    content_hash: str = "hash-123"
    raw_path: str = "data/raw/web.md"


class FakeFetcher:
    def fetch(self, url):
        return FetchResult(
            url=url,
            allowed_by_robots=True,
            status="fetched",
            status_code=200,
            html=(
                "<html><body>RFC page"
                "<a href='/next-page'>next</a>"
                "<a href='https://other.example.org/out'>out</a>"
                "<a href='/file.pdf'>pdf</a>"
                "</body></html>"
            ),
        )


class FakeBlockedFetcher:
    def fetch(self, url):
        return FetchResult(
            url=url,
            allowed_by_robots=False,
            status="skipped_robots",
            error="Blocked by robots.txt",
        )


class FakeExtractor:
    def extract(self, html, url=""):
        return ExtractedWebContent(
            url=url,
            title="Rock-Filled Concrete Web Page",
            markdown="# Rock-Filled Concrete Web Page\n\n" + ("content " * 80),
            author="Author",
            date="2024-01-01",
            description="Description",
        )


class FakeIngestionService:
    def __init__(self):
        self.calls = []

    def import_document(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return FakeImportResult()


class FakeSourceRegistryService:
    def __init__(self):
        self.calls = []

    def register_candidate(self, candidate, document_id=None):
        self.calls.append((candidate, document_id))


def make_manager(tmp_path):
    seed_csv = tmp_path / "seed_urls.csv"
    seed_csv.write_text(
        "url,category,trust_level,notes\n"
        "https://example.org/rfc,开放论文,high,public page\n",
        encoding="utf-8",
    )
    return CrawlUrlManager(seed_csv, tmp_path / "crawl_results.csv")


def test_pipeline_writes_markdown_imports_document_and_registers_source(tmp_path) -> None:
    ingestion = FakeIngestionService()
    registry = FakeSourceRegistryService()
    pipeline = WebCrawlIngestionPipeline(
        url_manager=make_manager(tmp_path),
        fetcher=FakeFetcher(),
        extractor=FakeExtractor(),
        ingestion_service=ingestion,
        source_registry_service=registry,
        output_dir=tmp_path / "web_crawl",
    )

    result = pipeline.process_seed(
        CrawlSeed(
            url="https://example.org/rfc",
            category="开放论文",
            trust_level="high",
            notes="public page",
        )
    )

    assert result.status == "imported"
    assert result.document_id == 7
    assert result.discovered_urls == ("https://example.org/next-page",)
    assert ingestion.calls[0][1]["source_path"] == "https://example.org/rfc"
    assert ingestion.calls[0][1]["source_type"] == "web_page"
    imported_path = ingestion.calls[0][0][0]
    assert imported_path.exists()
    assert imported_path.read_text(encoding="utf-8").startswith("# Rock-Filled")
    candidate, document_id = registry.calls[0]
    assert document_id == 7
    assert candidate.url == "https://example.org/rfc"
    assert candidate.source_type == "web_page"


def test_discover_public_links_keeps_same_host_html_links() -> None:
    links = discover_public_links(
        "<a href='/a'>A</a><a href='https://example.org/b#x'>B</a>"
        "<a href='https://other.example.org/c'>C</a><a href='/d.pdf'>PDF</a>",
        "https://example.org/root",
    )

    assert links == ("https://example.org/a", "https://example.org/b")


def test_pipeline_records_robots_skip_without_importing(tmp_path) -> None:
    ingestion = FakeIngestionService()
    registry = FakeSourceRegistryService()
    pipeline = WebCrawlIngestionPipeline(
        url_manager=make_manager(tmp_path),
        fetcher=FakeBlockedFetcher(),
        extractor=FakeExtractor(),
        ingestion_service=ingestion,
        source_registry_service=registry,
        output_dir=tmp_path / "web_crawl",
    )

    result = pipeline.process_seed(
        CrawlSeed(
            url="https://example.org/rfc",
            category="开放论文",
            trust_level="high",
        )
    )

    assert result.status == "skipped_robots"
    assert ingestion.calls == []
    assert registry.calls == []
