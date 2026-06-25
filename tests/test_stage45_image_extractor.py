import struct
import zlib
from pathlib import Path

import fitz

from app.services.ingestion.image_extractor import (
    PdfImageExtractionConfig,
    PdfImageExtractor,
    merge_image_rects,
)


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


def test_pdf_image_extractor_skips_full_page_scan_images(tmp_path) -> None:
    pdf_path = tmp_path / "scan.pdf"
    document = fitz.open()
    page = document.new_page(width=360, height=240)
    page.insert_image(fitz.Rect(5, 5, 355, 235), stream=make_png_bytes(350, 230, (30, 120, 220)))
    document.save(pdf_path)
    document.close()
    extractor = PdfImageExtractor(
        PdfImageExtractionConfig(
            output_dir=tmp_path / "images",
            min_width=50,
            min_height=50,
            max_page_area_ratio=0.70,
        )
    )

    assert extractor.extract_images(pdf_path, document_id=42) == []


def test_pdf_image_extractor_can_render_displayed_image_orientation(tmp_path) -> None:
    pdf_path = tmp_path / "displayed.pdf"
    write_pdf_with_images(pdf_path)
    extractor = PdfImageExtractor(
        PdfImageExtractionConfig(
            output_dir=tmp_path / "images",
            min_width=50,
            min_height=50,
            render_displayed_images=True,
            page_render_dpi=72,
        )
    )

    extracted = extractor.extract_images(pdf_path, document_id=42)

    assert len(extracted) == 2
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


def test_merge_image_rects_combines_nearby_regions() -> None:
    rects = [
        fitz.Rect(10, 10, 60, 60),
        fitz.Rect(65, 10, 120, 60),
        fitz.Rect(250, 250, 300, 300),
    ]

    merged = merge_image_rects(rects, iou_threshold=0.3, gap_points=10)

    assert len(merged) == 2
    assert merged[0] == fitz.Rect(10, 10, 120, 60)
    assert merged[1] == fitz.Rect(250, 250, 300, 300)


def test_pdf_image_extractor_page_render_merges_display_regions(tmp_path) -> None:
    pdf_path = tmp_path / "figures.pdf"
    document = fitz.open()
    page = document.new_page(width=360, height=240)
    page.insert_image(fitz.Rect(20, 20, 100, 100), stream=make_png_bytes(80, 80, (30, 120, 220)))
    page.insert_image(fitz.Rect(108, 20, 188, 100), stream=make_png_bytes(80, 80, (200, 80, 40)))
    page.insert_image(fitz.Rect(260, 20, 330, 90), stream=make_png_bytes(70, 70, (80, 160, 90)))
    document.save(pdf_path)
    document.close()
    extractor = PdfImageExtractor(
        PdfImageExtractionConfig(
            output_dir=tmp_path / "images",
            min_width=50,
            min_height=50,
            page_render_dpi=72,
            merge_gap_points=10,
        )
    )

    extracted = extractor.extract_images_page_render(pdf_path, document_id=42)

    assert len(extracted) == 2
    assert extracted[0].image_path.endswith("images/42/page1_render1.png")
    assert extracted[0].width >= 160
    assert Path(extracted[0].image_path).exists()


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
