from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CASES = Path("data/evaluation/phase53_graphrag_queries.csv")
DEFAULT_RESULTS = Path("data/evaluation/phase53_graphrag_ablation_results.csv")
DEFAULT_SUMMARY = Path("data/evaluation/phase53_graphrag_ablation_summary.csv")
DEFAULT_ABLATION = Path("data/evaluation/phase53_graphrag_ablation.csv")


@dataclass(frozen=True)
class GraphRAGEvalCase:
    case_id: str
    category: str
    question: str
    expected_graph_intent: bool
    expected_entities: str
    expected_relation_focus: str


def load_cases(path: Path) -> list[GraphRAGEvalCase]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return [
            GraphRAGEvalCase(
                case_id=row["case_id"],
                category=row["category"],
                question=row["question"],
                expected_graph_intent=row["expected_graph_intent"].casefold() == "true",
                expected_entities=row["expected_entities"],
                expected_relation_focus=row["expected_relation_focus"],
            )
            for row in reader
        ]


def evaluate_dry_run(cases: list[GraphRAGEvalCase]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    result_rows: list[dict[str, str]] = []
    ablation_rows: list[dict[str, str]] = []
    for case in cases:
        baseline_strategy = "hybrid_knowledge_search"
        graph_strategy = "graph_enhanced_search" if case.expected_graph_intent else "hybrid_knowledge_search"
        graph_expected_win = case.expected_graph_intent
        result_rows.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "status": "dry_run",
                "baseline_strategy": baseline_strategy,
                "graph_strategy": graph_strategy,
                "expected_graph_intent": str(case.expected_graph_intent).lower(),
                "expected_relation_focus": case.expected_relation_focus,
                "baseline_top_source_id": "",
                "graph_top_source_id": "",
                "graph_candidate_chunk_count": "",
                "graph_expected_win": str(graph_expected_win).lower(),
                "error": "",
            }
        )
        ablation_rows.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "baseline": baseline_strategy,
                "graph_enhanced": graph_strategy,
                "expected_delta": "graph_needed" if graph_expected_win else "no_graph_required",
            }
        )
    return result_rows, ablation_rows


def summarize(result_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    total = len(result_rows)
    graph_intent = sum(1 for row in result_rows if row["expected_graph_intent"] == "true")
    dry_run = sum(1 for row in result_rows if row["status"] == "dry_run")
    return [
        {
            "metric": "total_cases",
            "value": str(total),
        },
        {
            "metric": "graph_intent_cases",
            "value": str(graph_intent),
        },
        {
            "metric": "baseline_intent_cases",
            "value": str(total - graph_intent),
        },
        {
            "metric": "dry_run_rows",
            "value": str(dry_run),
        },
        {
            "metric": "safety_boundary",
            "value": "derived_counts_and_labels_only_no_chunk_bodies_no_provider_payloads",
        },
    ]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Phase 53 GraphRAG ablation design.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--results-output", default=str(DEFAULT_RESULTS))
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--ablation-output", default=str(DEFAULT_ABLATION))
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Reserved for a future real-corpus run. Default dry-run writes sanitized ablation design rows.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.execute:
        raise SystemExit(
            "--execute is not enabled in Phase 53G closeout; run retrieval integration through focused tests."
        )
    cases = load_cases(Path(args.cases))
    result_rows, ablation_rows = evaluate_dry_run(cases)
    write_csv(Path(args.results_output), result_rows)
    write_csv(Path(args.summary_output), summarize(result_rows))
    write_csv(Path(args.ablation_output), ablation_rows)
    print(
        "phase53_graphrag_ablation "
        f"cases={len(cases)} results={args.results_output} summary={args.summary_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
