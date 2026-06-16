"""Analyze Stage 38 structured final-answer citation-support gaps.

The script is offline and reads only the Stage 38 Judge CSV. It classifies
low-citation rows by comparing ``structured_final_answer`` against ``baseline``:

- prompt_citation_gap: baseline citation support passed but structured failed.
- retrieval_or_repair_gap: both strategies failed citation support.
- refusal_judge_artifact: expected-refusal rows where missing citations are not
  an answer-generation citation gap.
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Mapping, Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "evaluation" / "stage38_tool_calling_judge_results.csv"
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "stage38_citation_gap_analysis.csv"

FIELDS = [
    "query_id",
    "category",
    "structured_answer_coverage",
    "structured_citation_support",
    "baseline_answer_coverage",
    "baseline_citation_support",
    "structured_citation_count",
    "structured_source_count",
    "baseline_citation_count",
    "baseline_source_count",
    "root_cause",
    "evidence_note",
    "recommended_action",
]


def main() -> None:
    args = parse_args()
    rows = analyze(read_rows(Path(args.input)), threshold=args.threshold)
    write_csv(Path(args.output), rows)
    print(
        f"stage38 citation gap analysis rows={len(rows)} "
        f"threshold={args.threshold:.3f}"
    )
    for root_cause in sorted({row["root_cause"] for row in rows}):
        count = sum(1 for row in rows if row["root_cause"] == root_cause)
        print(f"  {root_cause}: {count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Stage 38 citation gaps.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--threshold", type=float, default=0.8)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def analyze(
    rows: Sequence[Mapping[str, str]],
    *,
    threshold: float = 0.8,
) -> list[dict[str, str]]:
    by_query_strategy: dict[tuple[str, str], Mapping[str, str]] = {
        (row["query_id"], row["strategy"]): row
        for row in rows
        if row.get("status") == "completed"
    }
    query_ids = sorted({row["query_id"] for row in rows})
    analysis_rows: list[dict[str, str]] = []
    for query_id in query_ids:
        structured = by_query_strategy.get((query_id, "structured_final_answer"))
        baseline = by_query_strategy.get((query_id, "baseline"))
        if not structured or not baseline:
            continue
        structured_cit = score(structured, "citation_support")
        if structured_cit >= threshold:
            continue
        baseline_cit = score(baseline, "citation_support")
        root_cause = classify_gap(
            structured=structured,
            baseline=baseline,
            threshold=threshold,
        )
        evidence_note = evidence_note_for(
            structured=structured,
            baseline=baseline,
            threshold=threshold,
        )
        analysis_rows.append(
            {
                "query_id": query_id,
                "category": structured.get("category", ""),
                "structured_answer_coverage": structured.get("answer_coverage", ""),
                "structured_citation_support": structured.get("citation_support", ""),
                "baseline_answer_coverage": baseline.get("answer_coverage", ""),
                "baseline_citation_support": baseline.get("citation_support", ""),
                "structured_citation_count": structured.get("citation_count", ""),
                "structured_source_count": structured.get("source_count", ""),
                "baseline_citation_count": baseline.get("citation_count", ""),
                "baseline_source_count": baseline.get("source_count", ""),
                "root_cause": root_cause,
                "evidence_note": evidence_note,
                "recommended_action": recommended_action(root_cause, baseline_cit),
            }
        )
    return analysis_rows


def classify_gap(
    *,
    structured: Mapping[str, str],
    baseline: Mapping[str, str],
    threshold: float,
) -> str:
    if structured.get("expected_refused") == "true" and structured.get("refused") == "true":
        return "refusal_judge_artifact"
    baseline_cit = score(baseline, "citation_support")
    if baseline_cit >= threshold:
        return "prompt_citation_gap"
    return "retrieval_or_repair_gap"


def evidence_note_for(
    *,
    structured: Mapping[str, str],
    baseline: Mapping[str, str],
    threshold: float,
) -> str:
    baseline_cit = score(baseline, "citation_support")
    structured_cit = score(structured, "citation_support")
    if structured.get("expected_refused") == "true" and structured.get("refused") == "true":
        return "expected refusal; Judge citation score is not sentence-level answer evidence"
    if baseline_cit >= threshold > structured_cit:
        return "baseline passed citation support on same query, so retrieved evidence is likely sufficient"
    return "both strategies missed citation support; inspect retrieval evidence or repair behavior"


def recommended_action(root_cause: str, baseline_cit: float) -> str:
    if root_cause == "prompt_citation_gap":
        return "tighten structured_final_answer sentence-level citation instructions"
    if root_cause == "refusal_judge_artifact":
        return "document separately; do not tune retrieval for expected refusal"
    if baseline_cit < 0.5:
        return "inspect retrieval evidence and citation repair before prompt-only tuning"
    return "inspect citation repair and source coverage; prompt-only fix may be insufficient"


def score(row: Mapping[str, str], field: str) -> float:
    try:
        return float(row.get(field, "") or 0.0)
    except ValueError:
        return 0.0


def write_csv(path: Path, rows: Sequence[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
