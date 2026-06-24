import csv
from pathlib import Path

from scripts.evaluate_phase53_graphrag_ablation import (
    evaluate_dry_run,
    load_cases,
    summarize,
    write_csv,
)


def test_phase53_graphrag_eval_set_has_30_sanitized_cases() -> None:
    cases = load_cases(Path("data/evaluation/phase53_graphrag_queries.csv"))

    assert len(cases) == 30
    assert sum(1 for case in cases if case.expected_graph_intent) >= 20
    serialized = "\n".join(case.question for case in cases).casefold()
    for forbidden in ["api_key", "bearer", "raw_response", "reasoning_content"]:
        assert forbidden not in serialized


def test_phase53_graphrag_ablation_dry_run_outputs_sanitized_rows(tmp_path) -> None:
    cases = load_cases(Path("data/evaluation/phase53_graphrag_queries.csv"))
    results, ablation = evaluate_dry_run(cases)
    summary = summarize(results)

    assert len(results) == 30
    assert len(ablation) == 30
    assert any(row["graph_strategy"] == "graph_enhanced_search" for row in results)
    serialized = "\n".join(str(row) for row in [*results, *summary, *ablation]).casefold()
    assert "chunk content" not in serialized
    assert "raw_response" not in serialized

    output_path = tmp_path / "summary.csv"
    write_csv(output_path, summary)
    with output_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["metric"] == "total_cases"
    assert rows[0]["value"] == "30"
