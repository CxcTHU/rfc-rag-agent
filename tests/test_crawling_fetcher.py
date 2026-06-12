import email.message
from io import BytesIO

from app.services.crawling.fetcher import WebFetcher


class DisallowRobots:
    def can_fetch(self, user_agent, url):
        return False


class AllowRobots:
    def can_fetch(self, user_agent, url):
        return True


class FakeResponse:
    status = 200

    def __init__(self, body: str) -> None:
        self._body = BytesIO(body.encode("utf-8"))
        self.headers = email.message.Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"

    def read(self):
        return self._body.read()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_fetcher_rejects_browser_like_user_agent() -> None:
    try:
        WebFetcher(user_agent="Mozilla/5.0 Chrome/120", sleep=lambda _: None)
    except ValueError as exc:
        assert "not a browser" in str(exc)
    else:
        raise AssertionError("Expected browser-like user agent to be rejected")


def test_fetcher_skips_when_robots_disallow(monkeypatch) -> None:
    fetcher = WebFetcher(sleep=lambda _: None)
    monkeypatch.setattr(fetcher, "_robots_parser_for", lambda url: DisallowRobots())

    result = fetcher.fetch("https://example.org/private/page.html")

    assert result.status == "skipped_robots"
    assert result.allowed_by_robots is False
    assert "robots.txt" in result.error


def test_fetcher_fetches_html_with_project_user_agent(monkeypatch) -> None:
    captured_headers = {}

    def fake_urlopen(request, timeout):
        captured_headers.update(dict(request.header_items()))
        return FakeResponse("<html><body>Rock-filled concrete page</body></html>")

    fetcher = WebFetcher(sleep=lambda _: None)
    monkeypatch.setattr(fetcher, "_robots_parser_for", lambda url: AllowRobots())
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = fetcher.fetch("https://example.org/page.html")

    assert result.status == "fetched"
    assert result.status_code == 200
    assert "Rock-filled concrete" in result.html
    assert captured_headers["User-agent"].startswith("RFC-RAG-Agent/")
    assert "Mozilla/" not in captured_headers["User-agent"]


def test_fetcher_records_timeout_as_fetch_failed(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise TimeoutError("read timed out")

    fetcher = WebFetcher(sleep=lambda _: None)
    monkeypatch.setattr(fetcher, "_robots_parser_for", lambda url: AllowRobots())
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = fetcher.fetch("https://example.org/slow")

    assert result.status == "fetch_failed"
    assert "Timeout" in result.error
