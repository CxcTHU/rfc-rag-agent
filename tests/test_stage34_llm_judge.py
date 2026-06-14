from scripts.judge_stage34_generation_quality import (
    parse_judge_payload,
    sanitize_text,
    summarize,
)


def test_stage34_llm_judge_parses_scores_and_sanitizes_reason() -> None:
    parsed = parse_judge_payload(
        """```json
        {
          "faithfulness": 1.2,
          "answer_coverage": 0.7,
          "citation_support": 0.6,
          "refusal_correctness": 0.9,
          "conciseness": 0.8,
          "safety_leak_check": -1,
          "risk_level": "high",
          "short_reason": "ok raw_response Bearer sk-testsecret123456",
          "next_action": "review"
        }
        ```"""
    )

    assert parsed["faithfulness"] == "1.000"
    assert parsed["safety_leak_check"] == "0.000"
    assert parsed["risk_level"] == "high"
    assert "raw_response" not in parsed["short_reason"]
    assert "Bearer" not in parsed["short_reason"]
    assert "sk-testsecret123456" not in parsed["short_reason"]


def test_stage34_llm_judge_summary_marks_medium_review_required() -> None:
    summary = summarize(
        [
            {
                "status": "completed",
                "faithfulness": "0.8",
                "answer_coverage": "0.7",
                "citation_support": "0.9",
                "refusal_correctness": "1.0",
                "conciseness": "0.6",
                "safety_leak_check": "1.0",
                "risk_level": "medium",
            }
        ]
    )

    assert summary["completed_rows"] == "1"
    assert summary["avg_faithfulness"] == "0.800"
    assert summary["medium_risk_count"] == "1"
    assert summary["judge_quality_gate"] == "review_required"


def test_stage34_llm_judge_sanitize_text_removes_sensitive_markers() -> None:
    sanitized = sanitize_text("Authorization: abc Bearer secret reasoning_content raw_response")

    assert "Authorization" not in sanitized
    assert "Bearer" not in sanitized
    assert "reasoning_content" not in sanitized
    assert "raw_response" not in sanitized
