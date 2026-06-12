from __future__ import annotations

import importlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedWebContent:
    url: str
    title: str
    markdown: str
    author: str = ""
    date: str = ""
    description: str = ""
    status: str = "extracted"
    error: str = ""


class WebContentExtractor:
    def __init__(self, min_text_chars: int = 300) -> None:
        if min_text_chars <= 0:
            raise ValueError("min_text_chars must be greater than 0")
        self.min_text_chars = min_text_chars

    def extract(self, html: str, url: str = "") -> ExtractedWebContent:
        if not html.strip():
            return self._failed(url, "Empty HTML")

        trafilatura = importlib.import_module("trafilatura")
        metadata = trafilatura.extract_metadata(html)
        markdown = trafilatura.extract(
            html,
            url=url or None,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
        )
        if not markdown or len(normalize_text(markdown)) < self.min_text_chars:
            return self._failed(url, "Extracted text is too short")

        title = clean_metadata_value(getattr(metadata, "title", "") if metadata else "")
        return ExtractedWebContent(
            url=url,
            title=title or title_from_markdown(markdown) or url,
            markdown=markdown.strip() + "\n",
            author=clean_metadata_value(getattr(metadata, "author", "") if metadata else ""),
            date=clean_metadata_value(getattr(metadata, "date", "") if metadata else ""),
            description=clean_metadata_value(
                getattr(metadata, "description", "") if metadata else ""
            ),
        )

    def _failed(self, url: str, error: str) -> ExtractedWebContent:
        return ExtractedWebContent(
            url=url,
            title=url,
            markdown="",
            status="extract_failed",
            error=error,
        )


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_metadata_value(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def title_from_markdown(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""
