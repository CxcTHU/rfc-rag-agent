"""Create embeddings for Phase 45 cloud-candidate text chunks only."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.models import Chunk, ChunkEmbedding  # noqa: E402
from app.db.repositories import ChunkEmbeddingCreate, ChunkEmbeddingRepository  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider  # noqa: E402
from app.services.retrieval.vector_index import calculate_text_hash  # noqa: E402


DEFAULT_AUDIT_PATH = ROOT / "data" / "incoming" / "phase45_literature" / "phase12_quality_audit.csv"
DEFAULT_OUTPUT_PATH = ROOT / "data" / "incoming" / "phase45_literature" / "phase13_embedding_summary.json"


@dataclass(frozen=True)
class Phase45EmbeddingSummary:
    candidate_documents: int
    total_chunks: int
    indexed_chunks: int
    skipped_chunks: int
    updated_chunks: int
    provider: str
    model_name: str
    dimension: int
    elapsed_seconds: float


def read_candidate_document_ids(audit_path: Path) -> list[int]:
    with audit_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = csv.DictReader(file)
        ids = [
            int(row["document_id"])
            for row in rows
            if row.get("review_status") == "cloud_candidate" and row.get("document_id")
        ]
    return sorted(set(ids))


def read_imported_document_ids(audit_path: Path) -> list[int]:
    with audit_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = csv.DictReader(file)
        ids = [
            int(row["document_id"])
            for row in rows
            if row.get("import_status") == "imported" and row.get("document_id")
        ]
    return sorted(set(ids))


def read_all_document_ids(db: Session) -> list[int]:
    return [int(value) for value in db.scalars(select(Chunk.document_id).distinct()).all()]


def list_candidate_chunks(db: Session, document_ids: list[int]) -> list[Chunk]:
    return list_candidate_chunks_by_type(db, document_ids, chunk_type="text")


def list_candidate_chunks_by_type(db: Session, document_ids: list[int], chunk_type: str) -> list[Chunk]:
    if not document_ids:
        return []
    conditions = [Chunk.document_id.in_(document_ids)]
    if chunk_type != "all":
        conditions.append(Chunk.chunk_type == chunk_type)
    statement = (
        select(Chunk)
        .where(*conditions)
        .order_by(Chunk.id)
    )
    return list(db.scalars(statement).all())


def index_candidate_chunks(
    db: Session,
    provider: EmbeddingProvider,
    document_ids: list[int],
    chunk_type: str = "text",
    batch_size: int = 16,
    sleep_seconds: float = 0.0,
) -> Phase45EmbeddingSummary:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    started = time.perf_counter()
    repository = ChunkEmbeddingRepository(db)
    chunks = list_candidate_chunks_by_type(db, document_ids, chunk_type=chunk_type)
    pending: list[tuple[Chunk, str, bool]] = []
    skipped = indexed = updated = 0

    for chunk in chunks:
        content_hash = calculate_text_hash(chunk.content)
        existing = repository.get_embedding(
            chunk_id=chunk.id,
            provider=provider.provider_name,
            model_name=provider.model_name,
        )
        if existing and existing.content_hash == content_hash and existing.dimension == provider.dimension:
            skipped += 1
            continue
        pending.append((chunk, content_hash, existing is not None))

    for batch in batched(pending, batch_size):
        embeddings = provider.embed_texts([chunk.content for chunk, _hash, _exists in batch])
        if len(embeddings) != len(batch):
            raise ValueError("embedding provider returned an unexpected number of vectors")
        for (chunk, content_hash, existed), embedding in zip(batch, embeddings, strict=True):
            if len(embedding) != provider.dimension:
                raise ValueError("embedding provider returned a vector with unexpected dimension")
            repository.save_embedding(
                ChunkEmbeddingCreate(
                    chunk_id=chunk.id,
                    provider=provider.provider_name,
                    model_name=provider.model_name,
                    dimension=provider.dimension,
                    embedding=embedding,
                    content_hash=content_hash,
                ),
                commit=False,
            )
            if existed:
                updated += 1
            else:
                indexed += 1
        db.commit()
        if sleep_seconds:
            time.sleep(sleep_seconds)

    return Phase45EmbeddingSummary(
        candidate_documents=len(document_ids),
        total_chunks=len(chunks),
        indexed_chunks=indexed,
        skipped_chunks=skipped,
        updated_chunks=updated,
        provider=provider.provider_name,
        model_name=provider.model_name,
        dimension=provider.dimension,
        elapsed_seconds=round(time.perf_counter() - started, 3),
    )


def prune_non_candidate_embeddings(
    db: Session,
    provider: EmbeddingProvider,
    imported_document_ids: list[int],
    candidate_document_ids: list[int],
    chunk_type: str = "text",
) -> int:
    non_candidate_ids = sorted(set(imported_document_ids) - set(candidate_document_ids))
    if not non_candidate_ids:
        return 0
    chunk_ids = [
        chunk_id
        for (chunk_id,) in db.execute(
            select(Chunk.id).where(
                Chunk.document_id.in_(non_candidate_ids),
                *((Chunk.chunk_type == chunk_type,) if chunk_type != "all" else ()),
            )
        ).all()
    ]
    if not chunk_ids:
        return 0
    embeddings = db.scalars(
        select(ChunkEmbedding).where(
            ChunkEmbedding.chunk_id.in_(chunk_ids),
            ChunkEmbedding.provider == provider.provider_name,
            ChunkEmbedding.model_name == provider.model_name,
        )
    ).all()
    deleted = len(embeddings)
    for embedding in embeddings:
        db.delete(embedding)
    db.commit()
    return deleted


def batched(items: list[tuple[Chunk, str, bool]], batch_size: int) -> list[list[tuple[Chunk, str, bool]]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def build_provider_from_settings(args: argparse.Namespace) -> EmbeddingProvider:
    settings = get_settings()
    return create_embedding_provider(
        provider_name=args.provider or settings.embedding_provider,
        model_name=args.model_name or settings.embedding_model_name,
        api_key=args.api_key or settings.embedding_api_key,
        base_url=args.base_url or settings.embedding_base_url,
        dimension=args.dimension or settings.embedding_dimension,
        timeout_seconds=args.timeout_seconds or settings.embedding_timeout_seconds,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Phase 45 cloud-candidate chunks.")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--provider", default="")
    parser.add_argument("--model-name", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--dimension", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=float, default=0.0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--prune-non-candidates", action="store_true")
    parser.add_argument("--chunk-type", default="text", choices=["text", "image_description", "all"])
    parser.add_argument("--all-documents", action="store_true", help="Index matching chunks across all documents.")
    args = parser.parse_args()

    provider = build_provider_from_settings(args)
    init_db()
    with SessionLocal() as db:
        document_ids = read_all_document_ids(db) if args.all_documents else read_candidate_document_ids(Path(args.audit))
        pruned = 0
        if args.prune_non_candidates and not args.all_documents:
            pruned = prune_non_candidate_embeddings(
                db=db,
                provider=provider,
                imported_document_ids=read_imported_document_ids(Path(args.audit)),
                candidate_document_ids=document_ids,
                chunk_type=args.chunk_type,
            )
        summary = index_candidate_chunks(
            db=db,
            provider=provider,
            document_ids=document_ids,
            chunk_type=args.chunk_type,
            batch_size=args.batch_size,
            sleep_seconds=args.sleep_seconds,
        )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if pruned:
        print(f"pruned_non_candidate_embeddings={pruned}")
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
