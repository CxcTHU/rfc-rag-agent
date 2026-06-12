import email.message
from io import BytesIO

from scripts.ingest_standards import StandardDocument, download_pdf, read_standards_csv


class FakeResponse:
    def __init__(self, body: bytes, content_length: str | None = None) -> None:
        self._body = BytesIO(body)
        self.headers = email.message.Message()
        if content_length is not None:
            self.headers["Content-Length"] = content_length

    def read(self, size=-1):
        return self._body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_read_standards_csv(tmp_path) -> None:
    path = tmp_path / "standards.csv"
    path.write_text(
        "title,url,category,trust_level,notes\n"
        "Manual,https://example.test/manual.pdf,dam_safety,high,public\n",
        encoding="utf-8",
    )

    standards = read_standards_csv(path)

    assert len(standards) == 1
    assert standards[0].title == "Manual"
    assert standards[0].url.endswith("manual.pdf")


def test_download_pdf_skips_content_length_over_limit(monkeypatch, tmp_path) -> None:
    def fake_urlopen(request, timeout):
        return FakeResponse(b"", content_length="5000")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = download_pdf(
        standard=StandardDocument(title="Large manual", url="https://example.test/large.pdf"),
        output_dir=tmp_path,
        max_bytes=100,
        sleep=lambda _: None,
    )

    assert result.status == "skipped_too_large"
    assert not list(tmp_path.glob("*.pdf"))


def test_download_pdf_writes_file_with_project_user_agent(monkeypatch, tmp_path) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        return FakeResponse(b"%PDF-1.4 public manual", content_length="22")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = download_pdf(
        standard=StandardDocument(title="Small manual", url="https://example.test/small.pdf"),
        output_dir=tmp_path,
        max_bytes=1000,
        sleep=lambda _: None,
    )

    assert result.status == "downloaded"
    assert result.local_path.exists()
    assert result.local_path.read_bytes().startswith(b"%PDF")
    assert captured["headers"]["User-agent"].startswith("RFC-RAG-Agent/")
