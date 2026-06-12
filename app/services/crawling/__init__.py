"""Web crawling helpers for the stage 28 auto-ingest pipeline."""

from app.services.crawling.extractor import ExtractedWebContent, WebContentExtractor
from app.services.crawling.fetcher import FetchResult, WebFetcher
from app.services.crawling.pipeline import CrawlPipelineResult, WebCrawlIngestionPipeline
from app.services.crawling.url_manager import CrawlSeed, CrawlUrlManager

__all__ = [
    "CrawlPipelineResult",
    "CrawlSeed",
    "CrawlUrlManager",
    "ExtractedWebContent",
    "FetchResult",
    "WebContentExtractor",
    "WebCrawlIngestionPipeline",
    "WebFetcher",
]
