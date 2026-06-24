from pathlib import Path

from scripts.evaluate_phase52_memory import evaluate_cases, load_cases, write_results


def test_phase52_memory_eval_cases_pass() -> None:
    cases = load_cases(Path("data/evaluation/phase52_memory_regression_cases.csv"))

    results, summary = evaluate_cases(cases)

    assert summary["case_count"] == 32
    assert summary["fail_count"] == 0
    assert summary["long_term_enabled_count"] == 0
    assert summary["memory_citation_source_true_count"] == 0
    assert {row["status"] for row in results} == {"pass"}


def test_phase52_memory_eval_writes_sanitized_outputs(tmp_path) -> None:
    cases = load_cases(Path("data/evaluation/phase52_memory_regression_cases.csv"))
    results, summary = evaluate_cases(cases)
    results_path = tmp_path / "results.csv"
    summary_path = tmp_path / "summary.csv"

    write_results(results, summary, results_path=results_path, summary_path=summary_path)

    text = results_path.read_text(encoding="utf-8") + summary_path.read_text(encoding="utf-8")
    assert "raw_response" not in text
    assert "reasoning_content" not in text
    assert "api key" not in text.casefold()
