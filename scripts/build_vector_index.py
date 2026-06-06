from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from app.services.retrieval.vector_index import VectorIndexService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build chunk embeddings for vector search.")
    parser.add_argument("--provider", default="", help="Embedding provider name. Defaults to .env EMBEDDING_PROVIDER or deterministic.")
    parser.add_argument("--model-name", default="", help="Embedding model name. Defaults to .env EMBEDDING_MODEL_NAME.")
    parser.add_argument("--api-key", default="", help="Embedding API key. Defaults to .env EMBEDDING_API_KEY.")
    parser.add_argument("--base-url", default="", help="Embedding base URL. Defaults to .env EMBEDDING_BASE_URL.")
    parser.add_argument("--dimension", type=int, default=0, help="Embedding vector dimension. Defaults to .env EMBEDDING_DIMENSION.")
    parser.add_argument("--timeout-seconds", type=float, default=0, help="Embedding request timeout. Defaults to .env EMBEDDING_TIMEOUT_SECONDS.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum chunks to inspect. 0 means all chunks.")
    parser.add_argument("--batch-size", type=int, default=32, help="Number of chunks embedded per provider call.")
    args = parser.parse_args()

    settings = get_settings()
    provider = build_embedding_provider_from_args(args, settings)

    init_db()
    with SessionLocal() as db:
        result = VectorIndexService(db, provider).build_index(
            limit=args.limit or None,
            batch_size=args.batch_size,
        )

    print(
        "vector index built\t"
        f"provider={result.provider}\t"
        f"model={result.model_name}\t"
        f"dimension={result.dimension}\t"
        "content_hash=tracked\t"
        f"total={result.total_chunks}\t"
        f"indexed={result.indexed_chunks}\t"
        f"updated={result.updated_chunks}\t"
        f"skipped={result.skipped_chunks}"
    )


def build_embedding_provider_from_args(args: argparse.Namespace, settings):
    provider_name = args.provider or settings.embedding_provider or "deterministic"
    dimension = args.dimension or settings.embedding_dimension or None
    timeout_seconds = args.timeout_seconds or settings.embedding_timeout_seconds
    return create_embedding_provider(
        provider_name=provider_name,
        model_name=args.model_name or settings.embedding_model_name,
        api_key=args.api_key or settings.embedding_api_key,
        base_url=args.base_url or settings.embedding_base_url,
        dimension=dimension,
        timeout_seconds=timeout_seconds,
    )


if __name__ == "__main__":
    main()
