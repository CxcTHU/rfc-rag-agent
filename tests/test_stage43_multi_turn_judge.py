import json

from scripts.evaluate_stage43_multi_turn import CASE_PATH, load_cases
from scripts.judge_stage43_multi_turn_quality import (
    RESULT_FIELDS,
    SENSITIVE_FIELD_NAMES,
    Stage43JudgeCase,
    build_judge_cases,
    dry_run_row,
    judge_payload,
    merge_result_rows,
    parse_stage43_judge_payload,
)


def test_stage43_judge_builds_all_history_modes() -> None:
    cases = build_judge_cases(load_cases(CASE_PATH), history_mode="all", recent_turns=4)

    assert len(cases) == 32 * 4
    assert {case.history_mode for case in cases} == {
        "no_history",
        "recent_only",
        "summary_recent",
        "layered_memory",
    }
    assert all(case.expected_answer_points for case in cases)


def test_stage43_judge_dry_run_has_no_scores_or_raw_outputs() -> None:
    case = build_judge_cases(load_cases(CASE_PATH), history_mode="layered_memory", recent_turns=4)[0]
    row = dry_run_row("2026-06-17T00:00:00+00:00", case, "judge", "model")

    assert row["status"] == "dry_run"
    assert row["answer_provider"] == "not_run"
    assert row["answer_faithfulness"] == ""
    assert SENSITIVE_FIELD_NAMES.isdisjoint({field.casefold() for field in RESULT_FIELDS})


def test_stage43_judge_payload_is_sanitized_and_bounded() -> None:
    class Result:
        answer = "Answer with raw_response and Bearer abcdefghijklmnop " * 20
        refused = False
        refusal_reason = ""
        citations = [1]
        sources = []

    case = Stage43JudgeCase(
        case_id="case",
        scenario="follow_up",
        turn_index=2,
        question="What about it?",
        history_mode="layered_memory",
        history=("sk-secret-token should be redacted",),
        expected_refused=False,
        expected_answer_points=("point",),
        expected_source_terms=("source",),
    )
    answer = type("Answer", (), {"result": Result(), "provider": "p", "model_name": "m"})()

    payload = judge_payload(case, answer)
    serialized = json.dumps(payload, ensure_ascii=False)

    assert "raw_response" not in serialized
    assert "Bearer" not in serialized
    assert "sk-secret-token" not in serialized
    assert len(payload["answer_summary"]) <= 700


def test_stage43_judge_parser_normalizes_scores() -> None:
    parsed = parse_stage43_judge_payload(
        json.dumps(
            {
                "answer_faithfulness": 1.2,
                "citation_accuracy": 0.7,
                "context_coherence": 0.8,
                "refusal_consistency": -1,
                "risk_level": "LOW",
                "short_reason": "ok",
                "next_action": "review",
            }
        )
    )

    assert parsed["answer_faithfulness"] == "1.000"
    assert parsed["refusal_consistency"] == "0.000"
    assert parsed["risk_level"] == "low"


def test_stage43_judge_single_mode_merge_preserves_other_modes() -> None:
    existing = [
        {field: "" for field in RESULT_FIELDS}
        | {"history_mode": "summary_recent", "case_id": "case_a", "turn_index": "1", "status": "completed"},
        {field: "" for field in RESULT_FIELDS}
        | {"history_mode": "layered_memory", "case_id": "case_a", "turn_index": "1", "status": "dry_run"},
    ]
    replacement = [
        {field: "" for field in RESULT_FIELDS}
        | {"history_mode": "layered_memory", "case_id": "case_a", "turn_index": "1", "status": "completed"}
    ]

    merged = merge_result_rows(existing, replacement, replacement_mode="layered_memory")

    assert [row["history_mode"] for row in merged] == ["summary_recent", "layered_memory"]
    assert [row["status"] for row in merged] == ["completed", "completed"]
