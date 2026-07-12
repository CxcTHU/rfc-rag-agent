import pytest

from scripts.evaluate_stage38_tool_calling_quality import (
    EVAL_CASES,
    REAL_RESULTS_PATH,
    REAL_SUMMARY_PATH,
    RESULT_FIELDS,
    RESULTS_PATH,
    SUMMARY_PATH,
    run_evaluation,
)


@pytest.fixture(scope="module")
def deterministic_evaluation(tmp_path_factory: pytest.TempPathFactory):
    output_dir = tmp_path_factory.mktemp("stage38_evaluation")
    rows, summary = run_evaluation(output_dir=output_dir)
    return output_dir, rows, summary


def test_stage38_eval_expands_case_count_and_categories() -> None:
    categories = {case.category for case in EVAL_CASES}

    assert 20 <= len(EVAL_CASES) <= 30
    assert len(categories) >= 11
    for category in {
        "single_hop",
        "comparison",
        "multi_dimensional",
        "multi_hop",
        "numeric_comparison",
        "bilingual",
        "long_question",
        "ambiguous_query",
        "followup",
        "evidence_insufficient",
        "off_topic",
        "responsibility_boundary",
        "citation_repair",
        "evidence_convergence",
        "skip_tool",
        "duplicate_tool_call",
    }:
        assert category in categories


def test_stage38_eval_writes_stage38_outputs(deterministic_evaluation) -> None:
    output_dir, rows, summary = deterministic_evaluation

    assert len(rows) == len(EVAL_CASES) * 2
    assert (output_dir / RESULTS_PATH.name).exists()
    assert (output_dir / SUMMARY_PATH.name).exists()
    assert {row["mode"] for row in rows} == {"react_agent", "tool_calling_agent"}
    assert set(rows[0]) == set(RESULT_FIELDS)
    assert {row["run_type"] for row in rows} == {"deterministic"}

    summaries = {row["mode"]: row for row in summary}
    assert summaries["react_agent"]["total"] == str(len(EVAL_CASES))
    assert summaries["tool_calling_agent"]["total"] == str(len(EVAL_CASES))


def test_stage38_eval_tracks_tool_calling_edge_metrics(deterministic_evaluation) -> None:
    _output_dir, rows, _summary = deterministic_evaluation
    tool_rows = [row for row in rows if row["mode"] == "tool_calling_agent"]
    by_category = {row["category"]: row for row in tool_rows}

    assert int(by_category["skip_tool"]["skipped_tool_call_count"]) >= 1
    assert int(by_category["duplicate_tool_call"]["executed_tool_call_count"]) == 1
    assert int(by_category["duplicate_tool_call"]["near_duplicate_query_count"]) == 0
    assert int(by_category["duplicate_tool_call"]["llm_call_count"]) == 2
    assert int(by_category["evidence_convergence"]["executed_tool_call_count"]) >= 1
    assert all(row["llm_call_count"] for row in tool_rows)
    assert all(row["tool_call_count"] for row in tool_rows)
    assert all(row["citation_count"] for row in tool_rows)
    assert all(row["same_refusal_as_react"] in {"true", "false"} for row in tool_rows)


def test_stage38_eval_outputs_do_not_include_sensitive_raw_content(
    deterministic_evaluation,
) -> None:
    output_dir, _rows, _summary = deterministic_evaluation

    serialized = "\n".join(
        path.read_text(encoding="utf-8") for path in output_dir.glob("*.csv")
    ).lower()
    assert "api key" not in serialized
    assert "authorization" not in serialized
    assert "bearer" not in serialized
    assert "raw_response" not in serialized
    assert "reasoning_content" not in serialized
    assert "hidden thought" not in serialized


def test_stage38_real_provider_output_paths_are_separate_from_stage37() -> None:
    assert RESULTS_PATH.name == "stage38_tool_calling_quality_results.csv"
    assert SUMMARY_PATH.name == "stage38_tool_calling_quality_summary.csv"
    assert REAL_RESULTS_PATH.name == "stage38_tool_calling_quality_real_results.csv"
    assert REAL_SUMMARY_PATH.name == "stage38_tool_calling_quality_real_summary.csv"
