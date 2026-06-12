from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document, Source
from app.db.session import SessionLocal


DEFAULT_CANDIDATES_CSV = Path("data/evaluation/stage28_crawl_quality_drop_candidates.csv")
DEFAULT_RAW_ROOT = Path("data/raw")


@dataclass(frozen=True)
class DatabaseCounts:
    documents: int
    chunks: int
    chunk_embeddings: int
    sources: int


@dataclass(frozen=True)
class CleanupPlan:
    candidate_ids: list[int]
    existing_document_ids: list[int]
    missing_document_ids: list[int]
    non_web_page_ids: list[int]
    chunks_to_delete: int
    embeddings_to_delete: int
    sources_to_unlink: int
    raw_files_to_delete: list[Path]
    missing_raw_files: list[Path]
    unsafe_raw_paths: list[Path]


@dataclass(frozen=True)
class CleanupResult:
    before: DatabaseCounts
    after: DatabaseCounts
    plan: CleanupPlan
    dry_run: bool
    deleted_documents: int
    deleted_raw_files: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean low-quality Stage 28 crawl drop candidates.")
    parser.add_argument(
        "--candidates-csv",
        type=Path,
        default=DEFAULT_CANDIDATES_CSV,
        help="CSV containing document_id values to delete.",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=DEFAULT_RAW_ROOT,
        help="Root directory that contains Stage 28 Markdown files referenced by documents/sources.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview database/file changes without deleting anything.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate_ids = read_candidate_document_ids(args.candidates_csv)
    with SessionLocal() as db:
        result = cleanup_drop_candidates(
            db=db,
            candidate_ids=candidate_ids,
            raw_root=args.raw_root,
            dry_run=args.dry_run,
        )
    print_result(result)
    return 0


def read_candidate_document_ids(path: Path) -> list[int]:
    if not path.exists():
        raise FileNotFoundError(f"Candidate CSV was not found: {path}")

    seen: set[int] = set()
    ids: list[int] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if "document_id" not in (reader.fieldnames or []):
            raise ValueError(f"Candidate CSV must contain document_id column: {path}")
        for row_number, row in enumerate(reader, start=2):
            raw_value = (row.get("document_id") or "").strip()
            if not raw_value:
                continue
            try:
                document_id = int(raw_value)
            except ValueError as exc:
                raise ValueError(f"Invalid document_id at row {row_number}: {raw_value!r}") from exc
            if document_id not in seen:
                seen.add(document_id)
                ids.append(document_id)
    return ids


def cleanup_drop_candidates(
    *,
    db: Session,
    candidate_ids: list[int],
    raw_root: Path = DEFAULT_RAW_ROOT,
    dry_run: bool = True,
) -> CleanupResult:
    before = count_database_rows(db)
    plan = build_cleanup_plan(db, candidate_ids, raw_root)
    if plan.unsafe_raw_paths:
        unsafe = ", ".join(str(path) for path in plan.unsafe_raw_paths[:5])
        raise ValueError(f"Unsafe raw_path outside {raw_root}: {unsafe}")

    deleted_raw_files = 0
    deleted_documents = 0
    if not dry_run:
        sources = db.scalars(select(Source).where(Source.document_id.in_(plan.existing_document_ids))).all()
        for source in sources:
            source.document_id = None

        documents = db.scalars(select(Document).where(Document.id.in_(plan.existing_document_ids))).all()
        for document in documents:
            db.delete(document)
            deleted_documents += 1

        db.commit()

        for raw_file in plan.raw_files_to_delete:
            try:
                raw_file.unlink()
                deleted_raw_files += 1
            except FileNotFoundError:
                continue

    after = count_database_rows(db)
    return CleanupResult(
        before=before,
        after=after,
        plan=plan,
        dry_run=dry_run,
        deleted_documents=deleted_documents,
        deleted_raw_files=deleted_raw_files,
    )


def build_cleanup_plan(db: Session, candidate_ids: list[int], raw_root: Path) -> CleanupPlan:
    documents = list(db.scalars(select(Document).where(Document.id.in_(candidate_ids))).all())
    document_by_id = {document.id: document for document in documents}
    missing_ids = [document_id for document_id in candidate_ids if document_id not in document_by_id]
    non_web_page_ids = [
        document.id for document in documents if document.source_type != "web_page"
    ]
    web_page_documents = [document for document in documents if document.source_type == "web_page"]
    web_page_ids = [document.id for document in web_page_documents]

    chunks_to_delete = (
        db.scalar(select(func.count(Chunk.id)).where(Chunk.document_id.in_(web_page_ids))) if web_page_ids else 0
    ) or 0
    embeddings_to_delete = (
        db.scalar(
            select(func.count(ChunkEmbedding.id))
            .join(Chunk, ChunkEmbedding.chunk_id == Chunk.id)
            .where(Chunk.document_id.in_(web_page_ids))
        )
        if web_page_ids
        else 0
    ) or 0
    sources_to_unlink = (
        db.scalar(select(func.count(Source.id)).where(Source.document_id.in_(web_page_ids))) if web_page_ids else 0
    ) or 0

    source_paths_by_document: dict[int, list[str]] = {document_id: [] for document_id in web_page_ids}
    if web_page_ids:
        linked_sources = db.scalars(select(Source).where(Source.document_id.in_(web_page_ids))).all()
        for source in linked_sources:
            if source.document_id is None:
                continue
            if source.local_path:
                source_paths_by_document.setdefault(source.document_id, []).append(source.local_path)

    raw_files_to_delete: list[Path] = []
    missing_raw_files: list[Path] = []
    unsafe_raw_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for document in web_page_documents:
        candidate_paths = [document.raw_path, *source_paths_by_document.get(document.id, [])]
        for candidate_path in candidate_paths:
            add_raw_file_candidate(
                candidate_path,
                raw_root=raw_root,
                seen_paths=seen_paths,
                raw_files_to_delete=raw_files_to_delete,
                missing_raw_files=missing_raw_files,
                unsafe_raw_paths=unsafe_raw_paths,
            )

    return CleanupPlan(
        candidate_ids=candidate_ids,
        existing_document_ids=web_page_ids,
        missing_document_ids=missing_ids,
        non_web_page_ids=non_web_page_ids,
        chunks_to_delete=int(chunks_to_delete),
        embeddings_to_delete=int(embeddings_to_delete),
        sources_to_unlink=int(sources_to_unlink),
        raw_files_to_delete=raw_files_to_delete,
        missing_raw_files=missing_raw_files,
        unsafe_raw_paths=unsafe_raw_paths,
    )


def add_raw_file_candidate(
    candidate_path: str,
    *,
    raw_root: Path,
    seen_paths: set[Path],
    raw_files_to_delete: list[Path],
    missing_raw_files: list[Path],
    unsafe_raw_paths: list[Path],
) -> None:
    raw_path = Path(candidate_path)
    if raw_path.suffix.casefold() != ".md":
        unsafe_raw_paths.append(raw_path)
        return
    if not raw_path.is_absolute():
        raw_path = Path.cwd() / raw_path
    raw_path = raw_path.resolve()
    if raw_path in seen_paths:
        return
    seen_paths.add(raw_path)
    if not is_relative_to(raw_path, raw_root):
        unsafe_raw_paths.append(raw_path)
        return
    if raw_path.exists():
        raw_files_to_delete.append(raw_path)
    else:
        missing_raw_files.append(raw_path)


def is_relative_to(path: Path, root: Path) -> bool:
    resolved_root = root if root.is_absolute() else Path.cwd() / root
    resolved_root = resolved_root.resolve()
    try:
        path.relative_to(resolved_root)
    except ValueError:
        return False
    return True


def count_database_rows(db: Session) -> DatabaseCounts:
    return DatabaseCounts(
        documents=int(db.scalar(select(func.count(Document.id))) or 0),
        chunks=int(db.scalar(select(func.count(Chunk.id))) or 0),
        chunk_embeddings=int(db.scalar(select(func.count(ChunkEmbedding.id))) or 0),
        sources=int(db.scalar(select(func.count(Source.id))) or 0),
    )


def print_result(result: CleanupResult) -> None:
    mode = "dry_run" if result.dry_run else "deleted"
    plan = result.plan
    print(f"mode={mode}")
    print(f"candidate_ids={len(plan.candidate_ids)}")
    print(f"existing_web_page_documents={len(plan.existing_document_ids)}")
    print(f"missing_documents={len(plan.missing_document_ids)}")
    print(f"non_web_page_documents={len(plan.non_web_page_ids)}")
    print(f"chunks_to_delete={plan.chunks_to_delete}")
    print(f"embeddings_to_delete={plan.embeddings_to_delete}")
    print(f"sources_to_unlink={plan.sources_to_unlink}")
    print(f"raw_files_to_delete={len(plan.raw_files_to_delete)}")
    print(f"missing_raw_files={len(plan.missing_raw_files)}")
    print(f"unsafe_raw_paths={len(plan.unsafe_raw_paths)}")
    print(f"deleted_documents={result.deleted_documents}")
    print(f"deleted_raw_files={result.deleted_raw_files}")
    print(
        "before="
        f"documents:{result.before.documents},"
        f"chunks:{result.before.chunks},"
        f"chunk_embeddings:{result.before.chunk_embeddings},"
        f"sources:{result.before.sources}"
    )
    print(
        "after="
        f"documents:{result.after.documents},"
        f"chunks:{result.after.chunks},"
        f"chunk_embeddings:{result.after.chunk_embeddings},"
        f"sources:{result.after.sources}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
