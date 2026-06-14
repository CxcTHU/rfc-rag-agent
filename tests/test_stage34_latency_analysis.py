from scripts.analyze_stage34_latency_bottlenecks import (
    average_stage_shares,
    build_summaries,
    percentile,
)


def test_stage34_latency_analysis_builds_summary_with_p90_and_bottleneck() -> None:
    rows = [
        {
            "mode": "default",
            "status": "completed",
            "time_to_final_ms": "100",
            "primary_bottleneck": "answer_generation_latency",
            "answer_latency_ms": "80",
            "tool_latency_ms": "80",
        },
        {
            "mode": "react_agent",
            "status": "completed",
            "time_to_final_ms": "200",
            "primary_bottleneck": "planner_latency",
            "planner_latency_ms": "120",
        },
    ]

    summaries = build_summaries(rows)
    all_summary = summaries[0]

    assert all_summary["group"] == "all"
    assert all_summary["completed_count"] == 2
    assert all_summary["time_to_final_p50_ms"] == "150.000"
    assert all_summary["time_to_final_p90_ms"] == "190.000"
    assert all_summary["dominant_bottleneck"] in {
        "answer_generation_latency",
        "planner_latency",
    }


def test_stage34_latency_analysis_stage_share_uses_final_latency_denominator() -> None:
    shares = average_stage_shares(
        [
            {
                "time_to_final_ms": "100",
                "answer_latency_ms": "25",
                "planner_latency_ms": "50",
            }
        ]
    )

    assert shares["answer_latency_ms"] == 0.25
    assert shares["planner_latency_ms"] == 0.5


def test_stage34_latency_analysis_percentile_handles_empty_and_singleton() -> None:
    assert percentile([], 90) == 0.0
    assert percentile([42.0], 90) == 42.0
