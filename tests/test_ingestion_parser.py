import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.services.ingestion.parser import (
    UnsupportedDocumentTypeError,
    parse_text_file,
)


def test_parse_markdown_file_extracts_heading_title(tmp_path) -> None:
    file_path = tmp_path / "rfc.md"
    file_path.write_text("# 堆石混凝土概念\n\n正文内容", encoding="utf-8")

    parsed = parse_text_file(file_path)

    assert parsed.title == "堆石混凝土概念"
    assert parsed.content == "# 堆石混凝土概念\n\n正文内容"
    assert parsed.file_name == "rfc.md"
    assert parsed.file_extension == ".md"
    assert parsed.source_path == str(file_path)


def test_parse_txt_file_uses_file_stem_as_default_title(tmp_path) -> None:
    file_path = tmp_path / "construction.txt"
    file_path.write_text("施工质量控制", encoding="utf-8")

    parsed = parse_text_file(file_path)

    assert parsed.title == "construction"
    assert parsed.content == "施工质量控制"
    assert parsed.file_extension == ".txt"


def test_parse_text_file_rejects_unsupported_extension(tmp_path) -> None:
    file_path = tmp_path / "sample.docx"
    file_path.write_text("DOCX is not supported in phase 1", encoding="utf-8")

    with pytest.raises(UnsupportedDocumentTypeError):
        parse_text_file(file_path)


def test_parse_text_file_extracts_pdf_text(tmp_path) -> None:
    file_path = tmp_path / "rfc.pdf"
    write_pdf_with_text(file_path, "Rock-filled concrete uses self-compacting concrete.")

    parsed = parse_text_file(file_path)

    assert parsed.title == "rfc"
    assert parsed.file_extension == ".pdf"
    assert "## Page 1" in parsed.content
    assert "Rock-filled concrete uses self-compacting concrete." in parsed.content


def write_pdf_with_text(path, text: str) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)

    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    resources = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        }
    )
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 40 250 Td ({escaped_text}) Tj ET".encode("latin-1"))

    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = stream

    with path.open("wb") as output:
        writer.write(output)
