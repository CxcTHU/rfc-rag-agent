from __future__ import annotations

import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from app.services.crawling.extractor import ExtractedWebContent, WebContentExtractor


DEFAULT_WIKIPEDIA_USER_AGENT = "RFC-RAG-Agent/0.1 (+https://github.com/local/rfc-rag-agent; research corpus ingestion)"
SUPPORTED_LANGUAGES = {"en", "zh"}


@dataclass(frozen=True)
class WikipediaArticle:
    language: str
    title: str
    category: str = ""
    trust_level: str = "high"
    notes: str = ""


@dataclass(frozen=True)
class WikipediaFetchResult:
    article: WikipediaArticle
    url: str
    status: str
    html: str = ""
    extracted: ExtractedWebContent | None = None
    error: str = ""
    status_code: int | None = None


class WikipediaFetcher:
    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_WIKIPEDIA_USER_AGENT,
        delay_seconds: float = 2.0,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if delay_seconds < 2.0:
            raise ValueError("delay_seconds must be at least 2 seconds")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")
        if "Mozilla/" in user_agent or "Chrome/" in user_agent:
            raise ValueError("User-Agent must identify this project, not a browser")
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.sleep = sleep

    def fetch_html(self, article: WikipediaArticle) -> WikipediaFetchResult:
        url = wikipedia_rest_html_url(article.language, article.title)
        last_error = ""
        for attempt in range(self.max_retries + 1):
            self.sleep(self.delay_seconds)
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html; charset=utf-8",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    status_code = getattr(response, "status", None)
                    html = response.read().decode("utf-8", errors="replace")
                return WikipediaFetchResult(
                    article=article,
                    url=url,
                    status="fetched",
                    html=html,
                    status_code=status_code,
                )
            except urllib.error.HTTPError as exc:
                return WikipediaFetchResult(
                    article=article,
                    url=url,
                    status="fetch_failed",
                    error=f"HTTP {exc.code}: {exc.reason}",
                    status_code=exc.code,
                )
            except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
                last_error = f"{exc.__class__.__name__}: {exc}"
                if attempt >= self.max_retries:
                    break

        return WikipediaFetchResult(
            article=article,
            url=url,
            status="fetch_failed",
            error=last_error,
        )

    def fetch_and_extract(
        self,
        article: WikipediaArticle,
        extractor: WebContentExtractor,
    ) -> WikipediaFetchResult:
        fetched = self.fetch_html(article)
        if fetched.status != "fetched":
            return fetched

        extracted = extractor.extract(fetched.html, url=fetched.url)
        if extracted.status != "extracted":
            return WikipediaFetchResult(
                article=article,
                url=fetched.url,
                status=extracted.status,
                html=fetched.html,
                extracted=extracted,
                error=extracted.error,
                status_code=fetched.status_code,
            )
        return WikipediaFetchResult(
            article=article,
            url=fetched.url,
            status="extracted",
            html=fetched.html,
            extracted=extracted,
            status_code=fetched.status_code,
        )


def wikipedia_rest_html_url(language: str, title: str) -> str:
    normalized_language = language.strip().casefold()
    if normalized_language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported Wikipedia language: {language}")
    normalized_title = title.strip().replace(" ", "_")
    if not normalized_title:
        raise ValueError("Wikipedia title is required")
    encoded_title = urllib.parse.quote(normalized_title, safe="")
    return f"https://{normalized_language}.wikipedia.org/api/rest_v1/page/html/{encoded_title}"
