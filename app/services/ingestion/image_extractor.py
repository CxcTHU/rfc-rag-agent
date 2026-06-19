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
