import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from app.services.ingestion.pdf_text import structure_pdf_pages


SUPPORTED_TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = SUPPORTED_TEXT_EXTENSIONS | SUPPORTED_PDF_EXTENSIONS
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


class UnsupportedDocumentTypeError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    content: str
    file_name: str
    file_extension: str
    source_path: str


def parse_text_file(path: str | Path, title: str | None = None) -> ParsedDocument:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    if not file_path.is_file():
        raise IsADirectoryError(file_path)

    file_extension = file_path.suffix.lower()
    if file_extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentTypeError(
            f"Unsupported file type: {file_extension}. "
            f"Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if file_extension in SUPPORTED_PDF_EXTENSIONS:
        content = read_pdf_text(file_path)
    else:
        content = read_text_with_fallback(file_path)
    inferred_title = title or infer_title(file_path, content)
    return ParsedDocument(
        title=inferred_title,
        content=content,
        file_name=file_path.name,
        file_extension=file_extension,
        source_path=str(file_path),
    )


def read_text_with_fallback(path: Path) -> str:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc

    raise ValueError(f"Cannot decode text file: {path}") from last_error


def read_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    raw_pages: list[str] = [(page.extract_text() or "") for page in reader.pages]
    # 阶段 18：对原始 PDF 文本做结构化加固（标题层级、表格、断词、去噪），
    # 让后续 cleaner/splitter 能拿到带 Markdown 标题的文本。
    return structure_pdf_pages(raw_pages)


def infer_title(path: Path, content: str) -> str:
    if path.suffix.lower() in {".md", ".markdown"}:
        for line in content.splitlines():
            match = MARKDOWN_HEADING_RE.match(line)
            if match:
                return match.group(1).strip()
    return path.stem
