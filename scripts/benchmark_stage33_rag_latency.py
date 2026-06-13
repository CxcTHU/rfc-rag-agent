from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.retrieval.embedding import DeterministicEmbeddingProvider, create_embedding_provider
from app.services.retrieval.vector_cache import VectorIndexCache


DEFAULT_QUERIES = [
    ("stage33_filling_capacity", "What affects filling capacity in rock-filled concrete?"),
    ("stage33_thermal_control", "How does thermal control affect rock-filled concrete dam construction?"),
]


@dataclass(frozen=True)
class BenchmarkRow:
    query_id: str
    provider: str
    model_name: str
    dimension: int
    load_mode: str
    query_embedding_latency_ms: float
    vector_search_latency_ms: float
    time_to_final_ms: float
    result_count: int


def main() -> None:
    args = parse_args()
    provider = build_provider(args)
    rows: list[BenchmarkRow] = []

    with SessionLocal() as db:
        cache = VectorIndexCache(db, provider)
        for query_id, query_text in DEFAULT_QUERIES[: args.limit]:
            started = time.perf_counter()
            embedding_started = time.perf_counter()
            query_embedding = provider.embed_query(query_text)
            query_embedding_latency_ms = elapsed_ms(embedding_started)

            search_started = time.perf_counter()
            matches = cache.search(query_embedding, top_k=args.top_k)
            vector_search_latency_ms = elapsed_ms(search_started)

            rows.append(
                BenchmarkRow(
                    query_id=query_id,
                    provider=provider.provider_name,
                    model_name=provider.model_name,
                    dimension=provider.dimension,
                    load_mode=cache.load_mode,
                    query_embedding_latency_ms=query_embedding_latency_ms,
                    vector_search_latency_ms=vector_search_latency_ms,
                    time_to_final_ms=elapsed_ms(started),
                    result_count=len(matches),
                )
            )

    write_rows(args.output, rows)
    for row in rows:
        print(
            f"{row.query_id}: provider={row.provider} model={row.model_name} "
            f"dim={row.dimension} load_mode={row.load_mode} "
            f"query_embedding={row.query_embedding_latency_ms:.2f}ms "
            f"vector_search={row.vector_search_latency_ms:.2f}ms "
            f"total={row.time_to_final_ms:.2f}ms results={row.result_count}"
        )
    print(f"wrote {args.output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark stage 33 query embedding and vector search latency.",
    )
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--dimension", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=len(DEFAULT_QUERIES))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/evaluation/stage33_rag_latency_benchmark.csv"),
    )
    return parser.parse_args()


def build_provider(args: argparse.Namespace):
    settings = get_settings()
    provider_name = args.provider or settings.embedding_provider or "deterministic"
    if provider_name.strip().casefold() in {"", "deterministic", "fake", "local"}:
        return DeterministicEmbeddingProvider(dimension=args.dimension or 64)
    return create_embedding_provider(
        provider_name=provider_name,
        model_name=args.model_name or settings.embedding_model_name,
        api_key=args.api_key or settings.embedding_api_key,
        base_url=args.base_url or settings.embedding_base_url,
        dimension=args.dimension or settings.embedding_dimension or None,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


def elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0


def write_rows(path: Path, rows: list[BenchmarkRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "query_id",
                "provider",
                "model_name",
                "dimension",
                "load_mode",
                "query_embedding_latency_ms",
                "vector_search_latency_ms",
                "time_to_final_ms",
                "result_count",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "query_id": row.query_id,
                    "provider": row.provider,
                    "model_name": row.model_name,
                    "dimension": row.dimension,
                    "load_mode": row.load_mode,
                    "query_embedding_latency_ms": f"{row.query_embedding_latency_ms:.3f}",
                    "vector_search_latency_ms": f"{row.vector_search_latency_ms:.3f}",
                    "time_to_final_ms": f"{row.time_to_final_ms:.3f}",
                    "result_count": row.result_count,
                }
            )


if __name__ == "__main__":
    main()
