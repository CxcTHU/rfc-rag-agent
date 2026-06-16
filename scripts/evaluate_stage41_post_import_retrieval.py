from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval.hybrid_rrf_tail import HybridRrfTailSearchService  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService  # noqa: E402
from app.services.retrieval.rrf_fusion import RRFHybridSearchResult, RRFHybridSearchService  # noqa: E402
from scripts.evaluate_stage29_real_quality import (  # noqa: E402
    create_stage29_embedding_provider,
    force_deterministic_reranking,
    normalize_for_match,
    sanitize_error,
    split_points,
)


QUERY_PATH = ROOT / "data" / "evaluation" / "stage41_post_import_retrieval_queries.csv"
RESULTS_PATH = ROOT / "data" / "evaluation" / "stage41_post_import_retrieval_results.csv"
SUMMARY_PATH = ROOT / "data" / "evaluation" / "stage41_post_import_retrieval_summary.csv"

RESULT_FIELDS = [
    "query_id",
    "question",
    "category",
    "expected_source_type",
    "provider",
    "model_name",
    "retrieval_mode",
    "top_k",
    "precision_at_1",
    "precision_at_3",
    "precision_at_5",
    "coverage_ratio",
    "covered_points",
    "missing_points",
    "source_type_distribution",
    "top1_source_type",
    "top1_document_title",
    "top_titles",
    "latency_ms",
    "status",
    "error",
]

SUMMARY_FIELDS = [
    "provider",
    "model_name",
    "retrieval_mode",
    "total_queries",
    "precision_at_1",
    "precision_at_3",
    "precision_at_5",
    "avg_coverage_ratio",
    "source_type_distribution",
    "decision",
    "next_action",
]


@dataclass(frozen=True)
class Stage41Query:
    query_id: str
    question: str
    category: str
    expected_source_type: str
    expected_title_terms: tuple[str, ...]
    expected_answer_points: tuple[str, ...]
    notes: str


SearchResult = HybridSearchResult | RRFHybridSearchResult


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate post-import retrieval coverage for stage 41."
    )
    parser.add_argument("--queries", default=str(QUERY_PATH))
    parser.add_argument("--out-results", default=str(RESULTS_PATH))
    parser.add_argument("--out-summary", default=str(SUMMARY_PATH))
    parser.add_argument("--provider", default="glm")
    parser.add_argument(
        "--retrieval-mode",
        choices=["hybrid", "bm25_rrf", "hybrid_rrf_tail"],
        default="hybrid_rrf_tail",
    )
    parser.add_argument("--top-k", type=int, default=8)
    return parser.parse_args()


def load_queries(path: Path) -> list[Stage41Query]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {
            "query_id",
            "question",
            "category",
            "expected_source_type",
            "expected_title_terms",
            "expected_answer_points",
            "notes",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing stage41 query fields: {', '.join(sorted(missing))}")
        return [
            Stage41Query(
                query_id=row["query_id"].strip(),
                question=row["question"].strip(),
                category=row["category"].strip(),
                expected_source_type=row["expected_source_type"].strip(),
                expected_title_terms=split_points(row["expected_title_terms"]),
                expected_answer_points=split_points(row["expected_answer_points"]),
                notes=row.get("notes", "").strip(),
            )
            for row in reader
            if row.get("query_id", "").strip()
        ]


def result_evidence(result: SearchResult) -> str:
    return " ".join(
        part
        for part in [
            result.document_title,
            result.heading_path or "",
            result.content,
        ]
        if part
    )


def result_matches_query(result: SearchResult, query: Stage41Query) -> bool:
    if query.expected_source_type != "any" and result.source_type != query.expected_source_type:
        return False
    evidence = normalize_for_match(result_evidence(result))
    expected_terms = query.expected_title_terms or query.expected_answer_points
    return any(normalize_for_match(term) in evidence for term in expected_terms)


def hit_at_k(results: list[SearchResult], query: Stage41Query, k: int) -> bool:
    return any(result_matches_query(result, query) for result in results[:k])


def coverage_ratio(results: list[SearchResult], query: Stage41Query) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
    points = query.expected_answer_points
    if not points:
        return 0.0, (), ()
    evidence = normalize_for_match(" ".join(result_evidence(result) for result in results))
    covered = tuple(point for point in points if normalize_for_match(point) in evidence)
    missing = tuple(point for point in points if normalize_for_match(point) not in evidence)
    return round(len(covered) / len(points), 3), covered, missing


def source_type_distribution(results: list[SearchResult]) -> str:
    counts = Counter(result.source_type for result in results)
    return ";".join(f"{source_type}:{count}" for source_type, count in sorted(counts.items()))


def evaluate_query(
    query: Stage41Query,
    *,
    search_service: HybridSearchService | RRFHybridSearchService,
    provider: str,
    model_name: str,
    retrieval_mode: str,
    top_k: int,
) -> dict[str, str]:
    started = time.perf_counter()
    try:
        results = search_service.search(query.question, top_k=top_k)
        coverage, covered, missing = coverage_ratio(results, query)
        top1 = results[0] if results else None
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "query_id": query.query_id,
            "question": query.question,
            "category": query.category,
            "expected_source_type": query.expected_source_type,
            "provider": provider,
            "model_name": model_name,
            "retrieval_mode": retrieval_mode,
            "top_k": str(top_k),
            "precision_at_1": str(hit_at_k(results, query, 1)).lower(),
            "precision_at_3": str(hit_at_k(results, query, min(3, top_k))).lower(),
            "precision_at_5": str(hit_at_k(results, query, min(5, top_k))).lower(),
            "coverage_ratio": f"{coverage:.3f}",
            "covered_points": ";".join(covered),
            "missing_points": ";".join(missing),
            "source_type_distribution": source_type_distribution(results),
            "top1_source_type": top1.source_type if top1 else "",
            "top1_document_title": top1.document_title[:160] if top1 else "",
            "top_titles": " || ".join(result.document_title[:80] for result in results),
            "latency_ms": f"{latency_ms:.2f}",
            "status": "completed",
            "error": "",
        }
    except Exception as exc:  # noqa: BLE001 - evaluation must record row-level errors
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "query_id": query.query_id,
            "question": query.question,
            "category": query.category,
            "expected_source_type": query.expected_source_type,
            "provider": provider,
            "model_name": model_name,
            "retrieval_mode": retrieval_mode,
            "top_k": str(top_k),
            "precision_at_1": "false",
            "precision_at_3": "false",
            "precision_at_5": "false",
            "coverage_ratio": "0.000",
            "covered_points": "",
            "missing_points": ";".join(query.expected_answer_points),
            "source_type_distribution": "",
            "top1_source_type": "",
            "top1_document_title": "",
            "top_titles": "",
            "latency_ms": f"{latency_ms:.2f}",
            "status": "error",
            "error": sanitize_error(exc),
        }


def summarize(rows: list[dict[str, str]], provider: str, model_name: str, retrieval_mode: str) -> dict[str, str]:
    source_counts: Counter[str] = Counter()
    for row in rows:
        for part in row["source_type_distribution"].split(";"):
            if not part or ":" not in part:
                continue
            source_type, count = part.split(":", 1)
            source_counts[source_type] += int(count)
    errors = [row for row in rows if row["status"] == "error"]
    p1 = ratio(count_true(rows, "precision_at_1"), len(rows))
    p3 = ratio(count_true(rows, "precision_at_3"), len(rows))
    p5 = ratio(count_true(rows, "precision_at_5"), len(rows))
    coverage = average([float(row["coverage_ratio"]) for row in rows])
    decision = "completed_with_errors" if errors else "completed"
    next_action = (
        f"{len(errors)} queries errored; inspect stage41_post_import_retrieval_results.csv"
        if errors
        else "Review low coverage cases; tune only if post-import retrieval misses persist"
    )
    return {
        "provider": provider,
        "model_name": model_name,
        "retrieval_mode": retrieval_mode,
        "total_queries": str(len(rows)),
        "precision_at_1": f"{p1:.3f}",
        "precision_at_3": f"{p3:.3f}",
        "precision_at_5": f"{p5:.3f}",
        "avg_coverage_ratio": f"{coverage:.3f}",
        "source_type_distribution": ";".join(
            f"{source_type}:{count}" for source_type, count in sorted(source_counts.items())
        ),
        "decision": decision,
        "next_action": next_action,
    }


def count_true(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if row.get(field) == "true")


def ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else numerator / denominator


def average(values: list[float]) -> float:
    return 0.0 if not values else sum(values) / len(values)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def create_search_service(db, provider, retrieval_mode: str):
    if retrieval_mode == "bm25_rrf":
        return RRFHybridSearchService(db=db, embedding_provider=provider)
    if retrieval_mode == "hybrid_rrf_tail":
        return HybridRrfTailSearchService(db=db, embedding_provider=provider)
    return HybridSearchService(db=db, embedding_provider=provider, reranking_enabled=True)


def main() -> None:
    args = parse_args()
    if args.top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    force_deterministic_reranking()
    settings = get_settings()
    provider = create_stage29_embedding_provider(args.provider, settings)
    queries = load_queries(Path(args.queries))

    init_db()
    with SessionLocal() as db:
        search_service = create_search_service(db, provider, args.retrieval_mode)
        rows = [
            evaluate_query(
                query,
                search_service=search_service,
                provider=provider.provider_name,
                model_name=provider.model_name,
                retrieval_mode=args.retrieval_mode,
                top_k=args.top_k,
            )
            for query in queries
        ]

    summary = summarize(rows, provider.provider_name, provider.model_name, args.retrieval_mode)
    write_csv(Path(args.out_results), RESULT_FIELDS, rows)
    write_csv(Path(args.out_summary), SUMMARY_FIELDS, [summary])

    print(
        "stage41 post-import retrieval "
        f"provider={provider.provider_name} model={provider.model_name} "
        f"retrieval_mode={args.retrieval_mode} "
        f"p@1={summary['precision_at_1']} p@3={summary['precision_at_3']} "
        f"p@5={summary['precision_at_5']} coverage={summary['avg_coverage_ratio']}"
    )


if __name__ == "__main__":
    main()
