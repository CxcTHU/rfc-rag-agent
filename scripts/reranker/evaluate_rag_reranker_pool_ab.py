"""Evaluate remote BGE reranker candidate-pool and final top-k settings.

This follow-up reuses the Stage 3 RAG query set and relevance labels. It does
not create a new evaluation set and does not serialize full candidate text.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchService  # noqa: E402
from scripts.evaluate_stage29_real_quality import create_stage29_embedding_provider  # noqa: E402
from scripts.reranker import evaluate_rag_reranker_ab as stage3_ab  # noqa: E402

DEFAULT_OUTPUT_DIR = ROOT / "data" / "evaluation"
RESULTS_NAME = "stage3_reranker_pool_ab_results.csv"
SUMMARY_NAME = "stage3_reranker_pool_ab_summary.csv"
DEFAULT_COMBOS = [(25, 5), (50, 5), (50, 8), (75, 8), (100, 10)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate remote BGE pool/top-k ablations.")
    parser.add_argument("--queries", type=Path, nargs="+", default=stage3_ab.DEFAULT_DATASETS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--provider", default="deterministic", help="Embedding provider used for candidate recall.")
    parser.add_argument("--combo", action="append", default=[], help="Pool/top-k pair, for example 50:8.")
    parser.add_argument("--limit", type=int, default=0, help="Optional query limit for smoke runs.")
    parser.add_argument("--include-phase51-cases", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--remote-bge-url", required=True)
    parser.add_argument("--remote-bge-api-key", default="")
    parser.add_argument("--remote-bge-model", default=stage3_ab.DEFAULT_REMOTE_BGE_MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = evaluate_pool_ab(
        query_paths=args.queries,
        output_dir=args.output_dir,
        provider_name=args.provider,
        combos=parse_combos(args.combo),
        limit=args.limit,
        include_phase51_cases=args.include_phase51_cases,
        remote_bge_url=args.remote_bge_url,
        remote_bge_api_key=args.remote_bge_api_key,
        remote_bge_model=args.remote_bge_model,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_combos(raw_combos: list[str]) -> list[tuple[int, int]]:
    if not raw_combos:
        return list(DEFAULT_COMBOS)
    combos: list[tuple[int, int]] = []
    for raw_combo in raw_combos:
        if ":" not in raw_combo:
            raise ValueError(f"combo must use pool:top_k format: {raw_combo}")
        pool_raw, top_raw = raw_combo.split(":", 1)
        pool_size = int(pool_raw)
        top_k = int(top_raw)
        validate_combo(pool_size, top_k)
        combos.append((pool_size, top_k))
    return combos


def validate_combo(candidate_pool_size: int, top_k: int) -> None:
    if candidate_pool_size <= 0:
        raise ValueError("candidate_pool_size must be greater than 0")
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")
    if top_k > candidate_pool_size:
        raise ValueError("top_k must not exceed candidate_pool_size")


def evaluate_pool_ab(
    *,
    query_paths: list[Path],
    output_dir: Path,
    provider_name: str,
    combos: list[tuple[int, int]],
    limit: int = 0,
    include_phase51_cases: bool = True,
    remote_bge_url: str,
    remote_bge_api_key: str = "",
    remote_bge_model: str = stage3_ab.DEFAULT_REMOTE_BGE_MODEL,
) -> dict[str, Any]:
    if limit < 0:
        raise ValueError("limit must be greater than or equal to 0")
    for candidate_pool_size, top_k in combos:
        validate_combo(candidate_pool_size, top_k)

    queries = stage3_ab.load_queries(query_paths, include_phase51_cases=include_phase51_cases)
    if limit:
        queries = queries[:limit]
    reranker = stage3_ab.build_rerankers(
        ["remote-bge-lora"],
        execute_glm=False,
        remote_bge_url=remote_bge_url,
        remote_bge_api_key=remote_bge_api_key,
        remote_bge_model=remote_bge_model,
    )[0]

    output_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    embedding_provider = create_stage29_embedding_provider(provider_name, settings)
    result_rows: list[dict[str, Any]] = []

    init_db()
    with SessionLocal() as db:
        search_service = HybridSearchService(
            db=db,
            embedding_provider=embedding_provider,
            reranking_enabled=False,
        )
        for candidate_pool_size, top_k in combos:
            combo_rows: list[dict[str, Any]] = []
            for query in queries:
                candidates = stage3_ab.freeze_candidates(search_service, query, candidate_pool_size)
                combo_rows.append(
                    evaluate_one_combo(
                        query=query,
                        reranker=reranker,
                        candidates=candidates,
                        candidate_pool_size=candidate_pool_size,
                        top_k=top_k,
                    )
                )
            result_rows.extend(combo_rows)
            write_results_csv(output_dir / RESULTS_NAME, result_rows)
            write_summary_csv(output_dir / SUMMARY_NAME, summarize_pool_results(result_rows))
            print(
                json.dumps(
                    {
                        "combo": combo_id(candidate_pool_size, top_k),
                        "completed": sum(1 for row in combo_rows if row["status"] == "completed"),
                        "errors": sum(1 for row in combo_rows if row["status"] != "completed"),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    summary_rows = summarize_pool_results(result_rows)
    write_results_csv(output_dir / RESULTS_NAME, result_rows)
    write_summary_csv(output_dir / SUMMARY_NAME, summary_rows)
    return {"combos": summary_rows}


def evaluate_one_combo(
    *,
    query: stage3_ab.EvalQuery,
    reranker: stage3_ab.RagReranker,
    candidates: list[stage3_ab.Candidate],
    candidate_pool_size: int,
    top_k: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        ranking = reranker.rerank(query.question, candidates)
        latency_ms = (time.perf_counter() - started) * 1000.0
        metrics = compute_pool_metrics(ranking=ranking, candidates=candidates, query=query, top_k=top_k)
        return {
            "combo": combo_id(candidate_pool_size, top_k),
            "candidate_pool_size": candidate_pool_size,
            "top_k": top_k,
            "query_id": query.query_id,
            "dataset": query.dataset,
            "category": query.category,
            "reranker": reranker.name,
            "candidate_count": len(candidates),
            "relevant_count": sum(1 for candidate in candidates if candidate.relevant),
            **metrics,
            "latency_ms": round(latency_ms, 3),
            "top_chunk_id": candidates[ranking[0].original_index].chunk_id if ranking else "",
            "top_title": candidates[ranking[0].original_index].document_title[:160] if ranking else "",
            "status": "completed",
            "error": "",
            "fallback_count": 0,
        }
    except Exception as exc:  # noqa: BLE001 - row-level eval errors are summarized
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "combo": combo_id(candidate_pool_size, top_k),
            "candidate_pool_size": candidate_pool_size,
            "top_k": top_k,
            "query_id": query.query_id,
            "dataset": query.dataset,
            "category": query.category,
            "reranker": reranker.name,
            "candidate_count": len(candidates),
            "relevant_count": sum(1 for candidate in candidates if candidate.relevant),
            **zero_metrics(),
            "latency_ms": round(latency_ms, 3),
            "top_chunk_id": "",
            "top_title": "",
            "status": "error",
            "error": stage3_ab.sanitize_error(str(exc)),
            "fallback_count": 0,
        }


def compute_pool_metrics(
    *,
    ranking: list[stage3_ab.RankedCandidate],
    candidates: list[stage3_ab.Candidate],
    query: stage3_ab.EvalQuery,
    top_k: int,
) -> dict[str, float]:
    delivered = ranking[:top_k]
    non_refusal = not query.expected_refused
    first_relevant_at_5 = first_relevant_rank(ranking, 5)
    metrics = {
        "mrr_at_5": round((1.0 / first_relevant_at_5) if first_relevant_at_5 else 0.0, 6),
        "ndcg_at_5": ndcg_at(ranking, 5),
        "precision_at_1": hit_at(ranking, 1),
        "precision_at_5": hit_at(ranking, 5),
        "ndcg_at_8": ndcg_at(ranking, 8) if top_k >= 8 else 0.0,
        "precision_at_8": hit_at(ranking, 8) if top_k >= 8 else 0.0,
        "ndcg_at_10": ndcg_at(ranking, 10) if top_k >= 10 else 0.0,
        "precision_at_10": hit_at(ranking, 10) if top_k >= 10 else 0.0,
        "coverage_ratio": stage3_ab.coverage_ratio(
            [candidates[item.original_index] for item in delivered],
            query,
        ),
        "refusal_accuracy": 1.0 if query.expected_refused and not any(item.relevant for item in delivered) else 0.0,
        "candidate_recall_hit": 1.0 if non_refusal and any(candidate.relevant for candidate in candidates) else 0.0,
        "non_refusal_query": 1.0 if non_refusal else 0.0,
    }
    return metrics


def zero_metrics() -> dict[str, float]:
    return {
        "mrr_at_5": 0.0,
        "ndcg_at_5": 0.0,
        "precision_at_1": 0.0,
        "precision_at_5": 0.0,
        "ndcg_at_8": 0.0,
        "precision_at_8": 0.0,
        "ndcg_at_10": 0.0,
        "precision_at_10": 0.0,
        "coverage_ratio": 0.0,
        "refusal_accuracy": 0.0,
        "candidate_recall_hit": 0.0,
        "non_refusal_query": 0.0,
    }


def first_relevant_rank(ranking: list[stage3_ab.RankedCandidate], k: int) -> int | None:
    for index, item in enumerate(ranking[:k], start=1):
        if item.relevant:
            return index
    return None


def ndcg_at(ranking: list[stage3_ab.RankedCandidate], k: int) -> float:
    if not ranking or k <= 0:
        return 0.0
    top_items = ranking[:k]
    dcg = sum((2**int(item.relevant) - 1) / math.log2(index + 2) for index, item in enumerate(top_items))
    ideal_labels = sorted((item.relevant for item in ranking), reverse=True)[:k]
    ideal_dcg = sum((2**int(label) - 1) / math.log2(index + 2) for index, label in enumerate(ideal_labels))
    return round((dcg / ideal_dcg) if ideal_dcg else 0.0, 6)


def hit_at(ranking: list[stage3_ab.RankedCandidate], k: int) -> float:
    if not ranking or k <= 0:
        return 0.0
    return 1.0 if any(item.relevant for item in ranking[:k]) else 0.0


def summarize_pool_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary_rows: list[dict[str, Any]] = []
    for combo in sorted({str(row["combo"]) for row in rows}, key=combo_sort_key):
        combo_rows = [row for row in rows if row["combo"] == combo]
        completed = [row for row in combo_rows if row["status"] == "completed"]
        latencies = sorted(float(row["latency_ms"]) for row in completed)
        non_refusal_completed = [row for row in completed if float(row["non_refusal_query"]) > 0.0]
        candidate_pool_size = int(combo_rows[0]["candidate_pool_size"]) if combo_rows else 0
        top_k = int(combo_rows[0]["top_k"]) if combo_rows else 0
        summary_rows.append(
            {
                "combo": combo,
                "candidate_pool_size": candidate_pool_size,
                "top_k": top_k,
                "reranker": "remote-bge-lora",
                "queries": len(combo_rows),
                "completed": len(completed),
                "error_count": len(combo_rows) - len(completed),
                "fallback_count": sum(int(row.get("fallback_count", 0)) for row in combo_rows),
                "mrr_at_5": average(completed, "mrr_at_5"),
                "ndcg_at_5": average(completed, "ndcg_at_5"),
                "precision_at_1": average(completed, "precision_at_1"),
                "precision_at_5": average(completed, "precision_at_5"),
                "ndcg_at_8": average(completed, "ndcg_at_8"),
                "precision_at_8": average(completed, "precision_at_8"),
                "ndcg_at_10": average(completed, "ndcg_at_10"),
                "precision_at_10": average(completed, "precision_at_10"),
                "coverage_ratio": average(completed, "coverage_ratio"),
                "recall_at_candidate_pool": average(non_refusal_completed, "candidate_recall_hit"),
                "avg_latency_ms": average(completed, "latency_ms"),
                "p95_latency_ms": percentile(latencies, 0.95),
            }
        )
    return summary_rows


def combo_sort_key(combo: str) -> tuple[int, int]:
    pool_raw, top_raw = combo.removeprefix("pool").split("_top")
    return int(pool_raw), int(top_raw)


def combo_id(candidate_pool_size: int, top_k: int) -> str:
    return f"pool{candidate_pool_size}_top{top_k}"


def average(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(float(row[key]) for row in rows) / len(rows), 6)


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, math.ceil(len(values) * quantile) - 1)
    return round(values[index], 3)


def write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(result_fieldnames())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(summary_fieldnames())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def result_fieldnames() -> Iterable[str]:
    return [
        "combo",
        "candidate_pool_size",
        "top_k",
        "query_id",
        "dataset",
        "category",
        "reranker",
        "candidate_count",
        "relevant_count",
        "mrr_at_5",
        "ndcg_at_5",
        "precision_at_1",
        "precision_at_5",
        "ndcg_at_8",
        "precision_at_8",
        "ndcg_at_10",
        "precision_at_10",
        "coverage_ratio",
        "refusal_accuracy",
        "candidate_recall_hit",
        "non_refusal_query",
        "latency_ms",
        "top_chunk_id",
        "top_title",
        "status",
        "error",
        "fallback_count",
    ]


def summary_fieldnames() -> Iterable[str]:
    return [
        "combo",
        "candidate_pool_size",
        "top_k",
        "reranker",
        "queries",
        "completed",
        "error_count",
        "fallback_count",
        "mrr_at_5",
        "ndcg_at_5",
        "precision_at_1",
        "precision_at_5",
        "ndcg_at_8",
        "precision_at_8",
        "ndcg_at_10",
        "precision_at_10",
        "coverage_ratio",
        "recall_at_candidate_pool",
        "avg_latency_ms",
        "p95_latency_ms",
    ]


if __name__ == "__main__":
    main()
