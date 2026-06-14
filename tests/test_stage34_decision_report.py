from scripts.build_stage34_decision_report import build_decision


def test_stage34_decision_report_keeps_glm_on_small_jina_edge_latency_and_judge() -> None:
    decision = build_decision(
        embedding_rows=[
            {
                "candidate": "jina_baseline",
                "precision_at_1": "0.667",
                "precision_at_3": "0.800",
                "precision_at_5": "0.933",
                "avg_coverage_ratio": "0.670",
                "avg_latency_ms": "1374.06",
                "status": "completed",
                "decision": "keep_glm",
            }
        ],
        latency_rows=[
            {
                "group": "all",
                "dominant_bottleneck": "tool_iteration_overhead",
                "time_to_final_p50_ms": "19716.168",
                "time_to_final_p90_ms": "37965.768",
                "time_to_final_max_ms": "41736.279",
                "top_stage_by_share": "tool_latency_ms",
                "top_stage_share": "0.744",
            }
        ],
        judge_rows=[
            {
                "judge_quality_gate": "review_required",
                "completed_rows": "4",
                "avg_faithfulness": "0.925",
                "avg_answer_coverage": "0.675",
                "avg_citation_support": "0.613",
                "high_risk_count": "0",
                "medium_risk_count": "4",
            }
        ],
        stage30_rows=[{"overall_score": "83.17", "release_decision": "review_required"}],
    )

    assert decision["embedding_decision"] == "keep_glm"
    assert decision["latency_primary_bottleneck"] == "tool_iteration_overhead"
    assert decision["judge_quality_gate"] == "review_required"
    assert decision["submit_state"] == "uncommitted_waiting_for_user_manual_review"
    # Stage 34 successfully landed the Flash planner + V4-Pro answer combo,
    # so phase 35 plans the next architectural step (tool-calling protocol
    # migration) rather than rolling back.
    assert decision["phase35_recommendation"].startswith("phase35_should_")
    assert "keep_glm_default" in decision["phase35_recommendation"]
    assert "tool_calling" in decision["phase35_recommendation"]
    assert decision["chat_provider_next_action"].startswith("keep_flash_planner_pro_answer")
