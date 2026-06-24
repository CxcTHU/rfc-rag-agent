"""Evaluate RAG rerankers on a frozen candidate pool.

Default execution is local-only and compares ``none`` with ``deterministic``.
GLM reranking requires ``--execute-glm``. Remote BGE LoRA requires an explicit
``--remote-bge-url`` and never loads BGE locally.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService  # noqa: E402
from app.services.retrieval.reranking import (  # noqa: E402
    DeterministicReRankingProvider,
    OpenAICompatibleReRankingProvider,
    ReRankResult,
    create_reranking_provider,
)
from scripts.evaluate_stage29_real_quality import (  # noqa: E402
    create_stage29_embedding_provider,
    normalize_for_match,
    split_points,
)

DEFAULT_DATASETS = [
    ROOT / "data" / "evaluation" / "stage29_new_corpus_queries.csv",
    ROOT / "data" / "evaluation" / "stage41_post_import_retrieval_queries.csv",
]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "evaluation"
RESULTS_NAME = "stage3_reranker_ab_results.csv"
SUMMARY_NAME = "stage3_reranker_ab_summary.csv"
SNAPSHOT_NAME = "stage3_reranker_candidate_snapshot.jsonl"
DEFAULT_RERANKERS = ["none", "deterministic"]
DEFAULT_REMOTE_BGE_MODEL = "bge-reranker-base-rfc-lora"
PHASE51_CASE_SOURCE = "phase51_performance_cases"


@dataclass(frozen=True)
class EvalQuery:
    query_id: str
    question: str
    dataset: str
    category: str
    expected_source_type: str
    expected_terms: tuple[str, ...]
    expected_refused: bool = False


@dataclass(frozen=True)
class Candidate:
    index: int
    chunk_id: int
    document_title: str
    source_type: str
    content: str
    score: float
    relevant: bool


@dataclass(frozen=True)
class RankedCandidate:
    original_index: int
    score: float
    relevant: bool


class RagReranker(Protocol):
    name: str

    def rerank(self, query: str, candidates: list[Candidate]) -> list[RankedCandidate]:
        """Rank the frozen candidates."""


@dataclass(frozen=True)
class NoneRagReranker:
    name: str = "none"

    def rerank(self, query: str, candidates: list[Candidate]) -> list[RankedCandidate]:
        return [
            RankedCandidate(original_index=candidate.index, score=candidate.score, relevant=candidate.relevant)
            for candidate in candidates
        ]


@dataclass(frozen=True)
class ProviderRagReranker:
    name: str
    provider: Any

    def rerank(self, query: str, candidates: list[Candidate]) -> list[RankedCandidate]:
        results = self.provider.rerank(
            query,
            [candidate.content for candidate in candidates],
            top_k=len(candidates),
        )
        return convert_rerank_results(results, candidates)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate RAG reranker A/B on frozen candidates.")
    parser.add_argument("--queries", type=Path, nargs="+", default=DEFAULT_DATASETS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--rerankers", nargs="+", default=list(DEFAULT_RERANKERS))
    parser.add_argument("--provider", default="deterministic", help="Embedding provider used for candidate recall.")
    parser.add_argument("--candidate-pool-size", type=int, default=25)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0, help="Optional query limit for smoke runs.")
    parser.add_argument("--include-phase51-cases", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--execute-glm", action="store_true")
    parser.add_argument("--remote-bge-url", default="")
    parser.add_argument("--remote-bge-api-key", default="")
    parser.add_argument("--remote-bge-model", default=DEFAULT_REMOTE_BGE_MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = evaluate_rag_reranker_ab(
        query_paths=args.queries,
        output_dir=args.output_dir,
        reranker_names=args.rerankers,
        provider_name=args.provider,
        candidate_pool_size=args.candidate_pool_size,
        top_k=args.top_k,
        limit=args.limit,
        include_phase51_cases=args.include_phase51_cases,
        execute_glm=args.execute_glm,
        remote_bge_url=args.remote_bge_url,
        remote_bge_api_key=args.remote_bge_api_key,
        remote_bge_model=args.remote_bge_model,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def evaluate_rag_reranker_ab(
    *,
    query_paths: list[Path],
    output_dir: Path,
    reranker_names: list[str],
    provider_name: str = "deterministic",
    candidate_pool_size: int = 25,
    top_k: int = 5,
    limit: int = 0,
    include_phase51_cases: bool = True,
    execute_glm: bool = False,
    remote_bge_url: str = "",
    remote_bge_api_key: str = "",
    remote_bge_model: str = DEFAULT_REMOTE_BGE_MODEL,
) -> dict[str, Any]:
    if candidate_pool_size <= 0:
        raise ValueError("candidate_pool_size must be greater than 0")
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")
    if top_k > candidate_pool_size:
        raise ValueError("top_k must not exceed candidate_pool_size")
    if limit < 0:
        raise ValueError("limit must be greater than or equal to 0")

    queries = load_queries(query_paths, include_phase51_cases=include_phase51_cases)
    if limit:
        queries = queries[:limit]
    rerankers = build_rerankers(
        reranker_names,
        execute_glm=execute_glm,
        remote_bge_url=remote_bge_url,
        remote_bge_api_key=remote_bge_api_key,
        remote_bge_model=remote_bge_model,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    embedding_provider = create_stage29_embedding_provider(provider_name, settings)

    result_rows: list[dict[str, Any]] = []
    snapshot_rows: list[dict[str, Any]] = []
    init_db()
    with SessionLocal() as db:
        search_service = HybridSearchService(
            db=db,
            embedding_provider=embedding_provider,
            reranking_enabled=False,
        )
        for query in queries:
            candidates = freeze_candidates(search_service, query, candidate_pool_size)
            snapshot_rows.extend(snapshot_candidates(query, candidates))
            for reranker in rerankers:
                result_rows.append(
                    evaluate_one_reranker(
                        query=query,
                        candidates=candidates,
                        reranker=reranker,
                        top_k=top_k,
                    )
                )

    write_results_csv(output_dir / RESULTS_NAME, result_rows)
    write_snapshot_jsonl(output_dir / SNAPSHOT_NAME, snapshot_rows)
    summary = summarize_results(result_rows)
    write_summary_csv(output_dir / SUMMARY_NAME, summary)
    return summary


def build_rerankers(
    names: list[str],
    *,
    execute_glm: bool,
    remote_bge_url: str,
    remote_bge_api_key: str,
    remote_bge_model: str,
) -> list[RagReranker]:
    rerankers: list[RagReranker] = []
    for raw_name in names:
        name = raw_name.strip().casefold()
        if name == "none":
            rerankers.append(NoneRagReranker())
        elif name == "deterministic":
            rerankers.append(ProviderRagReranker("deterministic", DeterministicReRankingProvider()))
        elif name in {"glm-reranker", "glm-rerank"}:
            if not execute_glm:
                raise ValueError("glm-reranker requires --execute-glm")
            settings = get_settings()
            provider = create_reranking_provider(
                provider_name=settings.reranking_provider,
                model_name=settings.reranking_model_name,
                api_key=settings.reranking_api_key,
                base_url=settings.reranking_base_url,
                timeout_seconds=settings.reranking_timeout_seconds,
            )
            if provider is None:
                raise ValueError("glm-reranker provider is disabled")
            rerankers.append(ProviderRagReranker("glm-reranker", provider))
        elif name == "remote-bge-lora":
            if not remote_bge_url.strip():
                raise ValueError("remote-bge-lora requires --remote-bge-url")
            provider = OpenAICompatibleReRankingProvider(
                model_name=remote_bge_model,
                api_key=remote_bge_api_key,
                base_url=remote_bge_url,
                timeout_seconds=get_settings().reranking_timeout_seconds,
                provider_name="remote-bge-lora",
            )
            rerankers.append(ProviderRagReranker("remote-bge-lora", provider))
        else:
            raise ValueError(f"unsupported reranker: {raw_name}")
    return rerankers


def load_queries(paths: list[Path], *, include_phase51_cases: bool = True) -> list[EvalQuery]:
    queries: list[EvalQuery] = []
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                query_id = (row.get("query_id") or "").strip()
                question = (row.get("question") or "").strip()
                if not query_id or not question:
                    continue
                title_terms = split_points(row.get("expected_title_terms", ""))
                answer_points = split_points(row.get("expected_answer_points", ""))
                queries.append(
                    EvalQuery(
                        query_id=query_id,
                        question=question,
                        dataset=path.stem,
                        category=(row.get("category") or "").strip(),
                        expected_source_type=(row.get("expected_source_type") or "any").strip() or "any",
                        expected_terms=title_terms or answer_points,
                        expected_refused=parse_bool(row.get("expected_refused", "")),
                    )
                )
    if include_phase51_cases:
        queries.extend(load_phase51_cases())
    if not queries:
        raise ValueError("no evaluation queries loaded")
    return queries


def load_phase51_cases() -> list[EvalQuery]:
    from scripts.evaluate_phase51_performance import EVAL_CASES

    return [
        EvalQuery(
            query_id=case.query_id,
            question=case.question,
            dataset=PHASE51_CASE_SOURCE,
            category=case.category,
            expected_source_type="any",
            expected_terms=phase51_expected_terms(case.question, case.category),
            expected_refused="refusal" in case.category or "insufficient" in case.category,
        )
        for case in EVAL_CASES
    ]


def phase51_expected_terms(question: str, category: str) -> tuple[str, ...]:
    normalized = f"{question} {category}".casefold()
    if "off_topic" in normalized:
        return ()
    terms: list[str] = []
    if "filling" in normalized or "flowability" in normalized:
        terms.append("filling")
    if "thermal" in normalized or "heat" in normalized:
        terms.append("thermal")
    if "durability" in normalized:
        terms.append("durability")
    if "rock-filled" in normalized or "堆石混凝土" in normalized:
        terms.append("rock-filled concrete")
    if "aggregate" in normalized:
        terms.append("aggregate")
    if "standard" in normalized or "clause" in normalized:
        terms.append("standard")
    return tuple(dict.fromkeys(terms or ["concrete"]))


def freeze_candidates(
    search_service: HybridSearchService,
    query: EvalQuery,
    candidate_pool_size: int,
) -> list[Candidate]:
    results = search_service.search(query.question, top_k=candidate_pool_size)
    candidates = [
        Candidate(
            index=index,
            chunk_id=result.chunk_id,
            document_title=result.document_title,
            source_type=result.source_type,
            content=result.content,
            score=result.score,
            relevant=result_matches_query(result, query),
        )
        for index, result in enumerate(results)
    ]
    if not candidates:
        raise ValueError(f"no candidates returned for query_id={query.query_id}")
    return candidates


def evaluate_one_reranker(
    *,
    query: EvalQuery,
    candidates: list[Candidate],
    reranker: RagReranker,
    top_k: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        ranking = reranker.rerank(query.question, candidates)
        latency_ms = (time.perf_counter() - started) * 1000.0
        metrics = compute_metrics(ranking, candidates, query, k=top_k)
        return {
            "query_id": query.query_id,
            "dataset": query.dataset,
            "category": query.category,
            "reranker": reranker.name,
            "candidate_count": len(candidates),
            "relevant_count": sum(1 for candidate in candidates if candidate.relevant),
            "mrr_at_5": metrics["mrr_at_5"],
            "ndcg_at_5": metrics["ndcg_at_5"],
            "precision_at_1": metrics["precision_at_1"],
            "precision_at_3": metrics["precision_at_3"],
            "precision_at_5": metrics["precision_at_5"],
            "coverage_ratio": metrics["coverage_ratio"],
            "refusal_accuracy": metrics["refusal_accuracy"],
            "latency_ms": round(latency_ms, 3),
            "top_chunk_id": candidates[ranking[0].original_index].chunk_id if ranking else "",
            "top_title": candidates[ranking[0].original_index].document_title[:160] if ranking else "",
            "status": "completed",
            "error": "",
            "fallback_count": 0,
        }
    except Exception as exc:  # noqa: BLE001 - row-level eval errors are recorded
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "query_id": query.query_id,
            "dataset": query.dataset,
            "category": query.category,
            "reranker": reranker.name,
            "candidate_count": len(candidates),
            "relevant_count": sum(1 for candidate in candidates if candidate.relevant),
            "mrr_at_5": 0.0,
            "ndcg_at_5": 0.0,
            "precision_at_1": 0.0,
            "precision_at_3": 0.0,
            "precision_at_5": 0.0,
            "coverage_ratio": 0.0,
            "refusal_accuracy": 0.0,
            "latency_ms": round(latency_ms, 3),
            "top_chunk_id": "",
            "top_title": "",
            "status": "error",
            "error": sanitize_error(str(exc)),
            "fallback_count": 0,
        }


def convert_rerank_results(results: list[ReRankResult], candidates: list[Candidate]) -> list[RankedCandidate]:
    return [
        RankedCandidate(
            original_index=result.index,
            score=result.score,
            relevant=candidates[result.index].relevant,
        )
        for result in results
    ]


def result_matches_query(result: HybridSearchResult, query: EvalQuery) -> bool:
    if query.expected_refused:
        return False
    if query.expected_source_type != "any" and result.source_type != query.expected_source_type:
        return False
    evidence = normalize_for_match(" ".join([result.document_title, result.heading_path or "", result.content]))
    return any(normalize_for_match(term) in evidence for term in query.expected_terms)


def compute_metrics(
    ranking: list[RankedCandidate],
    candidates: list[Candidate],
    query: EvalQuery,
    *,
    k: int,
) -> dict[str, float]:
    top_k = ranking[:k]
    first_relevant_rank = next((index + 1 for index, item in enumerate(top_k) if item.relevant), None)
    dcg = sum((2**int(item.relevant) - 1) / math.log2(index + 2) for index, item in enumerate(top_k))
    ideal_labels = sorted((item.relevant for item in ranking), reverse=True)[:k]
    ideal_dcg = sum((2**int(label) - 1) / math.log2(index + 2) for index, label in enumerate(ideal_labels))
    coverage = coverage_ratio([candidates[item.original_index] for item in top_k], query)
    return {
        "mrr_at_5": round((1.0 / first_relevant_rank) if first_relevant_rank else 0.0, 6),
        "ndcg_at_5": round((dcg / ideal_dcg) if ideal_dcg else 0.0, 6),
        "precision_at_1": precision_at(ranking, 1),
        "precision_at_3": precision_at(ranking, min(3, k)),
        "precision_at_5": precision_at(ranking, min(5, k)),
        "coverage_ratio": coverage,
        "refusal_accuracy": 1.0 if query.expected_refused and not any(item.relevant for item in top_k) else 0.0,
    }


def precision_at(ranking: list[RankedCandidate], k: int) -> float:
    if not ranking or k <= 0:
        return 0.0
    return 1.0 if any(item.relevant for item in ranking[:k]) else 0.0


def coverage_ratio(candidates: list[Candidate], query: EvalQuery) -> float:
    if not query.expected_terms or query.expected_refused:
        return 0.0
    evidence = normalize_for_match(" ".join(
        f"{candidate.document_title} {candidate.content}" for candidate in candidates
    ))
    covered = sum(1 for term in query.expected_terms if normalize_for_match(term) in evidence)
    return round(covered / len(query.expected_terms), 6)


def snapshot_candidates(query: EvalQuery, candidates: list[Candidate]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        rows.append(
            {
                "query_id": query.query_id,
                "candidate_id": stable_candidate_id(candidate),
                "chunk_id": candidate.chunk_id,
                "rank": candidate.index + 1,
                "source_type": candidate.source_type,
                "title": candidate.document_title[:160],
                "score": round(candidate.score, 6),
                "relevant": candidate.relevant,
            }
        )
    return rows


def summarize_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_reranker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_reranker[str(row["reranker"])].append(row)
    summary_rows: list[dict[str, Any]] = []
    for reranker, reranker_rows in sorted(by_reranker.items()):
        completed = [row for row in reranker_rows if row["status"] == "completed"]
        latencies = sorted(float(row["latency_ms"]) for row in completed)
        summary_rows.append(
            {
                "reranker": reranker,
                "queries": len(reranker_rows),
                "completed": len(completed),
                "error_count": len(reranker_rows) - len(completed),
                "fallback_count": sum(int(row.get("fallback_count", 0)) for row in reranker_rows),
                "mrr_at_5": average(completed, "mrr_at_5"),
                "ndcg_at_5": average(completed, "ndcg_at_5"),
                "precision_at_1": average(completed, "precision_at_1"),
                "precision_at_3": average(completed, "precision_at_3"),
                "precision_at_5": average(completed, "precision_at_5"),
                "coverage_ratio": average(completed, "coverage_ratio"),
                "refusal_accuracy": average(completed, "refusal_accuracy"),
                "avg_latency_ms": average(completed, "latency_ms"),
                "p95_latency_ms": percentile(latencies, 0.95),
            }
        )
    return {"rerankers": summary_rows, "decision": decision(summary_rows)}


def decision(summary_rows: list[dict[str, Any]]) -> str:
    by_name = {row["reranker"]: row for row in summary_rows}
    bge = by_name.get("remote-bge-lora")
    glm = by_name.get("glm-reranker")
    if not bge or bge["completed"] == 0:
        return "remote_bge_not_evaluated"
    if not glm or glm["completed"] == 0:
        return "parallel_candidate"
    if float(bge["mrr_at_5"]) >= float(glm["mrr_at_5"]) and float(bge["coverage_ratio"]) >= float(glm["coverage_ratio"]):
        return "switch_default_to_remote_bge_lora"
    if float(bge["mrr_at_5"]) >= float(glm["mrr_at_5"]) * 0.95:
        return "parallel_candidate"
    return "private_fallback_only"


def write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "query_id",
        "dataset",
        "category",
        "reranker",
        "candidate_count",
        "relevant_count",
        "mrr_at_5",
        "ndcg_at_5",
        "precision_at_1",
        "precision_at_3",
        "precision_at_5",
        "coverage_ratio",
        "refusal_accuracy",
        "latency_ms",
        "top_chunk_id",
        "top_title",
        "status",
        "error",
        "fallback_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_csv(path: Path, summary: dict[str, Any]) -> None:
    fieldnames = [
        "reranker",
        "queries",
        "completed",
        "error_count",
        "fallback_count",
        "mrr_at_5",
        "ndcg_at_5",
        "precision_at_1",
        "precision_at_3",
        "precision_at_5",
        "coverage_ratio",
        "refusal_accuracy",
        "avg_latency_ms",
        "p95_latency_ms",
        "decision",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary["rerankers"]:
            writer.writerow({**row, "decision": summary["decision"]})


def write_snapshot_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def stable_candidate_id(candidate: Candidate) -> str:
    payload = f"{candidate.chunk_id}:{candidate.document_title}:{candidate.source_type}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def parse_bool(value: str | None) -> bool:
    return (value or "").strip().casefold() in {"true", "yes", "1"}


def average(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(float(row[key]) for row in rows) / len(rows), 6)


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, math.ceil(len(values) * quantile) - 1)
    return round(values[index], 3)


def sanitize_error(message: str) -> str:
    settings = get_settings()
    for secret in [settings.reranking_api_key, settings.embedding_api_key]:
        if secret:
            message = message.replace(secret, "<redacted>")
    return message.replace("\n", " ")[:300]


if __name__ == "__main__":
    main()
