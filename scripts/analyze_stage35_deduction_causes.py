from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_DEDUCTIONS = ROOT / "data" / "evaluation" / "stage30_quality_deductions.csv"
DEFAULT_RESULTS = ROOT / "data" / "evaluation" / "stage29_real_quality_results.csv"
DEFAULT_QUERIES = ROOT / "data" / "evaluation" / "stage29_new_corpus_queries.csv"
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "stage35_deduction_root_causes.csv"

ROOT_CAUSES = {
    "retrieval_miss",
    "context_expansion_miss",
    "prompt_citation_gap",
    "answer_coverage_gap",
    "rule_too_strict",
}

OUTPUT_FIELDS = [
    "query_id",
    "dimension",
    "deduction_points",
    "root_cause",
    "evidence_summary",
    "repair_recommendation",
    "needs_score_rerun",
]

SENSITIVE_MARKERS = [
    "api key",
    "bearer token",
    "authorization",
    "raw_response",
    "raw provider response",
    "reasoning_content",
    "hidden thought",
]


@dataclass(frozen=True)
class CauseAnalysis:
    query_id: str
    dimension: str
    deduction_points: str
    root_cause: str
    evidence_summary: str
    repair_recommendation: str
    needs_score_rerun: str = "true"

    def as_dict(self) -> dict[str, str]:
        return {
            "query_id": self.query_id,
            "dimension": self.dimension,
            "deduction_points": self.deduction_points,
            "root_cause": self.root_cause,
            "evidence_summary": self.evidence_summary,
            "repair_recommendation": self.repair_recommendation,
            "needs_score_rerun": self.needs_score_rerun,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify Stage 30 deductions into Stage 35 root-cause buckets. "
            "This script is read-only for inputs and never calls real providers."
        )
    )
    parser.add_argument("--deductions", default=str(DEFAULT_DEDUCTIONS))
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--queries", default=str(DEFAULT_QUERIES))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def index_by_query_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("query_id", ""): row for row in rows if row.get("query_id")}


def bool_text(value: str) -> bool:
    return value.strip().lower() == "true"


def to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def split_semicolon(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def safe_join(items: list[str], *, limit: int = 4) -> str:
    return "; ".join(items[:limit])


def sanitize_summary(text: str) -> str:
    sanitized = " ".join((text or "").replace("\r", " ").replace("\n", " ").split())
    lower = sanitized.lower()
    for marker in SENSITIVE_MARKERS:
        if marker in lower:
            sanitized = sanitized.replace(marker, "[redacted]")
            sanitized = sanitized.replace(marker.upper(), "[redacted]")
    return sanitized[:800]


def classify_deduction(
    deduction: dict[str, str],
    result: dict[str, str],
    query: dict[str, str],
) -> tuple[str, str, str]:
    dimension = deduction.get("dimension", "")
    query_id = deduction.get("query_id", "")
    if dimension == "rule_based_context_answer_quality" and not result:
        root_cause = "rule_too_strict"
        evidence = f"query_id={query_id}, evidence_row=missing, dimension={dimension}"
        repair = (
            "Check whether the scoring input row is missing before changing retrieval or generation logic; "
            "rerun Stage 30 after restoring complete evaluation inputs."
        )
        return root_cause, sanitize_summary(evidence), repair

    precision_at_5 = bool_text(result.get("precision_at_5", ""))
    precision_at_3 = bool_text(result.get("precision_at_3", ""))
    coverage = to_float(result.get("coverage_ratio", "0"))
    missing_points = split_semicolon(result.get("missing_points", ""))
    covered_points = split_semicolon(result.get("covered_points", ""))
    expected_points = split_semicolon(query.get("expected_answer_points", ""))
    top_titles = split_semicolon(result.get("top_titles", "").replace(" || ", ";"))
    expected_source = result.get("expected_source_type") or query.get("expected_source_type", "")
    distribution = result.get("source_type_distribution", "")

    if dimension == "retrieval_quality":
        root_cause = "retrieval_miss"
        evidence = (
            f"precision_at_5={str(precision_at_5).lower()}, expected_source_type={expected_source}, "
            f"source_type_distribution={distribution}, top_titles={safe_join(top_titles)}"
        )
        repair = (
            "Calibrate retrieval recall for the expected source type; inspect synonym expansion, "
            "hybrid/BM25 weighting, and recall_k before changing scoring rules."
        )
        return root_cause, sanitize_summary(evidence), repair

    if dimension == "rule_based_context_answer_quality" and not precision_at_5:
        root_cause = "retrieval_miss"
        evidence = (
            f"coverage_ratio={coverage:.3f}, precision_at_5=false, missing_points={safe_join(missing_points)}, "
            f"top_titles={safe_join(top_titles)}"
        )
        repair = (
            "Fix retrieval before judging answer coverage; rerun Stage 30 after the expected source "
            "or equivalent evidence appears in Top-5."
        )
        return root_cause, sanitize_summary(evidence), repair

    if dimension == "rule_based_context_answer_quality" and precision_at_5 and not precision_at_3:
        root_cause = "context_expansion_miss"
        evidence = (
            f"coverage_ratio={coverage:.3f}, precision_at_5=true but precision_at_3=false, "
            f"missing_points={safe_join(missing_points)}, covered_points={safe_join(covered_points)}"
        )
        repair = (
            "Inspect parent-child or adjacent context expansion so the answer-bearing evidence is close "
            "enough to the prompt context."
        )
        return root_cause, sanitize_summary(evidence), repair

    if dimension == "rule_based_context_answer_quality" and coverage < 0.5:
        missing_ratio = len(missing_points) / len(expected_points) if expected_points else 0.0
        if missing_points and missing_ratio >= 0.5:
            root_cause = "answer_coverage_gap"
            repair = (
                "Strengthen answer prompt coverage requirements and verify the generated answer covers "
                "the missing expected points with citations."
            )
        else:
            root_cause = "rule_too_strict"
            repair = (
                "Review expected_answer_points and matching terms; document any rule calibration before "
                "rerunning the score."
            )
        evidence = (
            f"coverage_ratio={coverage:.3f}, precision_at_5=true, missing_points={safe_join(missing_points)}, "
            f"expected_points={safe_join(expected_points)}"
        )
        return root_cause, sanitize_summary(evidence), repair

    if "citation" in deduction.get("deduction_reason", "").lower():
        root_cause = "prompt_citation_gap"
        evidence = (
            f"dimension={dimension}, covered_points={safe_join(covered_points)}, "
            f"missing_points={safe_join(missing_points)}"
        )
        repair = "Tighten prompt citation rules and invalid_citations handling."
        return root_cause, sanitize_summary(evidence), repair

    root_cause = "answer_coverage_gap"
    evidence = f"query_id={query_id}, dimension={dimension}, coverage_ratio={coverage:.3f}"
    repair = "Inspect answer coverage and rerun Stage 30 after the minimal fix."
    return root_cause, sanitize_summary(evidence), repair


def analyze_deductions(
    deductions: list[dict[str, str]],
    results: list[dict[str, str]],
    queries: list[dict[str, str]],
) -> list[CauseAnalysis]:
    result_by_id = index_by_query_id(results)
    query_by_id = index_by_query_id(queries)
    analyses: list[CauseAnalysis] = []

    for deduction in deductions:
        query_id = deduction.get("query_id", "")
        result = result_by_id.get(query_id, {})
        query = query_by_id.get(query_id, {})
        root_cause, evidence, repair = classify_deduction(deduction, result, query)
        if root_cause not in ROOT_CAUSES:
            raise ValueError(f"unsupported root cause: {root_cause}")
        analyses.append(
            CauseAnalysis(
                query_id=query_id,
                dimension=deduction.get("dimension", ""),
                deduction_points=deduction.get("deduction_points", ""),
                root_cause=root_cause,
                evidence_summary=evidence,
                repair_recommendation=repair,
            )
        )

    return analyses


def write_output(path: Path, analyses: list[CauseAnalysis]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(item.as_dict() for item in analyses)


def main() -> None:
    args = parse_args()
    analyses = analyze_deductions(
        read_rows(Path(args.deductions)),
        read_rows(Path(args.results)),
        read_rows(Path(args.queries)),
    )
    write_output(Path(args.output), analyses)
    counts: dict[str, int] = {}
    for item in analyses:
        counts[item.root_cause] = counts.get(item.root_cause, 0) + 1
    summary = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    print(f"stage35 deduction causes written: rows={len(analyses)} {summary}")


if __name__ == "__main__":
    main()
