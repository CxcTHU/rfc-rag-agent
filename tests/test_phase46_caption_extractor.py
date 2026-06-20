import struct
import zlib
from pathlib import Path

import fitz

from app.services.ingestion.caption_extractor import (
    CAPTION_RE,
    CaptionExtractionConfig,
    PdfCaptionExtractor,
    find_caption_candidates,
    parse_image_reference,
)


def test_parse_image_reference_accepts_original_and_render_names() -> None:
    original = parse_image_reference("data/images/1/page12_img3.png")
    rendered = parse_image_reference("data/images/1/page7_render2.png")

    assert original.page_num == 12
    assert original.kind == "img"
    assert original.index == 3
    assert rendered.page_num == 7
    assert rendered.kind == "render"
    assert rendered.index == 2


def test_extract_caption_for_original_image_finds_chinese_caption(tmp_path: Path) -> None:
    pdf_path = tmp_path / "caption.pdf"
    document = fitz.open()
    page = document.new_page(width=360, height=240)
    page.insert_image(fitz.Rect(40, 40, 180, 120), stream=make_png_bytes(120, 80, (30, 120, 220)))
    page.insert_text((45, 138), "Fig. 1.2 Compressive strength curve", fontsize=11)
    document.save(pdf_path)
    document.close()

    match = PdfCaptionExtractor().extract_caption_for_image(pdf_path, "data/images/42/page1_img1.png")

    assert match.caption == "Fig. 1.2 Compressive strength curve"
    assert match.caption_bbox is not None


def test_caption_pattern_matches_chinese_caption_prefixes() -> None:
    assert CAPTION_RE.search("图 1.2 试件抗压强度变化曲线")
    assert CAPTION_RE.search("表 3 参数对比")


def test_caption_search_ignores_caption_too_far_below(tmp_path: Path) -> None:
    pdf_path = tmp_path / "caption.pdf"
    document = fitz.open()
    page = document.new_page(width=360, height=300)
    image_bbox = fitz.Rect(40, 40, 180, 120)
    page.insert_image(image_bbox, stream=make_png_bytes(120, 80, (30, 120, 220)))
    page.insert_text((45, 210), "Fig. 2 Distant caption", fontsize=11)
    document.save(pdf_path)
    document.close()

    with fitz.open(pdf_path) as pdf:
        candidates = find_caption_candidates(pdf[0], image_bbox, CaptionExtractionConfig(search_below_points=50))

    assert candidates == []


def test_extract_caption_for_rendered_image_uses_merged_bbox(tmp_path: Path) -> None:
    pdf_path = tmp_path / "render_caption.pdf"
    document = fitz.open()
    page = document.new_page(width=420, height=260)
    page.insert_image(fitz.Rect(40, 40, 130, 120), stream=make_png_bytes(90, 80, (30, 120, 220)))
    page.insert_image(fitz.Rect(138, 40, 228, 120), stream=make_png_bytes(90, 80, (200, 80, 40)))
    page.insert_text((45, 140), "Fig. 2 Merged display figure", fontsize=11)
    document.save(pdf_path)
    document.close()

    match = PdfCaptionExtractor(
        CaptionExtractionConfig(merge_gap_points=12)
    ).extract_caption_for_image(pdf_path, "data/images/42/page1_render1.png")

    assert match.caption == "Fig. 2 Merged display figure"
    assert match.image_bbox[0] <= 40
    assert match.image_bbox[2] >= 228


def test_extract_caption_can_match_top_of_next_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "cross_page_caption.pdf"
    document = fitz.open()
    page1 = document.new_page(width=360, height=240)
    page1.insert_image(fitz.Rect(40, 170, 180, 230), stream=make_png_bytes(120, 60, (30, 120, 220)))
    page2 = document.new_page(width=360, height=240)
    page2.insert_text((45, 24), "Table 3 Cross-page caption", fontsize=11)
    document.save(pdf_path)
    document.close()

    match = PdfCaptionExtractor().extract_caption_for_image(pdf_path, "data/images/42/page1_img1.png")

    assert match.caption == "Table 3 Cross-page caption"
    assert match.caption_page_num == 2


def test_extract_caption_returns_none_when_no_caption_matches(tmp_path: Path) -> None:
    pdf_path = tmp_path / "no_caption.pdf"
    document = fitz.open()
    page = document.new_page(width=360, height=240)
    page.insert_image(fitz.Rect(40, 40, 180, 120), stream=make_png_bytes(120, 80, (30, 120, 220)))
    page.insert_text((45, 138), "ordinary paragraph below image", fontsize=11)
    document.save(pdf_path)
    document.close()

    match = PdfCaptionExtractor().extract_caption_for_image(pdf_path, "data/images/42/page1_img1.png")

    assert match.caption is None
    assert match.caption_page_num is None


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
    return struct.pack(">I", len(data)) + data[:0] + chunk_type + data + struct.pack(">I", checksum)
