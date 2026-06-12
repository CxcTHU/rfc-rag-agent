from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.models import Chunk, ChunkEmbedding  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402


@dataclass(frozen=True)
class ProviderEmbeddingCount:
    provider: str
    model_name: str
    dimension: int
    count: int


@dataclass(frozen=True)
class EmbeddingCleanupStats:
    total_embeddings: int
    total_chunks: int
    orphan_embeddings: int
    selected_embeddings: int
    deleted_embeddings: int
    provider_filter: str | None
    executed: bool
    provider_counts: tuple[ProviderEmbeddingCount, ...]


def collect_embedding_cleanup_stats(
    db: Session,
    provider: str | None = None,
) -> EmbeddingCleanupStats:
    provider_filter = normalize_provider(provider)
    total_embeddings = scalar_count(db, select(func.count(ChunkEmbedding.id)))
    total_chunks = scalar_count(db, select(func.count(Chunk.id)))
    orphan_embeddings = scalar_count(
        db,
        select(func.count(ChunkEmbedding.id))
        .outerjoin(Chunk, ChunkEmbedding.chunk_id == Chunk.id)
        .where(Chunk.id.is_(None)),
    )

    selected_statement = select(func.count(ChunkEmbedding.id))
    if provider_filter is not None:
        selected_statement = selected_statement.where(ChunkEmbedding.provider == provider_filter)
    selected_embeddings = scalar_count(db, selected_statement)

    provider_rows = db.execute(
        select(
            ChunkEmbedding.provider,
            ChunkEmbedding.model_name,
            ChunkEmbedding.dimension,
            func.count(ChunkEmbedding.id),
        )
        .group_by(
            ChunkEmbedding.provider,
            ChunkEmbedding.model_name,
            ChunkEmbedding.dimension,
        )
        .order_by(
            ChunkEmbedding.provider,
            ChunkEmbedding.model_name,
            ChunkEmbedding.dimension,
        )
    ).all()
    provider_counts = tuple(
        ProviderEmbeddingCount(
            provider=str(row[0]),
            model_name=str(row[1]),
            dimension=int(row[2]),
            count=int(row[3]),
        )
        for row in provider_rows
    )

    return EmbeddingCleanupStats(
        total_embeddings=total_embeddings,
        total_chunks=total_chunks,
        orphan_embeddings=orphan_embeddings,
        selected_embeddings=selected_embeddings,
        deleted_embeddings=0,
        provider_filter=provider_filter,
        executed=False,
        provider_counts=provider_counts,
    )


def cleanup_embeddings(
    db: Session,
    provider: str | None = None,
    execute: bool = False,
) -> EmbeddingCleanupStats:
    dry_run_stats = collect_embedding_cleanup_stats(db, provider=provider)
    if not execute:
        return dry_run_stats

    statement = delete(ChunkEmbedding)
    if dry_run_stats.provider_filter is not None:
        statement = statement.where(ChunkEmbedding.provider == dry_run_stats.provider_filter)
    result = db.execute(statement)
    db.commit()

    deleted_embeddings = int(result.rowcount or 0)
    return EmbeddingCleanupStats(
        total_embeddings=dry_run_stats.total_embeddings,
        total_chunks=dry_run_stats.total_chunks,
        orphan_embeddings=dry_run_stats.orphan_embeddings,
        selected_embeddings=dry_run_stats.selected_embeddings,
        deleted_embeddings=deleted_embeddings,
        provider_filter=dry_run_stats.provider_filter,
        executed=True,
        provider_counts=dry_run_stats.provider_counts,
    )


def scalar_count(db: Session, statement) -> int:
    return int(db.scalar(statement) or 0)


def normalize_provider(provider: str | None) -> str | None:
    normalized = (provider or "").strip()
    return normalized or None


def format_stats(stats: EmbeddingCleanupStats) -> str:
    mode = "execute" if stats.executed else "dry-run"
    provider = stats.provider_filter or "ALL"
    lines = [
        "embedding cleanup",
        f"mode={mode}",
        f"provider_filter={provider}",
        f"total_chunks={stats.total_chunks}",
        f"total_embeddings={stats.total_embeddings}",
        f"orphan_embeddings={stats.orphan_embeddings}",
        f"selected_embeddings={stats.selected_embeddings}",
        f"deleted_embeddings={stats.deleted_embeddings}",
        "provider_distribution:",
    ]
    if not stats.provider_counts:
        lines.append("  (empty)")
    for count in stats.provider_counts:
        lines.append(
            "  "
            f"provider={count.provider}\t"
            f"model={count.model_name}\t"
            f"dimension={count.dimension}\t"
            f"count={count.count}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect or delete rows from chunk_embeddings before rebuilding indexes."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview cleanup without deleting rows.")
    mode.add_argument("--execute", action="store_true", help="Delete selected embedding rows.")
    parser.add_argument(
        "--provider",
        default="",
        help="Optional provider filter. Omit to delete all chunk embeddings.",
    )
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        stats = cleanup_embeddings(
            db,
            provider=args.provider,
            execute=bool(args.execute),
        )

    print(format_stats(stats))


if __name__ == "__main__":
    main()
