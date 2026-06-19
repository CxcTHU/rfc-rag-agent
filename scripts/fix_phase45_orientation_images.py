"""Re-render orientation-review PDF images as displayed on their source page."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_REVIEW_CSV = (
    ROOT
    / "data"
    / "incoming"
    / "phase45_literature"
    / "phase45_five_route_all_pdf_resume2"
    / "cleanup"
    / "phase18_image_quality_review.csv"
)
DEFAULT_OUTPUT_DIR = ROOT / "data" / "incoming" / "phase45_literature" / "phase45_orientation_fix"
IMAGE_NAME_RE = re.compile(r"page(?P<page>\d+)_img(?P<image>\d+)\.png$", re.IGNORECASE)
REPORT_FIELDS = [
    "chunk_id",
    "document_id",
    "source_image_path",
    "status",
    "reason",
    "backup_path",
    "error",
]


@dataclass(frozen=True)
class OrientationFixRow:
    chunk_id: int
    document_id: int
    source_image_path: str
    status: str
    reason: str
    backup_path: str
    error: str


@dataclass(frozen=True)
class OrientationFixSummary:
    candidates: int
    fixed: int
    skipped: int
    failed: int


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix Phase 45 orientation-review images.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--review-csv", default=str(DEFAULT_REVIEW_CSV))
    parser.add_argument("--document-id", type=int, action="append", default=[])
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--zoom", type=float, default=2.0)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    rows = load_target_rows(Path(args.review_csv), args.document_id, args.db_path)
    with sqlite3.connect(args.db_path) as connection:
        report_rows = [
            fix_row(row, connection, output_dir=output_dir, zoom=args.zoom, apply=args.apply)
            for row in rows
        ]
    summary = summarize(report_rows)
    write_outputs(report_rows, summary, output_dir)
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))


def load_orientation_rows(review_csv: Path) -> list[dict[str, str]]:
    with review_csv.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return [row for row in rows if row.get("decision") == "review"]


def load_target_rows(review_csv: Path, document_ids: list[int], db_path: str) -> list[dict[str, str]]:
    if not document_ids:
        return load_orientation_rows(review_csv)
    document_id_set = {str(document_id) for document_id in document_ids}
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            select id, document_id, chunk_index, char_count, source_image_path
            from chunks
            where chunk_type = 'image_description'
            order by document_id, source_image_path, id
            """
        ).fetchall()
    return [
        {
            "chunk_id": str(row[0]),
            "document_id": str(row[1]),
            "chunk_index": str(row[2]),
            "char_count": str(row[3] or 0),
            "source_image_path": str(row[4] or ""),
            "decision": "review",
            "reason": "manual_document_orientation_fix",
        }
        for row in rows
        if str(row[1]) in document_id_set and row[4]
    ]


def fix_row(
    row: dict[str, str],
    connection: sqlite3.Connection,
    *,
    output_dir: Path,
    zoom: float,
    apply: bool,
) -> OrientationFixRow:
    source_image_path = row.get("source_image_path", "")
    image_path = (ROOT / source_image_path).resolve()
    backup_path = backup_target(output_dir, source_image_path)
    try:
        document_id = int(row["document_id"])
        chunk_id = int(row["chunk_id"])
        page_num, image_num = parse_image_name(image_path)
        raw_path_row = connection.execute(
            "select raw_path from documents where id = ?",
            (document_id,),
        ).fetchone()
        if raw_path_row is None or not raw_path_row[0]:
            return report(row, "failed", "", "document raw_path not found")
        pdf_path = (ROOT / str(raw_path_row[0])).resolve()
        if not pdf_path.exists():
            return report(row, "failed", "", f"pdf not found: {pdf_path}")
        if not image_path.exists():
            return report(row, "failed", "", f"image not found: {image_path}")
        if not apply:
            return report(row, "skipped", "", "dry-run")
        backup_path = backup_path.resolve()
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image_path, backup_path)
        render_displayed_image(pdf_path, page_num, image_num, image_path, zoom=zoom)
        return OrientationFixRow(
            chunk_id=chunk_id,
            document_id=document_id,
            source_image_path=source_image_path,
            status="fixed",
            reason=row.get("reason", ""),
            backup_path=backup_path.relative_to(ROOT).as_posix(),
            error="",
        )
    except Exception as exc:  # noqa: BLE001 - report per-row failures and continue.
        return report(row, "failed", "", f"{type(exc).__name__}: {exc}")


def parse_image_name(image_path: Path) -> tuple[int, int]:
    match = IMAGE_NAME_RE.search(image_path.name)
    if not match:
        raise ValueError(f"cannot parse page/image number from {image_path.name}")
    return int(match.group("page")), int(match.group("image"))


def render_displayed_image(pdf_path: Path, page_num: int, image_num: int, output_path: Path, *, zoom: float) -> None:
    with fitz.open(pdf_path) as pdf:
        page = pdf.load_page(page_num - 1)
        images = page.get_images(full=True)
        if image_num < 1 or image_num > len(images):
            raise ValueError(f"image index {image_num} out of range on page {page_num}")
        xref = images[image_num - 1][0]
        rects = page.get_image_rects(xref)
        if not rects:
            raise ValueError(f"image xref {xref} has no display rect on page {page_num}")
        rect = max(rects, key=lambda item: item.width * item.height)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
        temp_path = output_path.with_name(f"{output_path.name}.tmp")
        try:
            pixmap.save(temp_path)
            temp_path.replace(output_path)
        finally:
            temp_path.unlink(missing_ok=True)


def backup_target(output_dir: Path, source_image_path: str) -> Path:
    return (ROOT / output_dir / "backups" / source_image_path).resolve()


def report(row: dict[str, str], status: str, backup_path: str, error: str) -> OrientationFixRow:
    return OrientationFixRow(
        chunk_id=int(row.get("chunk_id") or 0),
        document_id=int(row.get("document_id") or 0),
        source_image_path=row.get("source_image_path", ""),
        status=status,
        reason=row.get("reason", ""),
        backup_path=backup_path,
        error=error,
    )


def summarize(rows: list[OrientationFixRow]) -> OrientationFixSummary:
    return OrientationFixSummary(
        candidates=len(rows),
        fixed=sum(1 for row in rows if row.status == "fixed"),
        skipped=sum(1 for row in rows if row.status == "skipped"),
        failed=sum(1 for row in rows if row.status == "failed"),
    )


def write_outputs(
    rows: list[OrientationFixRow],
    summary: OrientationFixSummary,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "orientation_fix_report.csv"
    summary_path = output_dir / "orientation_fix_summary.json"
    with report_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    summary_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {report_path}")
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
