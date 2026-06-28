from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository  # noqa: E402
from app.db.session import create_sqlite_engine  # noqa: E402
from app.services.agent.tools import AgentToolbox  # noqa: E402
from app.services.cache import layered_cache  # noqa: E402
from app.services.generation.chat_model import DeterministicChatModelProvider  # noqa: E402
from app.services.observability.latency_trace import (  # noqa: E402
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchService  # noqa: E402
from app.services.retrieval.reranking import ReRankResult  # noqa: E402
from app.services.retrieval.vector_index import VectorIndexService  # noqa: E402


DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "phase56_layered_cache_eval.csv"


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value.encode("utf-8")


class CountingReranker:
    provider_name = "deterministic"
    model_name = "phase56-counting-reranker"

    def __init__(self) -> None:
        self.calls = 0

    def rerank(self, query, candidates, top_k=5):
        self.calls += 1
        return [
            ReRankResult(index=index, score=float(len(candidates) - index), content=candidates[index])
            for index in range(min(top_k, len(candidates)))
        ]


def configure_cache(fake_redis: FakeRedis) -> None:
    os.environ["REDIS_URL"] = "redis://phase56-eval"
    os.environ["LAYERED_CACHE_NAMESPACE"] = "phase56-eval"
    os.environ["RETRIEVAL_CANDIDATE_CACHE_ENABLED"] = "true"
    os.environ["RERANK_ORDER_CACHE_ENABLED"] = "true"
    os.environ["TOOL_RESULT_CACHE_ENABLED"] = "true"
    get_settings.cache_clear()
    layered_cache.get_redis_client = lambda settings=None: fake_redis  # type: ignore[assignment]


def seed_fixture(db) -> None:
    repository = DocumentRepository(db)
    repository.create_with_chunks(
        DocumentCreate(
            title="Phase 56 cache evaluation fixture",
            source_type="local_file",
            source_path="phase56-cache.md",
            file_name="phase56-cache.md",
            file_extension=".md",
            content_hash="phase56-cache-eval",
            raw_path="data/raw/phase56-cache.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Rock-filled concrete filling capacity is controlled by "
                    "self-compacting concrete flowability in rock voids."
                ),
                char_count=108,
                heading_path="Filling capacity",
                start_char=0,
                end_char=108,
            )
        ],
    )
    for index in range(5):
        repository.create_with_chunks(
            DocumentCreate(
                title=f"Phase 56 dynamic evidence fixture {index + 1}",
                source_type="local_file",
                source_path=f"phase56-dynamic-{index + 1}.md",
                file_name=f"phase56-dynamic-{index + 1}.md",
                file_extension=".md",
                content_hash=f"phase56-dynamic-eval-{index + 1}",
                raw_path=f"data/raw/phase56-dynamic-{index + 1}.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content=(
                        f"Dynamic evidence candidate {index + 1} discusses "
                        "rock-filled concrete retrieval diagnostics and rerank scoring."
                    ),
                    char_count=110,
                    heading_path="Dynamic evidence",
                    start_char=0,
                    end_char=110,
                )
            ],
        )


def timed_trace(fn):
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    started = time.perf_counter()
    try:
        result = fn()
    finally:
        reset_current_latency_trace(token)
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return result, trace.values, elapsed_ms


def run_eval() -> list[dict[str, object]]:
    fake_redis = FakeRedis()
    configure_cache(fake_redis)
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_sqlite_engine(f"sqlite:///{Path(tmpdir, 'phase56.sqlite').as_posix()}")
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        try:
            with SessionLocal() as db:
                provider = DeterministicEmbeddingProvider(dimension=32)
                seed_fixture(db)
                VectorIndexService(db, provider).build_index()
                reranker = CountingReranker()
                toolbox = AgentToolbox(
                    db=db,
                    embedding_provider=provider,
                    chat_model_provider=DeterministicChatModelProvider(),
                    log_answers=False,
                )
                query = "filling capacity rock-filled concrete"

                rows: list[dict[str, object]] = []
                for run_label in ("cold", "warm"):
                    results, trace, elapsed_ms = timed_trace(
                        lambda: HybridSearchService(
                            db,
                            provider,
                            parallel=False,
                            reranking_provider=reranker,
                            reranking_enabled=True,
                        ).search(query, top_k=1)
                    )
                    rows.append(
                        result_row(
                            scenario="hybrid_search",
                            run_label=run_label,
                            elapsed_ms=elapsed_ms,
                            trace=trace,
                            source_count=len(results),
                            citation_count=0,
                            reranker_calls=reranker.calls,
                        )
                    )

                for run_label in ("cold", "warm"):
                    result, trace, elapsed_ms = timed_trace(
                        lambda: toolbox.hybrid_search_knowledge(query, top_k=1)
                    )
                    rows.append(
                        result_row(
                            scenario="tool_hybrid_search_knowledge",
                            run_label=run_label,
                            elapsed_ms=elapsed_ms,
                            trace=trace,
                            source_count=len(result.sources),
                            citation_count=len(result.citations),
                            reranker_calls=reranker.calls,
                        )
                    )

                settings = get_settings()
                original_dynamic = (
                    settings.reranking_dynamic_top_k_enabled,
                    settings.reranking_dynamic_min_results,
                    settings.reranking_dynamic_max_results,
                    settings.reranking_dynamic_relative_score_threshold,
                )
                try:
                    settings.reranking_dynamic_top_k_enabled = True
                    settings.reranking_dynamic_min_results = 4
                    settings.reranking_dynamic_max_results = 5
                    settings.reranking_dynamic_relative_score_threshold = 0.65
                    dynamic_results, dynamic_trace, dynamic_elapsed_ms = timed_trace(
                        lambda: HybridSearchService(
                            db,
                            provider,
                            parallel=False,
                            reranking_provider=CountingReranker(),
                            reranking_enabled=True,
                        ).search("dynamic evidence rock-filled concrete", top_k=1)
                    )
                finally:
                    (
                        settings.reranking_dynamic_top_k_enabled,
                        settings.reranking_dynamic_min_results,
                        settings.reranking_dynamic_max_results,
                        settings.reranking_dynamic_relative_score_threshold,
                    ) = original_dynamic
                rows.append(
                    result_row(
                        scenario="dynamic_top_k_rerank_threshold",
                        run_label="single",
                        elapsed_ms=dynamic_elapsed_ms,
                        trace=dynamic_trace,
                        source_count=len(dynamic_results),
                        citation_count=0,
                        reranker_calls=0,
                    )
                )
                return rows
        finally:
            engine.dispose()


def result_row(
    *,
    scenario: str,
    run_label: str,
    elapsed_ms: float,
    trace: dict[str, object],
    source_count: int,
    citation_count: int,
    reranker_calls: int,
) -> dict[str, object]:
    return {
        "scenario": scenario,
        "run": run_label,
        "elapsed_ms": elapsed_ms,
        "retrieval_cache_hit": trace.get("retrieval_cache_hit", False),
        "rerank_cache_hit": trace.get("rerank_cache_hit", False),
        "tool_result_cache_hit": trace.get("tool_result_cache_hit", False),
        "vector_search_backend": trace.get("vector_search_backend", "not_run"),
        "source_count": source_count,
        "citation_count": citation_count,
        "reranker_calls_cumulative": reranker_calls,
        "retrieval_query_present": bool(trace.get("retrieval_query")),
        "retrieval_candidate_count": trace.get("retrieval_candidate_count", 0),
        "retrieval_candidate_ids_present": bool(trace.get("retrieval_candidate_chunk_ids")),
        "retrieval_selected_count": trace.get("retrieval_selected_count", source_count),
        "retrieval_selected_ids_present": bool(trace.get("retrieval_selected_chunk_ids")),
        "retrieval_selected_preview_present": bool(trace.get("retrieval_selected_preview")),
        "retrieval_dynamic_top_k_enabled": trace.get("retrieval_dynamic_top_k_enabled", False),
        "retrieval_selection_reason": trace.get("retrieval_selection_reason", ""),
        "reranking_fallback": trace.get("reranking_fallback", False),
        "reranking_fallback_used": trace.get("reranking_fallback_used", False),
    }


def write_rows(rows: list[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scenario",
        "run",
        "elapsed_ms",
        "retrieval_cache_hit",
        "rerank_cache_hit",
        "tool_result_cache_hit",
        "vector_search_backend",
        "source_count",
        "citation_count",
        "reranker_calls_cumulative",
        "retrieval_query_present",
        "retrieval_candidate_count",
        "retrieval_candidate_ids_present",
        "retrieval_selected_count",
        "retrieval_selected_ids_present",
        "retrieval_selected_preview_present",
        "retrieval_dynamic_top_k_enabled",
        "retrieval_selection_reason",
        "reranking_fallback",
        "reranking_fallback_used",
    ]
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a sanitized Phase 56 cold/warm layered-cache evaluation."
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = run_eval()
    write_rows(rows, args.out)
    warm_hits = sum(
        1
        for row in rows
        if row["run"] == "warm"
        and (
            row["retrieval_cache_hit"] == True
            or row["rerank_cache_hit"] == True
            or row["tool_result_cache_hit"] == True
        )
    )
    print(f"phase56_layered_cache_eval rows={len(rows)} warm_hit_rows={warm_hits} output={args.out}")


if __name__ == "__main__":
    main()
