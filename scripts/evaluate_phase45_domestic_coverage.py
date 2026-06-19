"""Evaluate Phase 45 domestic corpus coverage without exporting chunk text."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import create_database_engine  # noqa: E402
from app.services.retrieval.keyword_search import KeywordSearchService  # noqa: E402


DEFAULT_QUERIES = ROOT / "data" / "evaluation" / "phase45_domestic_coverage_queries.csv"
DEFAULT_RESULTS = ROOT / "data" / "evaluation" / "phase45_domestic_coverage_results.csv"
DEFAULT_SUMMARY = ROOT / "data" / "evaluation" / "phase45_domestic_coverage_summary.csv"
DEFAULT_CURRENT_DB = ROOT / "data" / "app.sqlite"
DEFAULT_BASELINE_DB = ROOT / "data" / "app.sqlite.backup-before-phase45-phase11-import-20260618"


@dataclass(frozen=True)
class CoverageResult:
    query_id: str
    query: str
    corpus: str
    hit_count: int
    phase45_hit_count: int
    top_title: str
    top_source_type: str
    top_document_id: int | None


def read_queries(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def evaluate_database(db_path: Path, corpus_name: str, queries: list[dict[str, str]], top_k: int) -> list[CoverageResult]:
    engine = create_database_engine(f"sqlite:///{db_path.as_posix()}")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    rows: list[CoverageResult] = []
    with SessionLocal() as db:
        service = KeywordSearchService(db)
        for query in queries:
            results = service.search(query["query"], top_k=top_k)
            top = results[0] if results else None
            rows.append(
                CoverageResult(
                    query_id=query["query_id"],
                    query=query["query"],
                    corpus=corpus_name,
                    hit_count=len(results),
                    phase45_hit_count=sum(1 for result in results if "papers_0618" in (result.source_path or "")),
                    top_title=top.document_title if top else "",
                    top_source_type=top.source_type if top else "",
                    top_document_id=top.document_id if top else None,
                )
            )
    return rows


def summarize(rows: list[CoverageResult]) -> list[dict[str, str]]:
    by_corpus: dict[str, list[CoverageResult]] = {}
    for row in rows:
        by_corpus.setdefault(row.corpus, []).append(row)
    summary: list[dict[str, str]] = []
    for corpus, corpus_rows in sorted(by_corpus.items()):
        total = len(corpus_rows)
        summary.append(
            {
                "corpus": corpus,
                "queries": str(total),
                "queries_with_hits": str(sum(1 for row in corpus_rows if row.hit_count > 0)),
                "queries_with_phase45_hits": str(sum(1 for row in corpus_rows if row.phase45_hit_count > 0)),
                "total_phase45_hits": str(sum(row.phase45_hit_count for row in corpus_rows)),
                "avg_hit_count": f"{sum(row.hit_count for row in corpus_rows) / max(total, 1):.2f}",
            }
        )
    return summary


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str] | CoverageResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row) if not isinstance(row, dict) else row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Phase 45 domestic corpus coverage.")
    parser.add_argument("--queries", default=str(DEFAULT_QUERIES))
    parser.add_argument("--current-db", default=str(DEFAULT_CURRENT_DB))
    parser.add_argument("--baseline-db", default=str(DEFAULT_BASELINE_DB))
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    queries = read_queries(Path(args.queries))
    rows: list[CoverageResult] = []
    baseline_path = Path(args.baseline_db)
    if baseline_path.exists():
        rows.extend(evaluate_database(baseline_path, "baseline_before_phase11", queries, args.top_k))
    rows.extend(evaluate_database(Path(args.current_db), "current_phase45", queries, args.top_k))

    write_csv(Path(args.results), list(asdict(rows[0]).keys()), rows)
    summary = summarize(rows)
    write_csv(Path(args.summary), list(summary[0].keys()), summary)
    for item in summary:
        print(item)
    print(f"wrote {args.results}")
    print(f"wrote {args.summary}")


if __name__ == "__main__":
    main()
