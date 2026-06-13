"""Tests for the stage 32 deterministic ReAct evaluation."""

from pathlib import Path

from scripts.evaluate_stage32_react_agent import (
    EVAL_CASES,
    RESULTS_PATH,
    SUMMARY_PATH,
    run_evaluation,
)


def test_stage32_eval_cases_cover_retrieval_rewrite_multi_evidence_and_refusal() -> None:
    categories = {case.category for case in EVAL_CASES}

    assert "direct_retrieval" in categories
    assert "rewrite_then_retrieve" in categories
    assert "multi_evidence" in categories
    assert "refusal" in categories
    assert any(case.expected_refused for case in EVAL_CASES)


def test_stage32_deterministic_eval_writes_three_mode_outputs(tmp_path: Path) -> None:
    rows, summary = run_evaluation(output_dir=tmp_path)

    assert len(rows) == len(EVAL_CASES) * 3
    assert (tmp_path / RESULTS_PATH.name).exists()
    assert (tmp_path / SUMMARY_PATH.name).exists()

    modes = {row["mode"] for row in rows}
    assert modes == {"default", "agentic_langgraph", "react_agent"}

    summaries = {row["mode"]: row for row in summary}
    assert summaries["default"]["errors"] == "0"
    assert summaries["agentic_langgraph"]["errors"] == "0"
    assert summaries["react_agent"]["errors"] == "0"
    assert summaries["react_agent"]["decision"] == "pass"


def test_stage32_react_rows_track_tools_iterations_and_refusals(tmp_path: Path) -> None:
    rows, _summary = run_evaluation(output_dir=tmp_path)

    react_rows = [row for row in rows if row["mode"] == "react_agent"]
    assert all(int(row["iteration_count"]) >= 1 for row in react_rows)
    assert all(int(row["workflow_step_count"]) >= 1 for row in react_rows)
    assert any(int(row["tool_count"]) >= 1 for row in react_rows)
    assert all(row["citation_valid"] == "true" for row in react_rows)

    refusal_row = next(row for row in react_rows if row["expected_refused"] == "true")
    assert refusal_row["refusal_match"] == "true"


def test_stage32_eval_outputs_do_not_include_secrets(tmp_path: Path) -> None:
    run_evaluation(output_dir=tmp_path)

    serialized = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.glob("*.csv")).lower()
    assert "secret" not in serialized
    assert "credential" not in serialized
    assert "sensitive" not in serialized
