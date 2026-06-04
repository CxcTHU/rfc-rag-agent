from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.models import Document  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.retrieval.keyword_search import KeywordSearchService  # noqa: E402


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
    "hit_rank",
    "hit_document_id",
    "hit_title",
    "hit_source_type",
    "metadata_ratio",
    "result_count",
    "top_titles",
    "top_source_types",
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
class EvaluatedResult:
    query_id: str
    query: str
    passed: bool
    hit_rank: int | None
    hit_document_id: int | None
    hit_title: str
    hit_source_type: str
    metadata_ratio: float
    result_count: int
    top_titles: str
    top_source_types: str
    notes: str

    def to_row(self) -> dict[str, str]:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "passed": "yes" if self.passed else "no",
            "hit_rank": str(self.hit_rank or ""),
            "hit_document_id": str(self.hit_document_id or ""),
            "hit_title": self.hit_title,
            "hit_source_type": self.hit_source_type,
            "metadata_ratio": f"{self.metadata_ratio:.2f}",
            "result_count": str(self.result_count),
            "top_titles": self.top_titles,
            "top_source_types": self.top_source_types,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the stage-1 keyword search baseline.")
    parser.add_argument("--queries", default="data/evaluation/keyword_queries.csv")
    parser.add_argument("--out", default="data/evaluation/keyword_results.csv")
    parser.add_argument("--top-k", type=int, default=0, help="Override top_k for every query when greater than zero.")
    args = parser.parse_args()

    expected_queries = read_expected_queries(Path(args.queries), top_k_override=args.top_k)
    results = evaluate_queries(expected_queries)
    write_results(Path(args.out), results)

    passed = sum(1 for result in results if result.passed)
    total = len(results)
    print(f"keyword evaluation: {passed}/{total} passed")
    print(f"wrote results to {args.out}")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"{status}\t{result.query_id}\tmetadata_ratio={result.metadata_ratio:.2f}\t"
            f"hit_rank={result.hit_rank or '-'}\t{result.hit_title or '-'}"
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


def parse_top_k(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        return 8
    return parsed if parsed > 0 else 8


def split_terms(value: str) -> list[str]:
    return [term.strip() for term in (value or "").split("|") if term.strip()]


def evaluate_queries(expected_queries: list[ExpectedQuery]) -> list[EvaluatedResult]:
    evaluated: list[EvaluatedResult] = []
    with SessionLocal() as db:
        search_service = KeywordSearchService(db)
        for expected in expected_queries:
            search_results = search_service.search(expected.query, top_k=expected.top_k)
            source_types = [
                document_source_type(db, result.document_id)
                for result in search_results
            ]
            hit_index = find_hit(expected, search_results, source_types)
            metadata_count = sum(1 for source_type in source_types if source_type == "metadata_record")
            metadata_ratio = metadata_count / len(source_types) if source_types else 0.0
            hit = search_results[hit_index] if hit_index is not None else None
            evaluated.append(
                EvaluatedResult(
                    query_id=expected.query_id,
                    query=expected.query,
                    passed=hit is not None,
                    hit_rank=(hit_index + 1) if hit_index is not None else None,
                    hit_document_id=hit.document_id if hit else None,
                    hit_title=hit.document_title if hit else "",
                    hit_source_type=source_types[hit_index] if hit_index is not None else "",
                    metadata_ratio=metadata_ratio,
                    result_count=len(search_results),
                    top_titles=" || ".join(result.document_title for result in search_results),
                    top_source_types=" || ".join(source_types),
                    notes=expected.notes,
                )
            )
    return evaluated


def document_source_type(db, document_id: int) -> str:
    document = db.get(Document, document_id)
    return document.source_type if document else ""


def find_hit(expected: ExpectedQuery, search_results, source_types: list[str]) -> int | None:
    for index, result in enumerate(search_results):
        if expected.expected_source_types and source_types[index] not in expected.expected_source_types:
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


def write_results(path: Path, results: list[EvaluatedResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


if __name__ == "__main__":
    main()
