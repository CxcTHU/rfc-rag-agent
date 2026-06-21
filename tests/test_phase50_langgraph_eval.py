from pathlib import Path

from scripts.evaluate_phase50_langgraph_vs_react import (
    EVAL_CASES,
    RESULT_FIELDS,
    RESULTS_PATH,
    SUMMARY_PATH,
    run_evaluation,
)


def test_phase50_eval_cases_cover_agent_routes() -> None:
    categories = {case.category for case in EVAL_CASES}

    assert "knowledge_search" in categories
    assert "comparison" in categories
    assert "table_search" in categories
    assert "figure_search" in categories
    assert "followup" in categories
    assert "off_topic_refusal" in categories


def test_phase50_eval_writes_react_and_langgraph_outputs(tmp_path: Path) -> None:
    rows, summary = run_evaluation(output_dir=tmp_path)

    assert len(rows) == len(EVAL_CASES) * 2
    assert (tmp_path / RESULTS_PATH.name).exists()
    assert (tmp_path / SUMMARY_PATH.name).exists()
    assert {row["mode"] for row in rows} == {"react_agent", "langgraph_agent"}
    assert set(rows[0]) == set(RESULT_FIELDS)
    assert {row["run_type"] for row in rows} == {"deterministic"}

    summaries = {row["mode"]: row for row in summary}
    assert summaries["react_agent"]["errors"] == "0"
    assert summaries["langgraph_agent"]["errors"] == "0"
    assert summaries["langgraph_agent"]["same_refusal_as_react"].endswith(
        f"/{len(EVAL_CASES)}"
    )


def test_phase50_eval_tracks_cache_and_checkpoint_metrics(tmp_path: Path) -> None:
    rows, _summary = run_evaluation(output_dir=tmp_path)
    langgraph_rows = [row for row in rows if row["mode"] == "langgraph_agent"]

    assert all(row["tool_call_count"] for row in langgraph_rows)
    assert all(row["iteration_count"] for row in langgraph_rows)
    assert all(row["time_to_final_ms"] for row in langgraph_rows)
    assert all(row["same_refusal_as_react"] in {"true", "false"} for row in langgraph_rows)
    assert all(row["same_top_source_as_react"] in {"true", "false"} for row in langgraph_rows)
    assert all(row["langgraph_checkpointer_backend"] for row in langgraph_rows)


def test_phase50_eval_outputs_do_not_include_sensitive_raw_content(tmp_path: Path) -> None:
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
