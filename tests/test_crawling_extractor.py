from types import SimpleNamespace

from app.services.crawling.extractor import WebContentExtractor


class FakeTrafilatura:
    @staticmethod
    def extract_metadata(html):
        return SimpleNamespace(
            title="  Rock-Filled Concrete Overview ",
            author="Feng Jin",
            date="2023-01-02",
            description="Public overview.",
        )

    @staticmethod
    def extract(html, **kwargs):
        return "# Rock-Filled Concrete Overview\n\n" + ("Rock-filled concrete " * 30)


class ShortTrafilatura(FakeTrafilatura):
    @staticmethod
    def extract(html, **kwargs):
        return "Too short"


def test_extractor_returns_markdown_and_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.crawling.extractor.importlib.import_module",
        lambda name: FakeTrafilatura,
    )

    result = WebContentExtractor(min_text_chars=80).extract(
        "<html><body>content</body></html>",
        url="https://example.org/rfc",
    )

    assert result.status == "extracted"
    assert result.title == "Rock-Filled Concrete Overview"
    assert result.author == "Feng Jin"
    assert result.date == "2023-01-02"
    assert result.markdown.startswith("# Rock-Filled Concrete Overview")


def test_extractor_rejects_short_text(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.crawling.extractor.importlib.import_module",
        lambda name: ShortTrafilatura,
    )

    result = WebContentExtractor(min_text_chars=80).extract(
        "<html><body>content</body></html>",
        url="https://example.org/rfc",
    )

    assert result.status == "extract_failed"
    assert "too short" in result.error
