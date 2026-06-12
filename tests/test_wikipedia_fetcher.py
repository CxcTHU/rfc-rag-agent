import email.message
from io import BytesIO
from types import SimpleNamespace
import urllib.error

from app.services.crawling.wikipedia_fetcher import (
    WikipediaArticle,
    WikipediaFetcher,
    wikipedia_rest_html_url,
)


class FakeResponse:
    status = 200

    def __init__(self, body: str) -> None:
        self._body = BytesIO(body.encode("utf-8"))
        self.headers = email.message.Message()

    def read(self):
        return self._body.read()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeExtractor:
    def extract(self, html: str, url: str = ""):
        return SimpleNamespace(
            url=url,
            title="Concrete dam",
            markdown="# Concrete dam\n\n" + ("Dam concrete " * 40),
            author="",
            date="2024-01-01",
            description="Wikipedia article",
            status="extracted",
            error="",
        )


def test_wikipedia_rest_html_url_encodes_titles() -> None:
    assert wikipedia_rest_html_url("en", "Concrete dam").endswith("/Concrete_dam")
    assert "%E6%B7%B7%E5%87%9D%E5%9C%9F" in wikipedia_rest_html_url("zh", "混凝土")


def test_fetcher_rejects_browser_like_user_agent() -> None:
    try:
        WikipediaFetcher(user_agent="Mozilla/5.0 Chrome/120", sleep=lambda _: None)
    except ValueError as exc:
        assert "not a browser" in str(exc)
    else:
        raise AssertionError("Expected browser-like user agent to be rejected")


def test_fetcher_uses_wikipedia_api_and_project_user_agent(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return FakeResponse("<html><body>Concrete dam page</body></html>")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    fetcher = WikipediaFetcher(sleep=lambda _: None, timeout_seconds=12)
    result = fetcher.fetch_html(WikipediaArticle(language="en", title="Concrete dam"))

    assert result.status == "fetched"
    assert captured["url"] == "https://en.wikipedia.org/api/rest_v1/page/html/Concrete_dam"
    assert captured["headers"]["User-agent"].startswith("RFC-RAG-Agent/")
    assert "Mozilla/" not in captured["headers"]["User-agent"]
    assert captured["timeout"] == 12


def test_fetcher_extracts_wikipedia_html(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeResponse("<html><body>Concrete dam page</body></html>")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    fetcher = WikipediaFetcher(sleep=lambda _: None)
    result = fetcher.fetch_and_extract(
        WikipediaArticle(language="en", title="Concrete dam"),
        FakeExtractor(),
    )

    assert result.status == "extracted"
    assert result.extracted.title == "Concrete dam"
    assert result.extracted.markdown.startswith("# Concrete dam")


def test_fetcher_retries_network_errors(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.URLError("connection reset")
        return FakeResponse("<html><body>Concrete dam page</body></html>")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    fetcher = WikipediaFetcher(sleep=lambda _: None, max_retries=1)
    result = fetcher.fetch_html(WikipediaArticle(language="en", title="Concrete dam"))

    assert result.status == "fetched"
    assert calls["count"] == 2
