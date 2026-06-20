from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass(frozen=True)
class ExtractedPdfImage:
    page_num: int
    image_path: str
    width: int
    height: int


@dataclass(frozen=True)
class PdfImageExtractionConfig:
    output_dir: Path = Path("data/images")
    min_width: int = 100
    min_height: int = 100
    page_render_dpi: int = 150
    merge_gap_points: float = 20.0
    merge_iou_threshold: float = 0.3


class PdfImageExtractor:
    def __init__(self, config: PdfImageExtractionConfig | None = None) -> None:
        self.config = config or PdfImageExtractionConfig()

    def extract_images(self, pdf_path: str | Path, document_id: int) -> list[ExtractedPdfImage]:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(path)
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a PDF file, got: {path.suffix}")

        document_output_dir = self.config.output_dir / str(document_id)
        document_output_dir.mkdir(parents=True, exist_ok=True)

        extracted: list[ExtractedPdfImage] = []
        with fitz.open(path) as pdf:
            for page_index in range(pdf.page_count):
                page = pdf.load_page(page_index)
                for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                    xref = image_info[0]
                    pixmap = None
                    try:
                        pixmap = fitz.Pixmap(pdf, xref)
                        if pixmap.n - pixmap.alpha > 3:
                            pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
                        width = int(pixmap.width)
                        height = int(pixmap.height)
                        if width < self.config.min_width or height < self.config.min_height:
                            continue
                        image_path = document_output_dir / f"page{page_index + 1}_img{image_index}.png"
                        pixmap.save(image_path)
                        extracted.append(
                            ExtractedPdfImage(
                                page_num=page_index + 1,
                                image_path=image_path.as_posix(),
                                width=width,
                                height=height,
                            )
                        )
                    except Exception:
                        continue
                    finally:
                        pixmap = None
        return extracted

    def extract_images_page_render(self, pdf_path: str | Path, document_id: int) -> list[ExtractedPdfImage]:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(path)
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a PDF file, got: {path.suffix}")

        document_output_dir = self.config.output_dir / str(document_id)
        document_output_dir.mkdir(parents=True, exist_ok=True)

        extracted: list[ExtractedPdfImage] = []
        with fitz.open(path) as pdf:
            for page_index in range(pdf.page_count):
                page = pdf.load_page(page_index)
                rects = image_rects_from_page(page)
                merged_rects = merge_image_rects(
                    rects,
                    iou_threshold=self.config.merge_iou_threshold,
                    gap_points=self.config.merge_gap_points,
                )
                for render_index, rect in enumerate(merged_rects, start=1):
                    pixmap = page.get_pixmap(clip=rect, dpi=self.config.page_render_dpi, alpha=False)
                    width = int(pixmap.width)
                    height = int(pixmap.height)
                    if width < self.config.min_width or height < self.config.min_height:
                        continue
                    image_path = document_output_dir / f"page{page_index + 1}_render{render_index}.png"
                    pixmap.save(image_path)
                    extracted.append(
                        ExtractedPdfImage(
                            page_num=page_index + 1,
                            image_path=image_path.as_posix(),
                            width=width,
                            height=height,
                        )
                    )
        return extracted


def image_rects_from_page(page: fitz.Page) -> list[fitz.Rect]:
    rects: list[fitz.Rect] = []
    for info in page.get_image_info(xrefs=True):
        bbox = info.get("bbox")
        if not bbox:
            continue
        rect = fitz.Rect(bbox)
        if rect.is_empty or rect.width <= 0 or rect.height <= 0:
            continue
        rects.append(rect)
    return rects


def merge_image_rects(
    rects: list[fitz.Rect],
    *,
    iou_threshold: float,
    gap_points: float,
) -> list[fitz.Rect]:
    merged: list[fitz.Rect] = []
    for rect in sorted(rects, key=lambda item: (item.y0, item.x0, item.y1, item.x1)):
        current = fitz.Rect(rect)
        did_merge = True
        while did_merge:
            did_merge = False
            next_merged: list[fitz.Rect] = []
            for existing in merged:
                if should_merge_rects(current, existing, iou_threshold=iou_threshold, gap_points=gap_points):
                    current |= existing
                    did_merge = True
                else:
                    next_merged.append(existing)
            merged = next_merged
        merged.append(current)
    return sorted(merged, key=lambda item: (item.y0, item.x0, item.y1, item.x1))


def should_merge_rects(
    left: fitz.Rect,
    right: fitz.Rect,
    *,
    iou_threshold: float,
    gap_points: float,
) -> bool:
    if rect_iou(left, right) >= iou_threshold:
        return True
    expanded = fitz.Rect(left.x0 - gap_points, left.y0 - gap_points, left.x1 + gap_points, left.y1 + gap_points)
    return expanded.intersects(right)


def rect_iou(left: fitz.Rect, right: fitz.Rect) -> float:
    intersection = left & right
    if intersection.is_empty:
        return 0.0
    intersection_area = intersection.width * intersection.height
    union_area = left.width * left.height + right.width * right.height - intersection_area
    if union_area <= 0:
        return 0.0
    return float(intersection_area / union_area)
