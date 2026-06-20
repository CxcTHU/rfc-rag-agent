from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.services.ingestion.image_extractor import image_rects_from_page, merge_image_rects


IMAGE_NAME_RE = re.compile(r"page(?P<page>\d+)_(?P<kind>img|render)(?P<index>\d+)\.png$", re.IGNORECASE)
CAPTION_RE = re.compile(
    r"^\s*(?:图|圖|表)\s*[\d一二三四五六七八九十]+(?:[.\-]\d+)*|"
    r"^\s*(?:Fig\.?|Figure|Table)\s*[\dIVXivx]+(?:[.\-]\d+)*",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CaptionCandidate:
    text: str
    bbox: tuple[float, float, float, float]
    distance_points: float


@dataclass(frozen=True)
class ImageCaptionMatch:
    page_num: int
    source_image_path: str
    image_bbox: tuple[float, float, float, float]
    caption: str | None
    caption_page_num: int | None = None
    caption_bbox: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class CaptionExtractionConfig:
    search_below_points: float = 50.0
    horizontal_overlap_ratio: float = 0.25
    merge_gap_points: float = 20.0
    merge_iou_threshold: float = 0.3


class PdfCaptionExtractor:
    def __init__(self, config: CaptionExtractionConfig | None = None) -> None:
        self.config = config or CaptionExtractionConfig()

    def extract_caption_for_image(self, pdf_path: str | Path, source_image_path: str) -> ImageCaptionMatch:
        image_ref = parse_image_reference(source_image_path)
        with fitz.open(pdf_path) as pdf:
            page = pdf.load_page(image_ref.page_num - 1)
            image_bbox = locate_image_bbox(page, image_ref, self.config)
            candidates = find_caption_candidates(page, image_bbox, self.config)
            caption_page_num = image_ref.page_num
            if not candidates and image_bbox.y1 >= page.rect.y1 - self.config.search_below_points:
                next_page_index = image_ref.page_num
                if next_page_index < pdf.page_count:
                    next_page = pdf.load_page(next_page_index)
                    candidates = find_top_of_page_caption_candidates(next_page, image_bbox, self.config)
                    caption_page_num = next_page_index + 1
        best = candidates[0] if candidates else None
        return ImageCaptionMatch(
            page_num=image_ref.page_num,
            source_image_path=source_image_path,
            image_bbox=rect_tuple(image_bbox),
            caption=best.text if best else None,
            caption_page_num=caption_page_num if best else None,
            caption_bbox=best.bbox if best else None,
        )


@dataclass(frozen=True)
class ImageReference:
    page_num: int
    kind: str
    index: int


def parse_image_reference(source_image_path: str) -> ImageReference:
    match = IMAGE_NAME_RE.search(Path(source_image_path).name)
    if not match:
        raise ValueError(f"cannot parse page/image reference from {source_image_path}")
    return ImageReference(
        page_num=int(match.group("page")),
        kind=match.group("kind").lower(),
        index=int(match.group("index")),
    )


def locate_image_bbox(
    page: fitz.Page,
    image_ref: ImageReference,
    config: CaptionExtractionConfig,
) -> fitz.Rect:
    if image_ref.kind == "render":
        rects = merge_image_rects(
            image_rects_from_page(page),
            iou_threshold=config.merge_iou_threshold,
            gap_points=config.merge_gap_points,
        )
    else:
        rects = original_image_rects_from_page(page)
    if image_ref.index < 1 or image_ref.index > len(rects):
        raise ValueError(f"image index {image_ref.index} out of range on page {image_ref.page_num}")
    return rects[image_ref.index - 1]


def original_image_rects_from_page(page: fitz.Page) -> list[fitz.Rect]:
    rects: list[fitz.Rect] = []
    for image in page.get_images(full=True):
        xref = image[0]
        image_rects = page.get_image_rects(xref)
        if not image_rects:
            continue
        rects.append(max(image_rects, key=lambda rect: rect.width * rect.height))
    return rects


def find_caption_candidates(
    page: fitz.Page,
    image_bbox: fitz.Rect,
    config: CaptionExtractionConfig,
) -> list[CaptionCandidate]:
    search_area = fitz.Rect(
        image_bbox.x0,
        image_bbox.y1,
        image_bbox.x1,
        min(page.rect.y1, image_bbox.y1 + config.search_below_points),
    )
    candidates: list[CaptionCandidate] = []
    for text, rect in text_blocks(page):
        if not CAPTION_RE.search(text):
            continue
        if rect.y0 < image_bbox.y1 or rect.y0 > search_area.y1:
            continue
        if horizontal_overlap_ratio(image_bbox, rect) < config.horizontal_overlap_ratio:
            continue
        candidates.append(
            CaptionCandidate(
                text=normalize_caption_text(text),
                bbox=rect_tuple(rect),
                distance_points=max(0.0, rect.y0 - image_bbox.y1),
            )
        )
    return sorted(candidates, key=lambda item: item.distance_points)


def find_top_of_page_caption_candidates(
    page: fitz.Page,
    previous_page_image_bbox: fitz.Rect,
    config: CaptionExtractionConfig,
) -> list[CaptionCandidate]:
    candidates: list[CaptionCandidate] = []
    for text, rect in text_blocks(page):
        if not CAPTION_RE.search(text):
            continue
        if rect.y0 > config.search_below_points:
            continue
        if horizontal_overlap_ratio(previous_page_image_bbox, rect) < config.horizontal_overlap_ratio:
            continue
        candidates.append(
            CaptionCandidate(
                text=normalize_caption_text(text),
                bbox=rect_tuple(rect),
                distance_points=rect.y0,
            )
        )
    return sorted(candidates, key=lambda item: item.distance_points)


def text_blocks(page: fitz.Page) -> list[tuple[str, fitz.Rect]]:
    text_dict = page.get_text("dict")
    blocks: list[tuple[str, fitz.Rect]] = []
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines = block.get("lines") or []
        line_texts: list[str] = []
        for line in lines:
            spans = line.get("spans") or []
            line_text = "".join(str(span.get("text") or "") for span in spans).strip()
            if line_text:
                line_texts.append(line_text)
        text = " ".join(line_texts).strip()
        if text:
            blocks.append((text, fitz.Rect(block.get("bbox"))))
    return blocks


def horizontal_overlap_ratio(left: fitz.Rect, right: fitz.Rect) -> float:
    overlap = max(0.0, min(left.x1, right.x1) - max(left.x0, right.x0))
    width = max(1.0, min(left.width, right.width))
    return overlap / width


def normalize_caption_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def rect_tuple(rect: fitz.Rect) -> tuple[float, float, float, float]:
    return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
