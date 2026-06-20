"""Build an image manifest for Phase 46 page-rendered repair images."""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_IMAGE_DIR = ROOT / "data" / "images"
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "phase46_rendered_image_manifest.csv"
RENDER_NAME_RE = re.compile(r"page(?P<page>\d+)_render(?P<render>\d+)\.png$", re.IGNORECASE)
FIELDS = [
    "document_id",
    "document_title",
    "page_num",
    "source_image_path",
    "width",
    "height",
    "status",
    "error",
]


@dataclass(frozen=True)
class RenderManifestRow:
    document_id: int
    document_title: str
    page_num: int
    source_image_path: str
    width: int
    height: int
    status: str
    error: str = ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 46 rendered-image manifest.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--image-dir", default=str(DEFAULT_IMAGE_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    with sqlite3.connect(args.db_path) as connection:
        rows = build_manifest(connection, Path(args.image_dir), ROOT)
    write_manifest(Path(args.output), rows)
    print(
        "summary:",
        f"rows={len(rows)}",
        f"pending={sum(1 for row in rows if row.status == 'pending')}",
        f"existing={sum(1 for row in rows if row.status == 'existing')}",
        f"failed={sum(1 for row in rows if row.status == 'failed')}",
    )
    print(f"wrote {args.output}")


def build_manifest(
    connection: sqlite3.Connection,
    image_dir: Path,
    root: Path = ROOT,
) -> list[RenderManifestRow]:
    titles = read_document_titles(connection)
    existing_paths = read_existing_image_paths(connection)
    rows: list[RenderManifestRow] = []
    for path in sorted(image_dir.rglob("*render*.png")):
        source_image_path = path.resolve().relative_to(root.resolve()).as_posix()
        document_id = infer_document_id(source_image_path)
        page_num = parse_page_num(path.name)
        status = "existing" if source_image_path in existing_paths else "pending"
        width = height = 0
        error = ""
        try:
            pixmap = fitz.Pixmap(path.as_posix())
            width = int(pixmap.width)
            height = int(pixmap.height)
        except Exception as exc:  # noqa: BLE001 - keep manifest complete.
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
        rows.append(
            RenderManifestRow(
                document_id=document_id,
                document_title=titles.get(document_id, ""),
                page_num=page_num,
                source_image_path=source_image_path,
                width=width,
                height=height,
                status=status,
                error=error,
            )
        )
    return rows


def read_document_titles(connection: sqlite3.Connection) -> dict[int, str]:
    return {
        int(row[0]): str(row[1] or "")
        for row in connection.execute("select id, title from documents").fetchall()
    }


def read_existing_image_paths(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "select source_image_path from chunks where chunk_type = 'image_description' and source_image_path is not null"
    ).fetchall()
    return {str(row[0]) for row in rows}


def infer_document_id(source_image_path: str) -> int:
    parts = Path(source_image_path).parts
    try:
        images_index = parts.index("images")
        return int(parts[images_index + 1])
    except (ValueError, IndexError):
        return 0


def parse_page_num(filename: str) -> int:
    match = RENDER_NAME_RE.search(filename)
    if not match:
        return 0
    return int(match.group("page"))


def write_manifest(path: Path, rows: list[RenderManifestRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


if __name__ == "__main__":
    main()
