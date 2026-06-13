from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import aliased

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.models import Chunk, ChunkEmbedding  # noqa: E402
from app.db.repositories import deserialize_embedding  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval.faiss_index import (  # noqa: E402
    FaissVectorIndex,
    default_faiss_paths,
)
from app.services.retrieval.vector_index import calculate_text_hash  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local FAISS index from chunk_embeddings.")
    parser.add_argument("--provider", default="jina", help="Embedding provider to index.")
    parser.add_argument("--model-name", default="", help="Embedding model name.")
    parser.add_argument("--dimension", type=int, default=0, help="Embedding dimension.")
    parser.add_argument("--output-dir", default="data/faiss", help="Directory for .index and ids metadata files.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum embeddings to index. 0 means all.")
    args = parser.parse_args()

    if args.limit < 0:
        raise ValueError("limit must be greater than or equal to 0")

    settings = get_settings()
    provider = args.provider or settings.embedding_provider or "jina"
    model_name = args.model_name or settings.embedding_model_name
    dimension = args.dimension or settings.embedding_dimension
    if not model_name:
        raise ValueError("model_name must be provided with --model-name or EMBEDDING_MODEL_NAME")
    if not dimension:
        raise ValueError("dimension must be provided with --dimension or EMBEDDING_DIMENSION")

    init_db()
    with SessionLocal() as db:
        chunk_ids, embeddings = list_current_embeddings(
            db=db,
            provider=provider,
            model_name=model_name,
            dimension=dimension,
            limit=args.limit or None,
        )

    index = FaissVectorIndex.build(
        embeddings=embeddings,
        chunk_ids=chunk_ids,
        provider=provider,
        model_name=model_name,
        dimension=dimension,
        complete=args.limit == 0,
    )
    index_path, metadata_path = default_faiss_paths(
        Path(args.output_dir),
        provider=provider,
        model_name=model_name,
        dimension=dimension,
    )
    index.save(index_path=index_path, metadata_path=metadata_path)

    print(
        "faiss index built\t"
        f"provider={provider}\t"
        f"model={model_name}\t"
        f"dimension={dimension}\t"
        f"vectors={len(chunk_ids)}\t"
        f"index={index_path}\t"
        f"metadata={metadata_path}"
    )


def list_current_embeddings(
    db,
    provider: str,
    model_name: str,
    dimension: int,
    limit: int | None = None,
) -> tuple[list[int], list[list[float]]]:
    child_chunk = aliased(Chunk)
    has_children = select(child_chunk.id).where(child_chunk.parent_chunk_id == Chunk.id).exists()
    statement = (
        select(ChunkEmbedding, Chunk)
        .join(Chunk, ChunkEmbedding.chunk_id == Chunk.id)
        .where(
            ChunkEmbedding.provider == provider,
            ChunkEmbedding.model_name == model_name,
            ChunkEmbedding.dimension == dimension,
            ~has_children,
        )
        .order_by(ChunkEmbedding.id)
    )
    if limit is not None:
        statement = statement.limit(limit)

    chunk_ids: list[int] = []
    embeddings: list[list[float]] = []
    for chunk_embedding, chunk in db.execute(statement).all():
        if chunk_embedding.content_hash != calculate_text_hash(chunk.content):
            continue
        embedding = deserialize_embedding(chunk_embedding.embedding_json)
        if len(embedding) != dimension:
            continue
        chunk_ids.append(chunk.id)
        embeddings.append(embedding)
    return chunk_ids, embeddings


if __name__ == "__main__":
    main()
