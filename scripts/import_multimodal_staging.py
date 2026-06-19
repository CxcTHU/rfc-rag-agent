"""Import staged image descriptions into SQLite chunks serially."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.models import Chunk, Document  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402


@dataclass(frozen=True)
class ImportStagingSummary:
    staging_rows: int
    described_rows: int
    created_chunks: int
    updated_existing_chunks: int
    skipped_existing_chunks: int
    skipped_invalid_rows: int
    elapsed_seconds: float


def main() -> None:
    parser = argparse.ArgumentParser(description="Import staged multimodal descriptions into SQLite chunks.")
    parser.add_argument("--staging-csv", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--update-existing", action="store_true")
    args = parser.parse_args()

    rows = []
    for path_value in args.staging_csv:
        rows.extend(read_staging_rows(Path(path_value)))
    started = time.perf_counter()
    init_db()
    with SessionLocal() as db:
        summary = import_rows(rows, db, started=started, update_existing=args.update_existing)
    write_summary(summary, Path(args.output_dir))


def read_staging_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def import_rows(
    rows: list[dict[str, str]],
    db,
    *,
    started: float | None = None,
    update_existing: bool = False,
) -> ImportStagingSummary:
    if started is None:
        started = time.perf_counter()
    created_chunks = updated_existing = skipped_existing = skipped_invalid = described_rows = 0
    next_indices: dict[int, int] = {}
    for row in rows:
        if row.get("status") != "described":
            continue
        described_rows += 1
        try:
            document_id = int(row.get("document_id") or 0)
        except ValueError:
            skipped_invalid += 1
            continue
        description = (row.get("description") or "").strip()
        image_path = (row.get("source_image_path") or "").strip()
        if not document_id or not description or not image_path:
            skipped_invalid += 1
            continue
        existing_chunk = find_image_chunk(db, image_path)
        if existing_chunk is not None and update_existing:
            existing_chunk.content = description
            existing_chunk.char_count = len(description)
            delete_existing_embeddings(db, existing_chunk.id)
            updated_existing += 1
            continue
        if existing_chunk is not None:
            skipped_existing += 1
            continue
        document = db.get(Document, document_id)
        if document is None:
            skipped_invalid += 1
            continue
        if document_id not in next_indices:
            next_indices[document_id] = next_chunk_index(db, document_id)
        db.add(
            Chunk(
                document_id=document_id,
                chunk_index=next_indices[document_id],
                content=description,
                char_count=len(description),
                heading_path=f"{document.title} > [图表]",
                start_char=None,
                end_char=None,
                chunk_type="image_description",
                source_image_path=image_path,
            )
        )
        next_indices[document_id] += 1
        created_chunks += 1
    db.commit()
    return ImportStagingSummary(
        staging_rows=len(rows),
        described_rows=described_rows,
        created_chunks=created_chunks,
        updated_existing_chunks=updated_existing,
        skipped_existing_chunks=skipped_existing,
        skipped_invalid_rows=skipped_invalid,
        elapsed_seconds=round(time.perf_counter() - started, 3),
    )


def image_chunk_exists(db, image_path: str) -> bool:
    return find_image_chunk(db, image_path) is not None


def find_image_chunk(db, image_path: str) -> Chunk | None:
    return (
        db.scalars(
            select(Chunk).where(
                Chunk.chunk_type == "image_description",
                Chunk.source_image_path == image_path,
            )
        ).first()
    )


def delete_existing_embeddings(db, chunk_id: int) -> None:
    from app.db.models import ChunkEmbedding

    existing_embeddings = db.scalars(
        select(ChunkEmbedding).where(ChunkEmbedding.chunk_id == chunk_id)
    ).all()
    for embedding in existing_embeddings:
        db.delete(embedding)


def next_chunk_index(db, document_id: int) -> int:
    max_index = db.scalar(select(func.max(Chunk.chunk_index)).where(Chunk.document_id == document_id))
    return int(max_index) + 1 if max_index is not None else 0


def write_summary(summary: ImportStagingSummary, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "import_multimodal_staging_summary.json"
    summary_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {summary_path}")
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))


if __name__ == "__main__":
    main()
