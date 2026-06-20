"""Backfill page_number for image_description chunks from image file names."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.agent.tools import page_number_from_source_image_path  # noqa: E402


DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_SUMMARY_JSON = ROOT / "data" / "evaluation" / "phase46_image_page_number_summary.json"


@dataclass(frozen=True)
class PageNumberSummary:
    total_image_chunks: int
    parsed_page_numbers: int
    already_had_page_number: int
    updated_rows: int
    failed_to_parse: int
    apply: bool
    elapsed_seconds: float


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill image chunk page numbers.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY_JSON))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    with sqlite3.connect(args.db_path, timeout=30) as connection:
        summary = backfill_page_numbers(connection, apply=args.apply)
        if args.apply:
            connection.commit()

    summary = PageNumberSummary(
        **{
            **asdict(summary),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    )
    write_summary(Path(args.summary_json), summary)
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))
    print(f"wrote {args.summary_json}")


def backfill_page_numbers(connection: sqlite3.Connection, *, apply: bool) -> PageNumberSummary:
    ensure_page_number_column(connection)
    rows = connection.execute(
        """
        select id, source_image_path, page_number
        from chunks
        where chunk_type = 'image_description'
          and source_image_path is not null
          and source_image_path != ''
        order by id
        """
    ).fetchall()
    parsed = 0
    already_had = 0
    updated = 0
    failed = 0
    for chunk_id, source_image_path, existing_page_number in rows:
        page_number = page_number_from_source_image_path(str(source_image_path or ""))
        if page_number is None:
            failed += 1
            continue
        parsed += 1
        if existing_page_number == page_number:
            already_had += 1
            continue
        if apply:
            connection.execute(
                "update chunks set page_number = ? where id = ?",
                (page_number, int(chunk_id)),
            )
            updated += 1
    return PageNumberSummary(
        total_image_chunks=len(rows),
        parsed_page_numbers=parsed,
        already_had_page_number=already_had,
        updated_rows=updated,
        failed_to_parse=failed,
        apply=apply,
        elapsed_seconds=0.0,
    )


def ensure_page_number_column(connection: sqlite3.Connection) -> None:
    columns = {
        str(row[1])
        for row in connection.execute("pragma table_info(chunks)").fetchall()
    }
    if "page_number" not in columns:
        raise RuntimeError("chunks.page_number column is missing; run alembic upgrade head first")


def write_summary(path: Path, summary: PageNumberSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
