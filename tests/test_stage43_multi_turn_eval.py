import csv
from pathlib import Path

from scripts.evaluate_stage43_multi_turn import (
    CASE_FIELDS,
    CASE_PATH,
    HISTORY_MODES,
    RESULT_FIELDS,
    group_cases,
    load_cases,
    make_dry_run_rows,
    merge_result_rows,
)


def test_stage43_multi_turn_case_set_covers_required_scenarios() -> None:
    rows = load_cases(CASE_PATH)
    grouped = group_cases(rows)
    scenarios = {}
    for case_id, turns in grouped.items():
        scenarios.setdefault(turns[0].scenario, set()).add(case_id)

    assert len(grouped) >= 16
    assert set(scenarios) == {
        "follow_up",
        "pronoun_ellipsis",
        "clarification",
        "topic_switch",
        "reference_previous_turn",
        "user_correction",
        "constrained_follow_up",
        "multi_turn_refusal",
    }
    assert all(len(case_ids) >= 2 for case_ids in scenarios.values())
    assert all(2 <= len(turns) <= 4 for turns in grouped.values())


def test_stage43_multi_turn_case_csv_schema_is_stable() -> None:
    with Path(CASE_PATH).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        assert reader.fieldnames == CASE_FIELDS

    for row in load_cases(CASE_PATH):
        assert row.case_id
        assert row.scenario
        assert row.user_question
        assert row.expected_answer_points
        assert row.expected_retrieval_anchors


def test_stage43_multi_turn_dry_run_rows_cover_all_history_modes() -> None:
    grouped = group_cases(load_cases(CASE_PATH))

    for history_mode in HISTORY_MODES:
        result_rows = make_dry_run_rows(
            grouped,
            history_mode=history_mode,
            recent_turns=4,
        )
        assert len(result_rows) == sum(len(turns) for turns in grouped.values())
        assert all(row["history_mode"] == history_mode for row in result_rows)
        assert all(row["status"] == "dry_run" for row in result_rows)
        assert all(row["retrieval_hit"] == "not_run" for row in result_rows)
        assert all(row["citation_support"] == "not_run" for row in result_rows)


def test_stage43_layered_memory_dry_run_uses_memory_slots() -> None:
    grouped = group_cases(load_cases(CASE_PATH))
    result_rows = make_dry_run_rows(
        grouped,
        history_mode="layered_memory",
        recent_turns=4,
    )

    second_turn_rows = [row for row in result_rows if row["turn_index"] == "2"]
    assert second_turn_rows
    assert any(row["memory_entities_used"] for row in second_turn_rows)
    assert any(row["retrieval_anchors_used"] for row in second_turn_rows)


def test_stage43_layered_memory_filters_stale_anchors_after_correction() -> None:
    grouped = group_cases(load_cases(CASE_PATH))
    result_rows = make_dry_run_rows(
        grouped,
        history_mode="layered_memory",
        recent_turns=4,
    )

    correction_turn = next(
        row
        for row in result_rows
        if row["case_id"] == "stage43_correction_02" and row["turn_index"] == "2"
    )

    stale_terms = (
        "\u65bd\u5de5\u8d28\u91cf",
        "\u8d28\u91cf\u63a7\u5236",
    )
    assert all(term not in correction_turn["retrieval_anchors_used"] for term in stale_terms)
    assert all(term not in correction_turn["planned_question"] for term in stale_terms)
    assert "\u88c2\u7eb9" in correction_turn["retrieval_anchors_used"]


def test_stage43_result_schema_does_not_store_raw_outputs() -> None:
    assert "planned_question" in RESULT_FIELDS
    assert "top_source_title" in RESULT_FIELDS
    forbidden = {
        "answer",
        "raw_answer",
        "raw_response",
        "reasoning_content",
        "api_key",
        "bearer_token",
        "chunk_content",
    }
    assert forbidden.isdisjoint(set(RESULT_FIELDS))


def test_stage43_single_mode_merge_preserves_existing_modes() -> None:
    existing_rows = [
        {field: "" for field in RESULT_FIELDS}
        | {
            "case_id": "case_a",
            "turn_index": "1",
            "history_mode": "no_history",
            "status": "completed",
        },
        {field: "" for field in RESULT_FIELDS}
        | {
            "case_id": "case_a",
            "turn_index": "1",
            "history_mode": "recent_only",
            "status": "completed",
        },
        {field: "" for field in RESULT_FIELDS}
        | {
            "case_id": "case_a",
            "turn_index": "1",
            "history_mode": "layered_memory",
            "status": "dry_run",
        },
    ]
    replacement_rows = [
        {field: "" for field in RESULT_FIELDS}
        | {
            "case_id": "case_a",
            "turn_index": "1",
            "history_mode": "layered_memory",
            "status": "completed",
        }
    ]

    merged = merge_result_rows(existing_rows, replacement_rows, ("layered_memory",))

    assert [row["history_mode"] for row in merged] == [
        "no_history",
        "recent_only",
        "layered_memory",
    ]
    assert [row["status"] for row in merged] == [
        "completed",
        "completed",
        "completed",
    ]
