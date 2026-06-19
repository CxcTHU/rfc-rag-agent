import struct
import zlib
from pathlib import Path

import fitz

from app.services.ingestion.image_extractor import PdfImageExtractionConfig, PdfImageExtractor


def test_pdf_image_extractor_saves_valid_images_and_skips_small_images(tmp_path) -> None:
    pdf_path = tmp_path / "figures.pdf"
    write_pdf_with_images(pdf_path)
    extractor = PdfImageExtractor(
        PdfImageExtractionConfig(
            output_dir=tmp_path / "images",
            min_width=100,
            min_height=100,
        )
    )

    extracted = extractor.extract_images(pdf_path, document_id=42)

    assert len(extracted) == 1
    assert extracted[0].page_num == 1
    assert extracted[0].width == 120
    assert extracted[0].height == 120
    assert extracted[0].image_path.endswith("images/42/page1_img1.png")
    assert Path(extracted[0].image_path).exists()


def test_pdf_image_extractor_rejects_non_pdf(tmp_path) -> None:
    text_path = tmp_path / "not-pdf.txt"
    text_path.write_text("not a PDF", encoding="utf-8")

    extractor = PdfImageExtractor(PdfImageExtractionConfig(output_dir=tmp_path / "images"))

    try:
        extractor.extract_images(text_path, document_id=1)
    except ValueError as exc:
        assert "Expected a PDF file" in str(exc)
    else:
        raise AssertionError("non-PDF input should fail fast")


def test_pdf_image_extractor_skips_one_bad_pixmap_and_continues(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "figures.pdf"
    write_pdf_with_images(pdf_path)
    original_pixmap = fitz.Pixmap
    call_count = {"value": 0}

    def flaky_pixmap(*args, **kwargs):
        if len(args) >= 2 and isinstance(args[1], int):
            call_count["value"] += 1
            if call_count["value"] == 1:
                raise fitz.FzErrorArgument("bad image")
        return original_pixmap(*args, **kwargs)

    monkeypatch.setattr(fitz, "Pixmap", flaky_pixmap)
    extractor = PdfImageExtractor(
        PdfImageExtractionConfig(
            output_dir=tmp_path / "images",
            min_width=50,
            min_height=100,
        )
    )

    extracted = extractor.extract_images(pdf_path, document_id=42)

    assert len(extracted) == 1
    assert extracted[0].image_path.endswith("images/42/page1_img2.png")


def write_pdf_with_images(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=360, height=240)
    page.insert_image(fitz.Rect(20, 20, 140, 140), stream=make_png_bytes(120, 120, (30, 120, 220)))
    page.insert_image(fitz.Rect(170, 20, 250, 140), stream=make_png_bytes(80, 120, (200, 80, 40)))
    document.save(path)
    document.close()


def make_png_bytes(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw))
        + png_chunk(b"IEND", b"")
    )


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)
