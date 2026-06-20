"""Classify Phase 46 PDF image artifacts without mutating DB or files."""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_IMAGE_DIR = ROOT / "data" / "images"
DEFAULT_OUTPUT_CSV = ROOT / "data" / "evaluation" / "phase46_image_quality_manifest.csv"
IMAGE_NAME_RE = re.compile(r"page(?P<page>\d+)_img(?P<image>\d+)\.png$", re.IGNORECASE)
MANIFEST_FIELDS = [
    "document_id",
    "document_title",
    "chunk_id",
    "chunk_index",
    "embedding_count",
    "source_image_path",
    "exists_on_disk",
    "file_size_bytes",
    "width",
    "height",
    "page_num",
    "image_num",
    "classification",
    "reason",
    "same_dim_page_count",
    "same_page_image_count",
    "page_has_extreme_ratio",
]


@dataclass(frozen=True)
class ImageInventoryRow:
    document_id: int
    document_title: str
    chunk_id: int
    chunk_index: int
    embedding_count: int
    source_image_path: str
    exists_on_disk: bool
    file_size_bytes: int
    width: int
    height: int
    page_num: int
    image_num: int


@dataclass(frozen=True)
class ImageClassificationRow:
    document_id: int
    document_title: str
    chunk_id: int
    chunk_index: int
    embedding_count: int
    source_image_path: str
    exists_on_disk: bool
    file_size_bytes: int
    width: int
    height: int
    page_num: int
    image_num: int
    classification: str
    reason: str
    same_dim_page_count: int
    same_page_image_count: int
    page_has_extreme_ratio: bool


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify Phase 46 image quality issues.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--image-dir", default=str(DEFAULT_IMAGE_DIR))
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--small-file-bytes", type=int, default=5 * 1024)
    parser.add_argument("--small-dimension", type=int, default=100)
    parser.add_argument("--decoration-page-threshold", type=int, default=3)
    parser.add_argument("--decoration-max-file-bytes", type=int, default=20 * 1024)
    parser.add_argument("--decoration-max-dimension", type=int, default=120)
    parser.add_argument("--fragment-page-image-threshold", type=int, default=3)
    parser.add_argument("--fragment-dense-page-threshold", type=int, default=20)
    parser.add_argument("--fragment-aspect-ratio", type=float, default=3.0)
    parser.add_argument("--fragment-candidate-max-file-bytes", type=int, default=20 * 1024)
    args = parser.parse_args()

    with sqlite3.connect(args.db_path) as connection:
        rows = build_inventory(connection, Path(args.image_dir), ROOT)
    classified = classify_rows(
        rows,
        small_file_bytes=args.small_file_bytes,
        small_dimension=args.small_dimension,
        decoration_page_threshold=args.decoration_page_threshold,
        decoration_max_file_bytes=args.decoration_max_file_bytes,
        decoration_max_dimension=args.decoration_max_dimension,
        fragment_page_image_threshold=args.fragment_page_image_threshold,
        fragment_dense_page_threshold=args.fragment_dense_page_threshold,
        fragment_aspect_ratio=args.fragment_aspect_ratio,
        fragment_candidate_max_file_bytes=args.fragment_candidate_max_file_bytes,
    )
    write_manifest(Path(args.output_csv), classified)
    counts = Counter(row.classification for row in classified)
    print(
        "summary:",
        f"total={len(classified)}",
        f"normal={counts['normal']}",
        f"type_a={counts['type_a']}",
        f"type_b={counts['type_b']}",
        f"type_c={counts['type_c']}",
    )
    print(f"wrote {args.output_csv}")


def build_inventory(
    connection: sqlite3.Connection,
    image_dir: Path,
    root: Path = ROOT,
) -> list[ImageInventoryRow]:
    chunk_rows = read_image_chunks(connection)
    disk_paths = read_disk_image_paths(image_dir, root)
    all_paths = sorted(set(chunk_rows) | disk_paths)
    rows: list[ImageInventoryRow] = []
    for source_image_path in all_paths:
        chunk = chunk_rows.get(source_image_path, {})
        document_id = int(chunk.get("document_id") or infer_document_id(source_image_path))
        absolute_path = resolve_image_path(source_image_path, root)
        exists = absolute_path.exists()
        file_size = absolute_path.stat().st_size if exists else 0
        width, height = read_image_size(absolute_path) if exists and file_size > 0 else (0, 0)
        page_num, image_num = parse_page_image(source_image_path)
        rows.append(
            ImageInventoryRow(
                document_id=document_id,
                document_title=str(chunk.get("document_title") or ""),
                chunk_id=int(chunk.get("chunk_id") or 0),
                chunk_index=int(chunk.get("chunk_index") or -1),
                embedding_count=int(chunk.get("embedding_count") or 0),
                source_image_path=source_image_path,
                exists_on_disk=exists,
                file_size_bytes=file_size,
                width=width,
                height=height,
                page_num=page_num,
                image_num=image_num,
            )
        )
    return rows


def read_image_chunks(connection: sqlite3.Connection) -> dict[str, dict[str, object]]:
    rows = connection.execute(
        """
        select
            c.id,
            c.document_id,
            d.title,
            c.chunk_index,
            c.source_image_path,
            count(e.id) as embedding_count
        from chunks c
        left join documents d on d.id = c.document_id
        left join chunk_embeddings e on e.chunk_id = c.id
        where c.chunk_type = 'image_description'
          and c.source_image_path is not null
          and c.source_image_path != ''
        group by c.id, c.document_id, d.title, c.chunk_index, c.source_image_path
        order by c.document_id, c.source_image_path, c.id
        """
    ).fetchall()
    return {
        normalize_image_path(str(row[4])): {
            "chunk_id": int(row[0]),
            "document_id": int(row[1]),
            "document_title": str(row[2] or ""),
            "chunk_index": int(row[3]),
            "embedding_count": int(row[5] or 0),
        }
        for row in rows
    }


def read_disk_image_paths(image_dir: Path, root: Path = ROOT) -> set[str]:
    if not image_dir.exists():
        return set()
    paths: set[str] = set()
    for path in image_dir.rglob("*.png"):
        paths.add(normalize_image_path(path.resolve().relative_to(root.resolve()).as_posix()))
    return paths


def classify_rows(
    rows: list[ImageInventoryRow],
    *,
    small_file_bytes: int,
    small_dimension: int,
    decoration_page_threshold: int,
    decoration_max_file_bytes: int = 20 * 1024,
    decoration_max_dimension: int = 120,
    fragment_page_image_threshold: int = 3,
    fragment_dense_page_threshold: int = 20,
    fragment_aspect_ratio: float = 3.0,
    fragment_candidate_max_file_bytes: int = 20 * 1024,
) -> list[ImageClassificationRow]:
    dim_pages: dict[tuple[int, int, int], set[int]] = defaultdict(set)
    page_rows: dict[tuple[int, int], list[ImageInventoryRow]] = defaultdict(list)
    for row in rows:
        if row.width > 0 and row.height > 0:
            dim_pages[(row.document_id, row.width, row.height)].add(row.page_num)
        page_rows[(row.document_id, row.page_num)].append(row)

    page_stats: dict[tuple[int, int], tuple[int, bool]] = {}
    for key, page_group in page_rows.items():
        usable = [row for row in page_group if row.width > 0 and row.height > 0]
        has_extreme = any(is_extreme_ratio(row, fragment_aspect_ratio) for row in usable)
        page_stats[key] = (len(page_group), has_extreme)

    classified: list[ImageClassificationRow] = []
    for row in rows:
        same_dim_page_count = len(dim_pages.get((row.document_id, row.width, row.height), set()))
        same_page_image_count, page_has_extreme_ratio = page_stats.get((row.document_id, row.page_num), (1, False))
        classification, reason = classify_one(
            row,
            same_dim_page_count=same_dim_page_count,
            same_page_image_count=same_page_image_count,
            page_has_extreme_ratio=page_has_extreme_ratio,
            small_file_bytes=small_file_bytes,
            small_dimension=small_dimension,
            decoration_page_threshold=decoration_page_threshold,
            decoration_max_file_bytes=decoration_max_file_bytes,
            decoration_max_dimension=decoration_max_dimension,
            fragment_page_image_threshold=fragment_page_image_threshold,
            fragment_dense_page_threshold=fragment_dense_page_threshold,
            fragment_aspect_ratio=fragment_aspect_ratio,
            fragment_candidate_max_file_bytes=fragment_candidate_max_file_bytes,
        )
        classified.append(
            ImageClassificationRow(
                **asdict(row),
                classification=classification,
                reason=reason,
                same_dim_page_count=same_dim_page_count,
                same_page_image_count=same_page_image_count,
                page_has_extreme_ratio=page_has_extreme_ratio,
            )
        )
    return classified


def classify_one(
    row: ImageInventoryRow,
    *,
    same_dim_page_count: int,
    same_page_image_count: int,
    page_has_extreme_ratio: bool,
    small_file_bytes: int,
    small_dimension: int,
    decoration_page_threshold: int,
    decoration_max_file_bytes: int,
    decoration_max_dimension: int,
    fragment_page_image_threshold: int,
    fragment_dense_page_threshold: int,
    fragment_aspect_ratio: float,
    fragment_candidate_max_file_bytes: int,
) -> tuple[str, str]:
    if not row.exists_on_disk:
        return "type_c", "missing_file"
    if row.file_size_bytes == 0:
        return "type_c", "zero_byte_file"
    if row.file_size_bytes < small_file_bytes and (row.width < small_dimension or row.height < small_dimension):
        return "type_c", "small_file_and_small_dimension"
    if (
        same_dim_page_count >= decoration_page_threshold
        and (
            row.file_size_bytes <= decoration_max_file_bytes
            or row.width <= decoration_max_dimension
            or row.height <= decoration_max_dimension
        )
    ):
        return "type_a", f"same_dimensions_across_{same_dim_page_count}_pages"
    if (
        same_page_image_count >= fragment_page_image_threshold
        and page_has_extreme_ratio
        and (
            same_page_image_count >= fragment_dense_page_threshold
            or row.file_size_bytes <= fragment_candidate_max_file_bytes
        )
    ):
        return "type_b", "fragment_suspect_page_with_extreme_ratio"
    return "normal", ""


def is_extreme_ratio(row: ImageInventoryRow, threshold: float) -> bool:
    if row.width <= 0 or row.height <= 0:
        return False
    ratio = row.width / row.height
    return ratio > threshold or ratio < 1 / threshold


def read_image_size(path: Path) -> tuple[int, int]:
    try:
        pixmap = fitz.Pixmap(path.as_posix())
        return int(pixmap.width), int(pixmap.height)
    except Exception:
        return 0, 0


def parse_page_image(source_image_path: str) -> tuple[int, int]:
    match = IMAGE_NAME_RE.search(Path(source_image_path).name)
    if not match:
        return 0, 0
    return int(match.group("page")), int(match.group("image"))


def infer_document_id(source_image_path: str) -> int:
    parts = Path(source_image_path.replace("\\", "/")).parts
    try:
        images_index = parts.index("images")
        return int(parts[images_index + 1])
    except (ValueError, IndexError):
        return 0


def resolve_image_path(source_image_path: str, root: Path = ROOT) -> Path:
    path = Path(source_image_path)
    if path.is_absolute():
        return path
    return root / path


def normalize_image_path(source_image_path: str) -> str:
    return source_image_path.replace("\\", "/").lstrip("/")


def write_manifest(path: Path, rows: list[ImageClassificationRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


if __name__ == "__main__":
    main()
