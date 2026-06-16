from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.models import Chunk, Document  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.ingestion.splitter import TextChunk, split_text  # noqa: E402


PARENT_HEADING_PREFIX = "__stage31_parent__"
CHILD_JOIN_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class ChildSpan:
    chunk: Chunk
    start: int
    end: int


@dataclass(frozen=True)
class BackfillStats:
    documents_seen: int = 0
    documents_changed: int = 0
    parent_chunks_created: int = 0
    parent_chunks_reused: int = 0
    child_chunks_seen: int = 0
    child_chunks_updated: int = 0
    skipped_documents: int = 0
    dry_run: bool = False

    def merge(self, other: "BackfillStats") -> "BackfillStats":
        return BackfillStats(
            documents_seen=self.documents_seen + other.documents_seen,
            documents_changed=self.documents_changed + other.documents_changed,
            parent_chunks_created=self.parent_chunks_created + other.parent_chunks_created,
            parent_chunks_reused=self.parent_chunks_reused + other.parent_chunks_reused,
            child_chunks_seen=self.child_chunks_seen + other.child_chunks_seen,
            child_chunks_updated=self.child_chunks_updated + other.child_chunks_updated,
            skipped_documents=self.skipped_documents + other.skipped_documents,
            dry_run=self.dry_run or other.dry_run,
        )

    def format_summary(self) -> str:
        return (
            "parent chunk backfill\t"
            f"dry_run={self.dry_run}\t"
            f"documents_seen={self.documents_seen}\t"
            f"documents_changed={self.documents_changed}\t"
            f"parent_created={self.parent_chunks_created}\t"
            f"parent_reused={self.parent_chunks_reused}\t"
            f"child_seen={self.child_chunks_seen}\t"
            f"child_updated={self.child_chunks_updated}\t"
            f"skipped_documents={self.skipped_documents}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill stage 31 parent chunks and link existing child chunks.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report intended writes without changing DB.")
    parser.add_argument("--document-id", type=int, default=0, help="Only process one document id.")
    parser.add_argument("--limit-documents", type=int, default=0, help="Limit processed documents. 0 means all.")
    parser.add_argument("--parent-chunk-size", type=int, default=1800, help="Target parent chunk size.")
    parser.add_argument("--parent-chunk-overlap", type=int, default=120, help="Parent chunk overlap.")
    args = parser.parse_args()

    if args.document_id < 0:
        raise ValueError("document-id must be greater than or equal to 0")
    if args.limit_documents < 0:
        raise ValueError("limit-documents must be greater than or equal to 0")

    init_db()
    with SessionLocal() as db:
        stats = backfill_parent_chunks(
            db=db,
            dry_run=args.dry_run,
            document_id=args.document_id or None,
            limit_documents=args.limit_documents or None,
            parent_chunk_size=args.parent_chunk_size,
            parent_chunk_overlap=args.parent_chunk_overlap,
        )
    print(stats.format_summary())


def backfill_parent_chunks(
    db: Session,
    dry_run: bool = False,
    document_id: int | None = None,
    limit_documents: int | None = None,
    parent_chunk_size: int = 1800,
    parent_chunk_overlap: int = 120,
) -> BackfillStats:
    if parent_chunk_size <= 0:
        raise ValueError("parent_chunk_size must be greater than 0")
    if parent_chunk_overlap < 0:
        raise ValueError("parent_chunk_overlap must be greater than or equal to 0")
    if parent_chunk_overlap >= parent_chunk_size:
        raise ValueError("parent_chunk_overlap must be smaller than parent_chunk_size")
    if limit_documents is not None and limit_documents <= 0:
        raise ValueError("limit_documents must be greater than 0")

    statement = select(Document).order_by(Document.id)
    if document_id is not None:
        statement = statement.where(Document.id == document_id)
    if limit_documents is not None:
        statement = statement.limit(limit_documents)

    stats = BackfillStats(dry_run=dry_run)
    for document in db.scalars(statement).all():
        document_stats = backfill_document_parent_chunks(
            db=db,
            document=document,
            dry_run=dry_run,
            parent_chunk_size=parent_chunk_size,
            parent_chunk_overlap=parent_chunk_overlap,
        )
        stats = stats.merge(document_stats)

    if not dry_run:
        db.commit()
    else:
        db.rollback()
    return stats


def backfill_document_parent_chunks(
    db: Session,
    document: Document,
    dry_run: bool,
    parent_chunk_size: int,
    parent_chunk_overlap: int,
) -> BackfillStats:
    child_chunks = list_existing_child_chunks(db, document.id)
    if not child_chunks:
        return BackfillStats(documents_seen=1, skipped_documents=1, dry_run=dry_run)

    reconstructed_text, child_spans = reconstruct_child_text(child_chunks)
    parent_plans = split_text(
        reconstructed_text,
        chunk_size=parent_chunk_size,
        chunk_overlap=parent_chunk_overlap,
    )
    if not parent_plans:
        return BackfillStats(
            documents_seen=1,
            child_chunks_seen=len(child_chunks),
            skipped_documents=1,
            dry_run=dry_run,
        )

    existing_parents = list_existing_parent_chunks(db, document.id)
    parent_chunks = existing_parents
    created_count = 0
    reused_count = len(existing_parents)

    if not existing_parents:
        created_count = len(parent_plans)
        if not dry_run:
            parent_chunks = create_parent_chunks(
                db=db,
                document_id=document.id,
                parent_plans=parent_plans,
            )

    child_updates = 0
    if parent_chunks:
        for span in child_spans:
            parent = choose_parent_for_child(span, parent_chunks)
            if parent is not None and span.chunk.parent_chunk_id != parent.id:
                child_updates += 1
                if not dry_run:
                    span.chunk.parent_chunk_id = parent.id
    else:
        child_updates = count_child_parent_updates_for_dry_run(child_spans, parent_plans)

    changed = created_count > 0 or child_updates > 0
    return BackfillStats(
        documents_seen=1,
        documents_changed=1 if changed else 0,
        parent_chunks_created=created_count,
        parent_chunks_reused=reused_count,
        child_chunks_seen=len(child_chunks),
        child_chunks_updated=child_updates,
        dry_run=dry_run,
    )


def list_existing_child_chunks(db: Session, document_id: int) -> list[Chunk]:
    statement = (
        select(Chunk)
        .where(
            Chunk.document_id == document_id,
            or_(
                Chunk.heading_path.is_(None),
                ~Chunk.heading_path.like(f"{PARENT_HEADING_PREFIX}%"),
            ),
        )
        .order_by(Chunk.chunk_index, Chunk.id)
    )
    return list(db.scalars(statement).all())


def list_existing_parent_chunks(db: Session, document_id: int) -> list[Chunk]:
    statement = (
        select(Chunk)
        .where(
            Chunk.document_id == document_id,
            Chunk.heading_path.like(f"{PARENT_HEADING_PREFIX}%"),
        )
        .order_by(Chunk.chunk_index, Chunk.id)
    )
    return list(db.scalars(statement).all())


def reconstruct_child_text(chunks: list[Chunk]) -> tuple[str, list[ChildSpan]]:
    parts: list[str] = []
    spans: list[ChildSpan] = []
    cursor = 0
    for chunk in chunks:
        if parts:
            parts.append(CHILD_JOIN_SEPARATOR)
            cursor += len(CHILD_JOIN_SEPARATOR)
        content = chunk.content.strip()
        start = cursor
        parts.append(content)
        cursor += len(content)
        spans.append(ChildSpan(chunk=chunk, start=start, end=cursor))
    return "".join(parts), spans


def create_parent_chunks(
    db: Session,
    document_id: int,
    parent_plans: list[TextChunk],
) -> list[Chunk]:
    next_index = next_parent_chunk_index(db, document_id)
    parent_chunks: list[Chunk] = []
    for offset, plan in enumerate(parent_plans):
        parent = Chunk(
            document_id=document_id,
            chunk_index=next_index + offset,
            content=plan.content,
            char_count=plan.char_count,
            heading_path=parent_heading_path(offset, plan.heading_path),
            start_char=plan.start_char,
            end_char=plan.end_char,
            parent_chunk_id=None,
        )
        db.add(parent)
        parent_chunks.append(parent)
    db.flush()
    return parent_chunks


def next_parent_chunk_index(db: Session, document_id: int) -> int:
    statement = select(func.max(Chunk.chunk_index)).where(Chunk.document_id == document_id)
    max_index = db.scalar(statement)
    return int(max_index or 0) + 1


def parent_heading_path(parent_index: int, original_heading: str | None) -> str:
    suffix = f":{parent_index}"
    if original_heading:
        return f"{PARENT_HEADING_PREFIX}{suffix}:{original_heading}"[:500]
    return f"{PARENT_HEADING_PREFIX}{suffix}"


def choose_parent_for_child(span: ChildSpan, parents: list[Chunk]) -> Chunk | None:
    best_parent: Chunk | None = None
    best_overlap = -1
    for parent in parents:
        if parent.start_char is None or parent.end_char is None:
            continue
        overlap = interval_overlap(span.start, span.end, parent.start_char, parent.end_char)
        if overlap > best_overlap:
            best_overlap = overlap
            best_parent = parent
    if best_parent is not None and best_overlap > 0:
        return best_parent
    return choose_nearest_parent_for_child(span, parents)


def choose_nearest_parent_for_child(span: ChildSpan, parents: list[Chunk]) -> Chunk | None:
    best_parent: Chunk | None = None
    best_distance: int | None = None
    child_center = (span.start + span.end) // 2
    for parent in parents:
        if parent.start_char is None or parent.end_char is None:
            continue
        parent_center = (parent.start_char + parent.end_char) // 2
        distance = abs(parent_center - child_center)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_parent = parent
    return best_parent


def count_child_parent_updates_for_dry_run(
    child_spans: list[ChildSpan],
    parent_plans: list[TextChunk],
) -> int:
    updates = 0
    for span in child_spans:
        best_overlap = max(
            interval_overlap(span.start, span.end, parent.start_char, parent.end_char)
            for parent in parent_plans
        )
        if best_overlap > 0:
            updates += 1
    return updates


def interval_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> int:
    return max(0, min(end_a, end_b) - max(start_a, start_b))


if __name__ == "__main__":
    main()
