from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService  # noqa: E402
from scripts.evaluate_vector_search import ExpectedQuery  # noqa: E402
from scripts.evaluate_vector_search import contains_any  # noqa: E402
from scripts.evaluate_vector_search import read_expected_queries  # noqa: E402


RESULT_FIELDS = [
    "query_id",
    "query",
    "passed",
    "keyword_passed",
    "vector_passed",
    "comparison",
    "hit_rank",
    "hit_document_id",
    "hit_title",
    "hit_source_type",
    "metadata_ratio",
    "result_count",
    "best_score",
    "top_scores",
    "top_keyword_scores",
    "top_vector_scores",
    "top_titles",
    "top_source_types",
    "provider",
    "model_name",
    "notes",
]


@dataclass(frozen=True)
class EvaluatedHybridResult:
    query_id: str
    query: str
    passed: bool
    keyword_passed: bool | None
    vector_passed: bool | None
    comparison: str
    hit_rank: int | None
    hit_document_id: int | None
    hit_title: str
    hit_source_type: str
    metadata_ratio: float
    result_count: int
    best_score: float
    top_scores: str
    top_keyword_scores: str
    top_vector_scores: str
    top_titles: str
    top_source_types: str
    provider: str
    model_name: str
    notes: str

    def to_row(self) -> dict[str, str]:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "passed": format_optional_bool(self.passed),
            "keyword_passed": format_optional_bool(self.keyword_passed),
            "vector_passed": format_optional_bool(self.vector_passed),
            "comparison": self.comparison,
            "hit_rank": str(self.hit_rank or ""),
            "hit_document_id": str(self.hit_document_id or ""),
            "hit_title": self.hit_title,
            "hit_source_type": self.hit_source_type,
            "metadata_ratio": f"{self.metadata_ratio:.2f}",
            "result_count": str(self.result_count),
            "best_score": f"{self.best_score:.4f}",
            "top_scores": self.top_scores,
            "top_keyword_scores": self.top_keyword_scores,
            "top_vector_scores": self.top_vector_scores,
            "top_titles": self.top_titles,
            "top_source_types": self.top_source_types,
            "provider": self.provider,
            "model_name": self.model_name,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the stage-6 hybrid search chain.")
    parser.add_argument("--queries", default="data/evaluation/keyword_queries.csv")
    parser.add_argument("--out", default="data/evaluation/hybrid_results.csv")
    parser.add_argument("--keyword-results", default="data/evaluation/keyword_results.csv")
    parser.add_argument("--vector-results", default="data/evaluation/vector_results.csv")
    parser.add_argument("--top-k", type=int, default=0, help="Override top_k for every query when greater than zero.")
    parser.add_argument("--provider", default="", help="Embedding provider name. Defaults to .env EMBEDDING_PROVIDER or deterministic.")
    args = parser.parse_args()

    settings = get_settings()
    provider_name = args.provider or settings.embedding_provider or "deterministic"
    provider = create_embedding_provider(provider_name)
    expected_queries = read_expected_queries(Path(args.queries), top_k_override=args.top_k)
    keyword_passed_by_id = read_passed_by_id(Path(args.keyword_results))
    vector_passed_by_id = read_passed_by_id(Path(args.vector_results))

    init_db()
    with SessionLocal() as db:
        results = evaluate_queries(
            expected_queries=expected_queries,
            db=db,
            provider=provider,
            keyword_passed_by_id=keyword_passed_by_id,
            vector_passed_by_id=vector_passed_by_id,
        )

    write_results(Path(args.out), results)
    print_summary(results, args.out)


def evaluate_queries(
    expected_queries: list[ExpectedQuery],
    db,
    provider: EmbeddingProvider,
    keyword_passed_by_id: dict[str, bool] | None = None,
    vector_passed_by_id: dict[str, bool] | None = None,
) -> list[EvaluatedHybridResult]:
    keyword_passed_by_id = keyword_passed_by_id or {}
    vector_passed_by_id = vector_passed_by_id or {}
    search_service = HybridSearchService(db, provider)
    evaluated: list[EvaluatedHybridResult] = []
    for expected in expected_queries:
        search_results = search_service.search(expected.query, top_k=expected.top_k)
        hit_index = find_hit(expected, search_results)
        hit = search_results[hit_index] if hit_index is not None else None
        metadata_count = sum(1 for result in search_results if result.source_type == "metadata_record")
        metadata_ratio = metadata_count / len(search_results) if search_results else 0.0
        best_score = search_results[0].score if search_results else 0.0
        keyword_passed = keyword_passed_by_id.get(expected.query_id)
        vector_passed = vector_passed_by_id.get(expected.query_id)
        passed = hit is not None
        evaluated.append(
            EvaluatedHybridResult(
                query_id=expected.query_id,
                query=expected.query,
                passed=passed,
                keyword_passed=keyword_passed,
                vector_passed=vector_passed,
                comparison=compare_with_baselines(passed, keyword_passed, vector_passed),
                hit_rank=(hit_index + 1) if hit_index is not None else None,
                hit_document_id=hit.document_id if hit else None,
                hit_title=hit.document_title if hit else "",
                hit_source_type=hit.source_type if hit else "",
                metadata_ratio=metadata_ratio,
                result_count=len(search_results),
                best_score=best_score,
                top_scores=" || ".join(f"{result.score:.4f}" for result in search_results),
                top_keyword_scores=" || ".join(f"{result.keyword_score:.4f}" for result in search_results),
                top_vector_scores=" || ".join(f"{result.vector_score:.4f}" for result in search_results),
                top_titles=" || ".join(result.document_title for result in search_results),
                top_source_types=" || ".join(result.source_type for result in search_results),
                provider=provider.provider_name,
                model_name=provider.model_name,
                notes=expected.notes,
            )
        )
    return evaluated


def find_hit(expected: ExpectedQuery, search_results: list[HybridSearchResult]) -> int | None:
    for index, result in enumerate(search_results):
        if expected.expected_source_types and result.source_type not in expected.expected_source_types:
            continue
        if expected.expected_title_terms and not contains_any(result.document_title, expected.expected_title_terms):
            continue
        if expected.expected_content_terms and not contains_any(result.content, expected.expected_content_terms):
            continue
        return index
    return None


def read_passed_by_id(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not {"query_id", "passed"}.issubset(reader.fieldnames or []):
            return {}
        return {
            row["query_id"]: parse_bool(row["passed"])
            for row in reader
            if row.get("query_id")
        }


def parse_bool(value: str) -> bool:
    return (value or "").strip().casefold() in {"yes", "true", "1", "pass", "passed"}


def compare_with_baselines(
    hybrid_passed: bool,
    keyword_passed: bool | None,
    vector_passed: bool | None,
) -> str:
    if keyword_passed is None and vector_passed is None:
        return ""
    if hybrid_passed and keyword_passed and vector_passed:
        return "all_pass"
    if hybrid_passed and keyword_passed and vector_passed is False:
        return "hybrid_rescued_vector"
    if hybrid_passed and keyword_passed is False and vector_passed:
        return "hybrid_vector_pass_keyword_fail"
    if hybrid_passed and keyword_passed is False and vector_passed is False:
        return "hybrid_only_pass"
    if not hybrid_passed and keyword_passed:
        return "hybrid_regressed_keyword"
    if not hybrid_passed and vector_passed:
        return "hybrid_regressed_vector"
    return "all_fail"


def format_optional_bool(value: bool | None) -> str:
    if value is None:
        return ""
    return "yes" if value else "no"


def write_results(path: Path, results: list[EvaluatedHybridResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(results: list[EvaluatedHybridResult], output_path: str) -> None:
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    rescued_vector = sum(1 for result in results if result.comparison == "hybrid_rescued_vector")
    regressed_keyword = sum(1 for result in results if result.comparison == "hybrid_regressed_keyword")
    print(
        f"hybrid evaluation: {passed}/{total} passed\t"
        f"rescued_vector={rescued_vector}\tregressed_keyword={regressed_keyword}"
    )
    print(f"wrote results to {output_path}")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"{status}\t{result.query_id}\tcomparison={result.comparison or '-'}\t"
            f"hit_rank={result.hit_rank or '-'}\tbest_score={result.best_score:.4f}\t"
            f"{result.hit_title or '-'}"
        )


if __name__ == "__main__":
    main()
