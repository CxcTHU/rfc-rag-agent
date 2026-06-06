from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


OUTPUT_FIELDS = [
    "query_id",
    "query",
    "evaluator",
    "failure_type",
    "expected_terms",
    "actual_top_titles",
    "likely_reason",
    "suggested_fix",
    "before_status",
    "after_status",
]


@dataclass(frozen=True)
class ErrorCase:
    query_id: str
    query: str
    evaluator: str
    failure_type: str
    expected_terms: str
    actual_top_titles: str
    likely_reason: str
    suggested_fix: str
    before_status: str
    after_status: str = "pending"

    def to_row(self) -> dict[str, str]:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "evaluator": self.evaluator,
            "failure_type": self.failure_type,
            "expected_terms": self.expected_terms,
            "actual_top_titles": self.actual_top_titles,
            "likely_reason": self.likely_reason,
            "suggested_fix": self.suggested_fix,
            "before_status": self.before_status,
            "after_status": self.after_status,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze retrieval and chat evaluation failures.")
    parser.add_argument("--keyword-queries", default="data/evaluation/keyword_queries.csv")
    parser.add_argument("--chat-queries", default="data/evaluation/chat_queries.csv")
    parser.add_argument("--keyword-results", default="data/evaluation/keyword_results.csv")
    parser.add_argument("--vector-results", default="data/evaluation/vector_results.csv")
    parser.add_argument("--hybrid-results", default="data/evaluation/hybrid_results.csv")
    parser.add_argument("--chat-results", default="data/evaluation/chat_results.csv")
    parser.add_argument("--out", default="data/evaluation/retrieval_error_cases.csv")
    args = parser.parse_args()

    cases = analyze_error_cases(
        keyword_queries_path=Path(args.keyword_queries),
        chat_queries_path=Path(args.chat_queries),
        keyword_results_path=Path(args.keyword_results),
        vector_results_path=Path(args.vector_results),
        hybrid_results_path=Path(args.hybrid_results),
        chat_results_path=Path(args.chat_results),
    )
    write_error_cases(Path(args.out), cases)

    print(f"retrieval error cases: {len(cases)}")
    print(f"wrote results to {args.out}")
    for case in cases:
        print(f"{case.evaluator}\t{case.query_id}\t{case.failure_type}\t{case.before_status}")


def analyze_error_cases(
    keyword_queries_path: Path,
    chat_queries_path: Path,
    keyword_results_path: Path,
    vector_results_path: Path,
    hybrid_results_path: Path,
    chat_results_path: Path,
) -> list[ErrorCase]:
    keyword_expectations = read_keyword_expectations(keyword_queries_path)
    chat_expectations = read_chat_expectations(chat_queries_path)
    hybrid_passed_by_id = read_passed_by_id(hybrid_results_path)
    cases: list[ErrorCase] = []

    cases.extend(analyze_keyword_results(read_csv(keyword_results_path), keyword_expectations))
    cases.extend(analyze_vector_results(read_csv(vector_results_path), keyword_expectations, hybrid_passed_by_id))
    cases.extend(analyze_chat_results(read_csv(chat_results_path), chat_expectations, hybrid_passed_by_id))
    return cases


def read_keyword_expectations(path: Path) -> dict[str, str]:
    expectations: dict[str, str] = {}
    for row in read_csv(path):
        expectations[row.get("query_id", "")] = join_terms(
            row.get("expected_title_terms", ""),
            row.get("expected_content_terms", ""),
            row.get("expected_source_types", ""),
        )
    return expectations


def read_chat_expectations(path: Path) -> dict[str, str]:
    expectations: dict[str, str] = {}
    for row in read_csv(path):
        expectations[row.get("query_id", "")] = join_terms(
            row.get("expected_source_title_terms", ""),
            row.get("expected_source_content_terms", ""),
            f"expected_refused={row.get('expected_refused', '')}",
        )
    return expectations


def analyze_keyword_results(
    rows: list[dict[str, str]],
    expectations: dict[str, str],
) -> list[ErrorCase]:
    cases: list[ErrorCase] = []
    for row in rows:
        if parse_bool(row.get("passed", "")):
            continue
        cases.append(
            ErrorCase(
                query_id=row.get("query_id", ""),
                query=row.get("query", ""),
                evaluator="keyword",
                failure_type="no_expected_hit",
                expected_terms=expectations.get(row.get("query_id", ""), ""),
                actual_top_titles=row.get("top_titles", ""),
                likely_reason="Keyword baseline did not return a result matching the expected title, content, and source type constraints.",
                suggested_fix="Review synonym rules, title weighting, source diversification, and query terms.",
                before_status="keyword failed",
            )
        )
    return cases


def analyze_vector_results(
    rows: list[dict[str, str]],
    expectations: dict[str, str],
    hybrid_passed_by_id: dict[str, bool] | None = None,
) -> list[ErrorCase]:
    hybrid_passed_by_id = hybrid_passed_by_id or {}
    cases: list[ErrorCase] = []
    for row in rows:
        if parse_bool(row.get("passed", "")):
            continue
        comparison = row.get("comparison", "")
        failure_type = comparison or "no_expected_hit"
        likely_reason = "Vector baseline did not return a result matching the expected title, content, and source type constraints."
        suggested_fix = "Review embedding quality, query expansion, and reranking."
        if comparison == "keyword_only_pass":
            likely_reason = "Vector baseline missed an expected source that keyword search already found."
            suggested_fix = "Use hybrid search or rerank so keyword evidence can rescue weak vector matches."
        cases.append(
            ErrorCase(
                query_id=row.get("query_id", ""),
                query=row.get("query", ""),
                evaluator="vector",
                failure_type=failure_type,
                expected_terms=expectations.get(row.get("query_id", ""), ""),
                actual_top_titles=row.get("top_titles", ""),
                likely_reason=likely_reason,
                suggested_fix=suggested_fix,
                before_status=f"vector failed; comparison={comparison or 'unknown'}",
                after_status=after_status_from_hybrid(row.get("query_id", ""), hybrid_passed_by_id),
            )
        )
    return cases


def analyze_chat_results(
    rows: list[dict[str, str]],
    expectations: dict[str, str],
    hybrid_passed_by_id: dict[str, bool] | None = None,
) -> list[ErrorCase]:
    cases: list[ErrorCase] = []
    for row in rows:
        if parse_bool(row.get("passed", "")):
            continue
        query_id = row.get("query_id", "")
        cases.append(
            ErrorCase(
                query_id=query_id,
                query=row.get("question", ""),
                evaluator="chat",
                failure_type=chat_failure_type(row),
                expected_terms=expectations.get(query_id, ""),
                actual_top_titles=row.get("top_source_titles", ""),
                likely_reason=chat_failure_reason(row),
                suggested_fix="Inspect retrieval results, citation mapping, refusal threshold, and prompt constraints.",
                before_status="chat failed",
                after_status=after_status_from_hybrid(query_id, hybrid_passed_by_id or {}),
            )
        )
    return cases


def read_passed_by_id(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {}
    rows = read_csv(path)
    return {
        row["query_id"]: parse_bool(row["passed"])
        for row in rows
        if row.get("query_id") and "passed" in row
    }


def after_status_from_hybrid(query_id: str, hybrid_passed_by_id: dict[str, bool]) -> str:
    if query_id not in hybrid_passed_by_id:
        return "pending"
    return "fixed_by_hybrid" if hybrid_passed_by_id[query_id] else "still_failing"


def chat_failure_type(row: dict[str, str]) -> str:
    if not parse_bool(row.get("returned_answer", "")):
        return "no_answer"
    if not parse_bool(row.get("refusal_matched", "")):
        if parse_bool(row.get("expected_refused", "")) and not parse_bool(row.get("refused", "")):
            return "under_refusal"
        if not parse_bool(row.get("expected_refused", "")) and parse_bool(row.get("refused", "")):
            return "over_refusal"
        return "refusal_mismatch"
    if not parse_bool(row.get("citations_valid", "")):
        return "citation_miss"
    if not parse_bool(row.get("expected_source_hit", "")):
        return "source_miss"
    if not parse_bool(row.get("forbidden_terms_absent", "")):
        return "faithfulness_risk"
    return "chat_quality_failure"


def chat_failure_reason(row: dict[str, str]) -> str:
    failure_type = chat_failure_type(row)
    reasons = {
        "no_answer": "The chat chain did not return an answer.",
        "under_refusal": "The model answered when the query should have been refused.",
        "over_refusal": "The model refused despite an expected answerable query.",
        "refusal_mismatch": "The refusal state did not match expectation.",
        "citation_miss": "Returned citations did not map cleanly to retrieved sources.",
        "source_miss": "Retrieved sources did not match expected source terms.",
        "faithfulness_risk": "The answer contained forbidden terms that indicate possible unsupported content.",
    }
    return reasons.get(failure_type, "The chat result failed one or more quality checks.")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_error_cases(path: Path, cases: list[ErrorCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for case in cases:
            writer.writerow(case.to_row())


def parse_bool(value: str) -> bool:
    return (value or "").strip().casefold() in {"yes", "true", "1", "pass", "passed"}


def join_terms(*values: str) -> str:
    terms: list[str] = []
    for value in values:
        for term in (value or "").split("|"):
            stripped = term.strip()
            if stripped:
                terms.append(stripped)
    return " | ".join(dict.fromkeys(terms))


if __name__ == "__main__":
    main()
