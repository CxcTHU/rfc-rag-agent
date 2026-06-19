"""Review and optionally remove low-value Phase 45 image_description chunks.

The script writes a review CSV first. With ``--apply`` it deletes only chunks
classified as ``remove`` and their embeddings. Orientation issues are marked
for review but preserved because they may still contain useful engineering
information.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "incoming" / "phase45_literature"
REVIEW_FIELDS = [
    "chunk_id",
    "document_id",
    "chunk_index",
    "char_count",
    "source_image_path",
    "decision",
    "reason",
]

LOW_VALUE_KEYWORDS = (
    "确定性视觉描述",
    "二维码",
    "qr",
    "条形码",
    "barcode",
    "elsevier",
    "sciencedirect",
    "springer",
    "publisher",
    "logo",
    "标志",
    "商标",
    "版权",
    "copyright",
    "non solus",
)
LOW_INFORMATION_KEYWORDS = (
    "简约的线条",
    "两支笔",
    "标识",
    "页面元素",
    "装饰",
)
ORIENTATION_KEYWORDS = (
    "倒立",
    "倒置",
    "侧向",
    "旋转",
)


@dataclass(frozen=True)
class ImageReviewRow:
    chunk_id: int
    document_id: int
    chunk_index: int
    char_count: int
    source_image_path: str
    decision: str
    reason: str


@dataclass(frozen=True)
class ImageCleanSummary:
    total_image_chunks: int
    remove_candidates: int
    review_candidates: int
    kept_chunks: int
    deleted_chunks: int
    deleted_embeddings: int


def classify_image_chunk(content: str, char_count: int) -> tuple[str, str]:
    lowered = content.casefold()
    low_value_hits = [keyword for keyword in LOW_VALUE_KEYWORDS if keyword.casefold() in lowered]
    if low_value_hits:
        return "remove", "low_value_keyword:" + "|".join(low_value_hits)
    if char_count < 60:
        return "remove", "short_description_under_60_chars"
    low_information_hits = [
        keyword for keyword in LOW_INFORMATION_KEYWORDS if keyword.casefold() in lowered
    ]
    if char_count < 90 and low_information_hits:
        return "remove", "low_information_short_description:" + "|".join(low_information_hits)
    orientation_hits = [keyword for keyword in ORIENTATION_KEYWORDS if keyword in content]
    if orientation_hits:
        return "review", "orientation_review:" + "|".join(orientation_hits)
    return "keep", ""


def review_image_chunks(connection: sqlite3.Connection) -> list[ImageReviewRow]:
    rows = connection.execute(
        """
        select id, document_id, chunk_index, char_count, source_image_path, content
        from chunks
        where chunk_type = 'image_description'
        order by id
        """
    ).fetchall()
    review_rows: list[ImageReviewRow] = []
    for row in rows:
        decision, reason = classify_image_chunk(str(row[5] or ""), int(row[3] or 0))
        review_rows.append(
            ImageReviewRow(
                chunk_id=int(row[0]),
                document_id=int(row[1]),
                chunk_index=int(row[2]),
                char_count=int(row[3] or 0),
                source_image_path=str(row[4] or ""),
                decision=decision,
                reason=reason,
            )
        )
    return review_rows


def apply_removals(connection: sqlite3.Connection, rows: list[ImageReviewRow]) -> tuple[int, int]:
    remove_ids = [row.chunk_id for row in rows if row.decision == "remove"]
    if not remove_ids:
        return 0, 0
    placeholders = ",".join("?" for _ in remove_ids)
    deleted_embeddings = connection.execute(
        f"delete from chunk_embeddings where chunk_id in ({placeholders})",
        remove_ids,
    ).rowcount
    deleted_chunks = connection.execute(
        f"delete from chunks where id in ({placeholders})",
        remove_ids,
    ).rowcount
    connection.commit()
    return int(deleted_chunks or 0), int(deleted_embeddings or 0)


def write_outputs(
    rows: list[ImageReviewRow],
    summary: ImageCleanSummary,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    review_path = output_dir / "phase18_image_quality_review.csv"
    summary_path = output_dir / "phase18_image_quality_summary.json"
    with review_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    summary_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return review_path, summary_path


def summarize(rows: list[ImageReviewRow], deleted_chunks: int, deleted_embeddings: int) -> ImageCleanSummary:
    return ImageCleanSummary(
        total_image_chunks=len(rows),
        remove_candidates=sum(1 for row in rows if row.decision == "remove"),
        review_candidates=sum(1 for row in rows if row.decision == "review"),
        kept_chunks=sum(1 for row in rows if row.decision == "keep"),
        deleted_chunks=deleted_chunks,
        deleted_embeddings=deleted_embeddings,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Review and remove low-value Phase 45 image chunks.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with sqlite3.connect(args.db_path) as connection:
        rows = review_image_chunks(connection)
        deleted_chunks = deleted_embeddings = 0
        if args.apply:
            deleted_chunks, deleted_embeddings = apply_removals(connection, rows)
        summary = summarize(rows, deleted_chunks, deleted_embeddings)
    review_path, summary_path = write_outputs(rows, summary, Path(args.output_dir))
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))
    print(f"wrote {review_path}")
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
