"""Tests for the stage 37 Tool Calling Loop vs ReAct evaluation."""

from pathlib import Path

from scripts.evaluate_stage37_tool_calling_vs_react import (
    EVAL_CASES,
    REAL_RESULTS_PATH,
    REAL_SUMMARY_PATH,
    RESULT_FIELDS,
    RESULTS_PATH,
    SUMMARY_PATH,
    build_planner_provider,
    run_evaluation,
)


def test_stage37_eval_cases_cover_required_question_types() -> None:
    categories = {case.category for case in EVAL_CASES}

    assert "single_hop_definition" in categories
    assert "comparison" in categories
    assert "multi_dimensional" in categories
    assert "bilingual_terminology" in categories
    assert "followup" in categories
    assert "evidence_insufficient" in categories
    assert "off_topic_refusal" in categories
    assert "multi_hop_retrieval" in categories


def test_stage37_eval_writes_react_and_tool_calling_outputs(tmp_path: Path) -> None:
    rows, summary = run_evaluation(output_dir=tmp_path)

    assert len(rows) == len(EVAL_CASES) * 2
    assert (tmp_path / RESULTS_PATH.name).exists()
    assert (tmp_path / SUMMARY_PATH.name).exists()
    assert {row["mode"] for row in rows} == {"react_agent", "tool_calling_agent"}
    assert set(rows[0]) == set(RESULT_FIELDS)
    assert {row["run_type"] for row in rows} == {"deterministic"}

    summaries = {row["mode"]: row for row in summary}
    assert summaries["react_agent"]["errors"] == "0"
    assert summaries["tool_calling_agent"]["errors"] == "0"


def test_stage37_eval_tracks_required_comparison_metrics(tmp_path: Path) -> None:
    rows, _summary = run_evaluation(output_dir=tmp_path)
    tool_rows = [row for row in rows if row["mode"] == "tool_calling_agent"]

    assert all(row["llm_call_count"] for row in tool_rows)
    assert all(row["tool_call_count"] for row in tool_rows)
    assert all(row["iteration_count"] for row in tool_rows)
    assert all(row["time_to_final_ms"] for row in tool_rows)
    assert all(row["citation_count"] for row in tool_rows)
    assert all(row["source_count"] for row in tool_rows)
    assert all(row["same_refusal_as_react"] in {"true", "false"} for row in tool_rows)
    assert all(row["same_top_source_as_react"] in {"true", "false"} for row in tool_rows)
    assert all(row["repeated_query_count"] for row in tool_rows)
    assert all(row["near_duplicate_query_count"] for row in tool_rows)
    assert all(row["executed_tool_call_count"] for row in tool_rows)
    assert all(row["skipped_tool_call_count"] for row in tool_rows)
    assert all(row["citation_repair_count"] for row in tool_rows)
    assert any(
        int(row["tool_call_count"]) >= 2
        for row in tool_rows
        if row["category"] == "multi_hop_retrieval"
    )
    assert any(
        row["refused"] == "true"
        for row in tool_rows
        if row["category"] == "off_topic_refusal"
    )


def test_stage37_eval_outputs_do_not_include_sensitive_raw_content(tmp_path: Path) -> None:
    run_evaluation(output_dir=tmp_path)

    serialized = "\n".join(
        path.read_text(encoding="utf-8") for path in tmp_path.glob("*.csv")
    ).lower()
    assert "api key" not in serialized
    assert "authorization" not in serialized
    assert "bearer" not in serialized
    assert "raw_response" not in serialized
    assert "reasoning_content" not in serialized
    assert "hidden thought" not in serialized


def test_stage37_eval_defines_real_provider_output_paths() -> None:
    assert REAL_RESULTS_PATH.name == "stage37_tool_calling_vs_react_real_results.csv"
    assert REAL_SUMMARY_PATH.name == "stage37_tool_calling_vs_react_real_summary.csv"


def test_stage37_real_provider_requires_planner_provider() -> None:
    class SettingsWithoutPlanner:
        planner_chat_model_provider = ""

    try:
        build_planner_provider(SettingsWithoutPlanner())
    except ValueError as exc:
        assert "planner chat provider" in str(exc)
    else:
        raise AssertionError("real-provider comparison should require planner provider")
