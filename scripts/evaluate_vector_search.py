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
from app.services.retrieval.vector_index import VectorIndexResult, VectorIndexService  # noqa: E402
from app.services.retrieval.vector_search import VectorSearchResult, VectorSearchService  # noqa: E402


QUERY_FIELDS = [
    "query_id",
    "question",
    "query",
    "top_k",
    "expected_title_terms",
    "expected_content_terms",
    "expected_source_types",
    "notes",
]

RESULT_FIELDS = [
    "query_id",
    "query",
    "passed",
    "keyword_passed",
    "comparison",
    "hit_rank",
    "hit_document_id",
    "hit_title",
    "hit_source_type",
    "metadata_ratio",
    "result_count",
    "best_score",
    "top_scores",
    "top_titles",
    "top_source_types",
    "provider",
    "model_name",
    "notes",
]


@dataclass(frozen=True)
class ExpectedQuery:
    query_id: str
    question: str
    query: str
    top_k: int
    expected_title_terms: list[str]
    expected_content_terms: list[str]
    expected_source_types: list[str]
    notes: str


@dataclass(frozen=True)
class EvaluatedVectorResult:
    query_id: str
    query: str
    passed: bool
    keyword_passed: bool | None
    comparison: str
    hit_rank: int | None
    hit_document_id: int | None
    hit_title: str
    hit_source_type: str
    metadata_ratio: float
    result_count: int
    best_score: float
    top_scores: str
    top_titles: str
    top_source_types: str
    provider: str
    model_name: str
    notes: str

    def to_row(self) -> dict[str, str]:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "passed": "yes" if self.passed else "no",
            "keyword_passed": format_optional_bool(self.keyword_passed),
            "comparison": self.comparison,
            "hit_rank": str(self.hit_rank or ""),
            "hit_document_id": str(self.hit_document_id or ""),
            "hit_title": self.hit_title,
            "hit_source_type": self.hit_source_type,
            "metadata_ratio": f"{self.metadata_ratio:.2f}",
            "result_count": str(self.result_count),
            "best_score": f"{self.best_score:.4f}",
            "top_scores": self.top_scores,
            "top_titles": self.top_titles,
            "top_source_types": self.top_source_types,
            "provider": self.provider,
            "model_name": self.model_name,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the stage-2 vector search chain.")
    parser.add_argument("--queries", default="data/evaluation/keyword_queries.csv")
    parser.add_argument("--out", default="data/evaluation/vector_results.csv")
    parser.add_argument("--keyword-results", default="data/evaluation/keyword_results.csv")
    parser.add_argument("--top-k", type=int, default=0, help="Override top_k for every query when greater than zero.")
    parser.add_argument("--provider", default="", help="Embedding provider name. Defaults to .env EMBEDDING_PROVIDER or deterministic.")
    parser.add_argument("--batch-size", type=int, default=32, help="Number of chunks embedded per provider call.")
    parser.add_argument("--skip-index-build", action="store_true", help="Use existing chunk_embeddings without rebuilding missing or stale vectors.")
    args = parser.parse_args()

    settings = get_settings()
    provider = create_embedding_provider_from_settings(args.provider, settings)
    expected_queries = read_expected_queries(Path(args.queries), top_k_override=args.top_k)
    keyword_passed_by_id = read_keyword_passed(Path(args.keyword_results))

    init_db()
    index_result: VectorIndexResult | None = None
    with SessionLocal() as db:
        if not args.skip_index_build:
            index_result = VectorIndexService(db, provider).build_index(batch_size=args.batch_size)
        results = evaluate_queries(expected_queries, db, provider, keyword_passed_by_id)

    write_results(Path(args.out), results)
    print_summary(results, args.out, index_result)


def create_embedding_provider_from_settings(
    provider_name: str | None,
    settings,
) -> EmbeddingProvider:
    return create_embedding_provider(
        provider_name=provider_name or settings.embedding_provider or "deterministic",
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension or None,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


def read_expected_queries(path: Path, top_k_override: int = 0) -> list[ExpectedQuery]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = set(QUERY_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing query fields: {', '.join(sorted(missing))}")
        return [
            ExpectedQuery(
                query_id=row["query_id"],
                question=row["question"],
                query=row["query"] or row["question"],
                top_k=top_k_override or parse_top_k(row["top_k"]),
                expected_title_terms=split_terms(row["expected_title_terms"]),
                expected_content_terms=split_terms(row["expected_content_terms"]),
                expected_source_types=split_terms(row["expected_source_types"]),
                notes=row["notes"],
            )
            for row in reader
        ]


def read_keyword_passed(path: Path) -> dict[str, bool]:
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


def parse_top_k(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        return 8
    return parsed if parsed > 0 else 8


def split_terms(value: str) -> list[str]:
    return [term.strip() for term in (value or "").split("|") if term.strip()]


def parse_bool(value: str) -> bool:
    return (value or "").strip().casefold() in {"yes", "true", "1", "pass", "passed"}


def evaluate_queries(
    expected_queries: list[ExpectedQuery],
    db,
    provider: EmbeddingProvider,
    keyword_passed_by_id: dict[str, bool] | None = None,
) -> list[EvaluatedVectorResult]:
    keyword_passed_by_id = keyword_passed_by_id or {}
    search_service = VectorSearchService(db, provider)
    evaluated: list[EvaluatedVectorResult] = []
    for expected in expected_queries:
        search_results = search_service.search(expected.query, top_k=expected.top_k)
        hit_index = find_hit(expected, search_results)
        hit = search_results[hit_index] if hit_index is not None else None
        metadata_count = sum(1 for result in search_results if result.source_type == "metadata_record")
        metadata_ratio = metadata_count / len(search_results) if search_results else 0.0
        best_score = search_results[0].score if search_results else 0.0
        keyword_passed = keyword_passed_by_id.get(expected.query_id)
        passed = hit is not None
        evaluated.append(
            EvaluatedVectorResult(
                query_id=expected.query_id,
                query=expected.query,
                passed=passed,
                keyword_passed=keyword_passed,
                comparison=compare_with_keyword(passed, keyword_passed),
                hit_rank=(hit_index + 1) if hit_index is not None else None,
                hit_document_id=hit.document_id if hit else None,
                hit_title=hit.document_title if hit else "",
                hit_source_type=hit.source_type if hit else "",
                metadata_ratio=metadata_ratio,
                result_count=len(search_results),
                best_score=best_score,
                top_scores=" || ".join(f"{result.score:.4f}" for result in search_results),
                top_titles=" || ".join(result.document_title for result in search_results),
                top_source_types=" || ".join(result.source_type for result in search_results),
                provider=provider.provider_name,
                model_name=provider.model_name,
                notes=expected.notes,
            )
        )
    return evaluated


def find_hit(expected: ExpectedQuery, search_results: list[VectorSearchResult]) -> int | None:
    for index, result in enumerate(search_results):
        if expected.expected_source_types and result.source_type not in expected.expected_source_types:
            continue
        if expected.expected_title_terms and not contains_any(result.document_title, expected.expected_title_terms):
            continue
        if expected.expected_content_terms and not contains_any(result.content, expected.expected_content_terms):
            continue
        return index
    return None


def contains_any(value: str, terms: list[str]) -> bool:
    normalized = normalize(value)
    return any(normalize(term) in normalized for term in terms)


def normalize(value: str) -> str:
    return (value or "").casefold()


def compare_with_keyword(vector_passed: bool, keyword_passed: bool | None) -> str:
    if keyword_passed is None:
        return ""
    if vector_passed and keyword_passed:
        return "same_pass"
    if not vector_passed and not keyword_passed:
        return "same_fail"
    if vector_passed and not keyword_passed:
        return "vector_only_pass"
    return "keyword_only_pass"


def format_optional_bool(value: bool | None) -> str:
    if value is None:
        return ""
    return "yes" if value else "no"


def write_results(path: Path, results: list[EvaluatedVectorResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(
    results: list[EvaluatedVectorResult],
    output_path: str,
    index_result: VectorIndexResult | None,
) -> None:
    if index_result is not None:
        print(
            "vector index checked\t"
            f"provider={index_result.provider}\t"
            f"model={index_result.model_name}\t"
            f"dimension={index_result.dimension}\t"
            f"total={index_result.total_chunks}\t"
            f"indexed={index_result.indexed_chunks}\t"
            f"updated={index_result.updated_chunks}\t"
            f"skipped={index_result.skipped_chunks}"
        )

    passed = sum(1 for result in results if result.passed)
    total = len(results)
    print(f"vector evaluation: {passed}/{total} passed")

    keyword_known = [result for result in results if result.keyword_passed is not None]
    if keyword_known:
        keyword_passed = sum(1 for result in keyword_known if result.keyword_passed)
        vector_only = sum(1 for result in keyword_known if result.comparison == "vector_only_pass")
        keyword_only = sum(1 for result in keyword_known if result.comparison == "keyword_only_pass")
        print(
            f"keyword baseline: {keyword_passed}/{len(keyword_known)} passed\t"
            f"vector_only_pass={vector_only}\tkeyword_only_pass={keyword_only}"
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
