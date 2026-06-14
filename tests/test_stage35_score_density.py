from scripts.analyze_stage35_score_density import build_density_rows


def test_stage35_score_density_marks_distributed_gap_when_no_single_item_is_enough() -> None:
    rows = build_density_rows(
        {"overall_score": "84.40"},
        [
            {"query_id": "q1", "dimension": "retrieval_quality", "deduction_points": "2.00"},
            {"query_id": "q2", "dimension": "rule_based_context_answer_quality", "deduction_points": "2.00"},
            {"query_id": "q2", "dimension": "retrieval_quality", "deduction_points": "2.00"},
        ],
        target_score=88.0,
    )

    overall = next(row for row in rows if row["scope"] == "overall_gap")
    q2 = next(row for row in rows if row["scope"] == "query_total" and row["query_id"] == "q2")

    assert overall["points_needed_to_target"] == "3.60"
    assert overall["deduction_points"] == "6.00"
    assert overall["recommended_priority"] == "recorded_deductions_can_cover_gap_if_recovered"
    assert q2["deduction_points"] == "4.00"
    assert q2["enough_if_fully_recovered"] == "true"


def test_stage35_score_density_flags_metric_ceiling_when_deductions_cannot_cover_gap() -> None:
    rows = build_density_rows(
        {"overall_score": "83.00"},
        [{"query_id": "q1", "dimension": "retrieval_quality", "deduction_points": "2.00"}],
        target_score=88.0,
    )

    overall = next(row for row in rows if row["scope"] == "overall_gap")

    assert overall["points_needed_to_target"] == "5.00"
    assert overall["deduction_points"] == "2.00"
    assert overall["enough_if_fully_recovered"] == "false"
    assert overall["recommended_priority"] == (
        "recorded_deductions_cannot_explain_gap; inspect scoring formula and aggregate metric ceilings"
    )
