from __future__ import annotations

import time
import socket
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


DEFAULT_USER_AGENT = "RFC-RAG-Agent/0.1 (+https://github.com/local/rfc-rag-agent; research crawler)"


class SleepFunction(Protocol):
    def __call__(self, seconds: float) -> None:
        """Sleep for the requested number of seconds."""


@dataclass(frozen=True)
class FetchResult:
    url: str
    allowed_by_robots: bool
    status: str
    status_code: int | None = None
    content_type: str = ""
    html: str = ""
    fetched_at: str = ""
    error: str = ""


class WebFetcher:
    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        delay_seconds: float = 2.0,
        timeout_seconds: float = 20.0,
        max_retries: int = 1,
        sleep: SleepFunction = time.sleep,
    ) -> None:
        if delay_seconds < 2.0:
            raise ValueError("delay_seconds must be at least 2.0")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        normalized_user_agent = user_agent.strip()
        if not normalized_user_agent:
            raise ValueError("user_agent must not be empty")
        if "Mozilla/" in normalized_user_agent or "Chrome/" in normalized_user_agent:
            raise ValueError("user_agent must identify this crawler, not a browser")

        self.user_agent = normalized_user_agent
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.sleep = sleep
        self._last_request_at: float | None = None
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def fetch(self, url: str) -> FetchResult:
        normalized_url = normalize_url(url)
        if not self.can_fetch(normalized_url):
            return FetchResult(
                url=normalized_url,
                allowed_by_robots=False,
                status="skipped_robots",
                fetched_at=utc_now(),
                error="Blocked by robots.txt",
            )

        self._respect_delay()
        request = urllib.request.Request(
            normalized_url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "User-Agent": self.user_agent,
            },
            method="GET",
        )

        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    body = response.read().decode(charset, errors="replace")
                    self._last_request_at = time.monotonic()
                    return FetchResult(
                        url=normalized_url,
                        allowed_by_robots=True,
                        status="fetched",
                        status_code=response.status,
                        content_type=response.headers.get("Content-Type", ""),
                        html=body,
                        fetched_at=utc_now(),
                    )
            except urllib.error.HTTPError as exc:
                self._last_request_at = time.monotonic()
                error_body = exc.read().decode("utf-8", errors="replace")[:300]
                last_error = f"HTTP {exc.code}: {error_body}"
                if 400 <= exc.code < 500:
                    break
            except urllib.error.URLError as exc:
                self._last_request_at = time.monotonic()
                last_error = f"URL error: {exc.reason}"
            except (TimeoutError, socket.timeout) as exc:
                self._last_request_at = time.monotonic()
                last_error = f"Timeout: {exc}"
            except OSError as exc:
                self._last_request_at = time.monotonic()
                last_error = f"Network error: {exc}"
            if attempt < self.max_retries:
                self.sleep(self.delay_seconds)

        return FetchResult(
            url=normalized_url,
            allowed_by_robots=True,
            status="fetch_failed",
            fetched_at=utc_now(),
            error=last_error or "Unknown fetch error",
        )

    def can_fetch(self, url: str) -> bool:
        parser = self._robots_parser_for(url)
        return parser.can_fetch(self.user_agent, url)

    def _robots_parser_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parsed = urllib.parse.urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        cached = self._robots_cache.get(origin)
        if cached is not None:
            return cached

        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(urllib.parse.urljoin(origin, "/robots.txt"))
        try:
            parser.read()
        except Exception:
            parser.parse([])
        self._robots_cache[origin] = parser
        return parser

    def _respect_delay(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.delay_seconds - elapsed
        if remaining > 0:
            self.sleep(remaining)


def normalize_url(url: str) -> str:
    normalized = url.strip()
    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Unsupported or invalid URL: {url}")
    return normalized


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
