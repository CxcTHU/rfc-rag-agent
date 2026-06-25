from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_BASELINE_SUMMARY = Path("data/evaluation/phase54_graphrag_eval_summary_real_api.csv")
DEFAULT_BASELINE_RESULTS = Path("data/evaluation/phase54_graphrag_eval_results_real_api.csv")
DEFAULT_C_SUMMARY = Path("data/evaluation/phase54_graphrag_eval_summary_reranker_bge.csv")
DEFAULT_C_RESULTS = Path("data/evaluation/phase54_graphrag_eval_results_reranker_bge.csv")
DEFAULT_OUTPUT = Path("data/evaluation/phase54_graphrag_eval_comparison_reranker_bge.csv")


KEY_METRICS = (
    "completed_rows",
    "error_rows",
    "formal_judge_scored_rows",
    "graph_intent_accuracy_delta",
    "graph_intent_completeness_delta",
    "graph_intent_citation_quality_delta",
    "ordinary_accuracy_delta",
    "negative_graph_false_positive_count",
    "same_top_chunk_count",
    "same_top_chunk_comparable_count",
    "formal_judge_gate_decision",
    "formal_judge_gate_reason",
)


def read_summary(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["metric"]: row["value"] for row in csv.DictReader(handle)}


def read_results(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def numeric_delta(baseline: str, candidate: str) -> str:
    try:
        return f"{float(candidate) - float(baseline):.4f}"
    except ValueError:
        return ""


def metric_rows(baseline: dict[str, str], candidate: dict[str, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for metric in KEY_METRICS:
        baseline_value = baseline.get(metric, "")
        candidate_value = candidate.get(metric, "")
        rows.append(
            {
                "section": "summary_metric",
                "item": metric,
                "baseline_reranker_disabled": baseline_value,
                "candidate_reranker_bge": candidate_value,
                "delta_candidate_minus_baseline": numeric_delta(baseline_value, candidate_value),
            }
        )
    return rows


def case_rows(baseline_rows: list[dict[str, str]], candidate_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    baseline_by_id = {row.get("case_id", ""): row for row in baseline_rows}
    rows: list[dict[str, str]] = []
    for candidate in candidate_rows:
        case_id = candidate.get("case_id", "")
        baseline = baseline_by_id.get(case_id, {})
        rows.append(
            {
                "section": "case_score_delta",
                "item": case_id,
                "baseline_reranker_disabled": baseline.get("category", candidate.get("category", "")),
                "candidate_reranker_bge": candidate.get("category", ""),
                "delta_candidate_minus_baseline": "|".join(
                    [
                        f"accuracy={numeric_delta(baseline.get('graph_accuracy', ''), candidate.get('graph_accuracy', ''))}",
                        f"completeness={numeric_delta(baseline.get('graph_completeness', ''), candidate.get('graph_completeness', ''))}",
                        f"citation={numeric_delta(baseline.get('graph_citation_quality', ''), candidate.get('graph_citation_quality', ''))}",
                    ]
                ),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "section",
                "item",
                "baseline_reranker_disabled",
                "candidate_reranker_bge",
                "delta_candidate_minus_baseline",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Phase 54 reranker-disabled vs GPU BGE reranker results.")
    parser.add_argument("--baseline-summary", default=str(DEFAULT_BASELINE_SUMMARY))
    parser.add_argument("--baseline-results", default=str(DEFAULT_BASELINE_RESULTS))
    parser.add_argument("--candidate-summary", default=str(DEFAULT_C_SUMMARY))
    parser.add_argument("--candidate-results", default=str(DEFAULT_C_RESULTS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    baseline_summary = read_summary(Path(args.baseline_summary))
    candidate_summary = read_summary(Path(args.candidate_summary))
    baseline_results = read_results(Path(args.baseline_results))
    candidate_results = read_results(Path(args.candidate_results))
    rows = metric_rows(baseline_summary, candidate_summary) + case_rows(baseline_results, candidate_results)
    write_csv(Path(args.output), rows)
    print(f"phase54_reranker_bge_comparison rows={len(rows)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
