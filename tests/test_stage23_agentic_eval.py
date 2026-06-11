"""Tests for the stage 23 deterministic agentic evaluation."""

from pathlib import Path

from scripts.evaluate_stage23_agentic_auto_routing import (
    DECISION_PATH,
    EVAL_CASES,
    RESULTS_PATH,
    SUMMARY_PATH,
    run_evaluation,
)


def test_stage23_eval_cases_cover_simple_complex_and_refusal() -> None:
    categories = {case.category for case in EVAL_CASES}

    assert "simple_concept" in categories
    assert "complex_compare" in categories
    assert "complex_multi_evidence" in categories
    assert "refusal" in categories
    assert any(case.expected_agentic_gain for case in EVAL_CASES)


def test_stage23_deterministic_eval_writes_reliable_outputs(tmp_path: Path) -> None:
    rows, summary, decision = run_evaluation(output_dir=tmp_path)

    assert len(rows) == len(EVAL_CASES)
    assert (tmp_path / RESULTS_PATH.name).exists()
    assert (tmp_path / SUMMARY_PATH.name).exists()
    assert (tmp_path / DECISION_PATH.name).exists()
    assert decision["decision"] == "reliable_auto_route_candidate"
    assert float(decision["default_error_rate"]) < 0.10
    assert float(decision["agentic_error_rate"]) < 0.10
    assert int(decision["agentic_gain_count"]) >= 1

    methods = {row["method"]: row for row in summary}
    assert methods["default_agent_service"]["errors"] == "0"
    assert methods["agentic_langgraph"]["errors"] == "0"


def test_stage23_eval_outputs_do_not_include_secrets(tmp_path: Path) -> None:
    run_evaluation(output_dir=tmp_path)

    serialized = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.glob("*.csv")).lower()
    assert "api_key" not in serialized
    assert "bearer" not in serialized
    assert "authorization" not in serialized
