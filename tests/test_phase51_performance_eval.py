from __future__ import annotations

import csv

from scripts.evaluate_phase51_performance import (
    EVAL_CONFIGS,
    RESULT_FIELDS,
    parse_config_ids,
    run_evaluation,
)


def test_phase51_eval_configs_cover_required_matrix() -> None:
    assert [config.config_id for config in EVAL_CONFIGS] == [
        "brain_baseline",
        "react_agent",
        "tool_calling_agent",
        "langgraph_deterministic",
        "langgraph_flash_planner",
        "langgraph_faiss_fallback",
        "semantic_cache_hit",
    ]


def test_phase51_performance_dry_run_writes_safe_csv(tmp_path) -> None:
    rows, summary = run_evaluation(output_dir=tmp_path, limit=2)

    assert len(rows) == 14
    assert len(summary) == len(EVAL_CONFIGS)
    assert {row["config_id"] for row in rows} == {config.config_id for config in EVAL_CONFIGS}
    assert any(row["semantic_cache_hit"] == "true" for row in rows)
    assert all("raw_response" not in row["error_summary"] for row in rows)

    results_path = tmp_path / "phase51_performance_results.csv"
    summary_path = tmp_path / "phase51_performance_summary.csv"
    assert results_path.exists()
    assert summary_path.exists()

    with results_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == RESULT_FIELDS
        persisted = list(reader)
    assert len(persisted) == len(rows)


def test_phase51_config_filter_preserves_other_existing_rows(tmp_path) -> None:
    run_evaluation(output_dir=tmp_path, limit=1)

    rows, summary = run_evaluation(
        output_dir=tmp_path,
        limit=1,
        config_ids={"langgraph_deterministic"},
    )

    assert len(rows) == len(EVAL_CONFIGS)
    assert {row["config_id"] for row in rows} == {config.config_id for config in EVAL_CONFIGS}
    assert {row["config_id"] for row in summary} == {config.config_id for config in EVAL_CONFIGS}


def test_phase51_parse_config_ids_accepts_repeated_and_comma_separated_values() -> None:
    assert parse_config_ids(["langgraph_deterministic,langgraph_flash_planner"]) == {
        "langgraph_deterministic",
        "langgraph_flash_planner",
    }
