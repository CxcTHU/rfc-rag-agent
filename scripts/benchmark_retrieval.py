from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import statistics
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models import Chunk, ChunkEmbedding  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.agent.service import AgentService  # noqa: E402
from app.services.generation.chat_model import DeterministicChatModelProvider  # noqa: E402
from app.services.retrieval.embedding import EmbeddingProvider  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchService  # noqa: E402
from app.services.retrieval.keyword_search import KeywordSearchService  # noqa: E402
from app.services.retrieval.reranking import DeterministicReRankingProvider  # noqa: E402
from app.services.retrieval.vector_search import VectorSearchService  # noqa: E402
from scripts.evaluate_vector_search import create_embedding_provider_from_settings  # noqa: E402


DEFAULT_QUERIES = (
    "What affects filling capacity in rock-filled concrete?",
    "堆石混凝土施工质量控制有哪些要点？",
)


@dataclass(frozen=True)
class BenchmarkTiming:
    name: str
    runs: int
    min_ms: float
    mean_ms: float
    median_ms: float
    max_ms: float


@dataclass(frozen=True)
class BenchmarkResult:
    query: str
    chunk_count: int
    embedding_count: int
    provider: str
    model_name: str
    dimension: int
    timings: list[BenchmarkTiming]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark retrieval and agent latency for stage 26 performance work."
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Query to benchmark. Can be supplied multiple times.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--provider",
        default="deterministic",
        help=(
            "Embedding provider name. Defaults to deterministic so benchmark runs do not "
            "call real APIs unless explicitly requested."
        ),
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Print cProfile summary for a single hybrid search on the first query.",
    )
    args = parser.parse_args()

    settings = get_settings()
    provider = create_embedding_provider_from_settings(args.provider, settings)
    queries = tuple(args.queries or DEFAULT_QUERIES)

    init_db()
    with SessionLocal() as db:
        results = [
            benchmark_query(
                db=db,
                provider=provider,
                query=query,
                top_k=args.top_k,
                runs=args.runs,
            )
            for query in queries
        ]
        print_markdown(results)
        if args.profile and queries:
            print_profile_summary(db, provider, queries[0], top_k=args.top_k)


def benchmark_query(
    *,
    db: Session,
    provider: EmbeddingProvider,
    query: str,
    top_k: int,
    runs: int,
) -> BenchmarkResult:
    if runs <= 0:
        raise ValueError("runs must be greater than 0")
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    chunk_count = count_rows(db, Chunk)
    embedding_count = count_matching_embeddings(db, provider)
    keyword_service = KeywordSearchService(db)
    vector_service = VectorSearchService(db, provider)
    hybrid_service = HybridSearchService(db, provider)
    agent_service = AgentService(
        db=db,
        embedding_provider=provider,
        chat_model_provider=DeterministicChatModelProvider(),
        log_answers=False,
    )

    timings = [
        time_operation("query_embedding", runs, lambda: provider.embed_query(query)),
        time_operation("keyword_search", runs, lambda: keyword_service.search(query, top_k=top_k)),
        time_operation("vector_search", runs, lambda: vector_service.search(query, top_k=top_k)),
        time_operation("hybrid_search", runs, lambda: hybrid_service.search(query, top_k=top_k)),
    ]
    rerank_candidates = [
        result.content
        for result in HybridSearchService(db, provider, reranking_enabled=False).search(
            query,
            top_k=max(top_k * 5, 25),
        )
    ]
    if rerank_candidates:
        reranker = DeterministicReRankingProvider()
        timings.append(
            time_operation(
                "rerank_only",
                runs,
                lambda: reranker.rerank(query, rerank_candidates, top_k=top_k),
            )
        )
    timings.append(time_operation("agent_query", runs, lambda: agent_service.query(query, top_k=top_k)))
    return BenchmarkResult(
        query=query,
        chunk_count=chunk_count,
        embedding_count=embedding_count,
        provider=provider.provider_name,
        model_name=provider.model_name,
        dimension=provider.dimension,
        timings=timings,
    )


def time_operation(name: str, runs: int, operation: Callable[[], Any]) -> BenchmarkTiming:
    if runs <= 0:
        raise ValueError("runs must be greater than 0")

    durations: list[float] = []
    for _index in range(runs):
        started = time.perf_counter()
        operation()
        durations.append((time.perf_counter() - started) * 1000.0)
    return BenchmarkTiming(
        name=name,
        runs=runs,
        min_ms=min(durations),
        mean_ms=statistics.fmean(durations),
        median_ms=statistics.median(durations),
        max_ms=max(durations),
    )


def count_rows(db: Session, model: type) -> int:
    return int(db.execute(select(func.count()).select_from(model)).scalar_one())


def count_matching_embeddings(db: Session, provider: EmbeddingProvider) -> int:
    statement = (
        select(func.count())
        .select_from(ChunkEmbedding)
        .where(
            ChunkEmbedding.provider == provider.provider_name,
            ChunkEmbedding.model_name == provider.model_name,
            ChunkEmbedding.dimension == provider.dimension,
        )
    )
    return int(db.execute(statement).scalar_one())


def print_markdown(results: Iterable[BenchmarkResult]) -> None:
    print("| query | chunks | embeddings | provider | operation | runs | min_ms | mean_ms | median_ms | max_ms |")
    print("| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for result in results:
        provider_label = f"{result.provider}/{result.model_name}/dim={result.dimension}"
        for timing in result.timings:
            print(
                "| "
                f"{escape_table_cell(result.query)} | "
                f"{result.chunk_count} | "
                f"{result.embedding_count} | "
                f"{escape_table_cell(provider_label)} | "
                f"{timing.name} | "
                f"{timing.runs} | "
                f"{timing.min_ms:.2f} | "
                f"{timing.mean_ms:.2f} | "
                f"{timing.median_ms:.2f} | "
                f"{timing.max_ms:.2f} |"
            )


def escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def print_profile_summary(
    db: Session,
    provider: EmbeddingProvider,
    query: str,
    *,
    top_k: int,
) -> None:
    profiler = cProfile.Profile()
    service = HybridSearchService(db, provider)
    profiler.enable()
    service.search(query, top_k=top_k)
    profiler.disable()

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumtime")
    stats.print_stats(25)
    print("\n## cProfile hybrid_search")
    print(stream.getvalue())


if __name__ == "__main__":
    main()
