from scripts.tool_calling_eval_support import (
    parse_judge_payload,
    sanitize_text,
    source_summary,
)


def test_judge_payload_scores_and_sensitive_text_are_sanitized() -> None:
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


def test_sanitize_text_removes_sensitive_markers() -> None:
    sanitized = sanitize_text("Authorization: abc Bearer secret reasoning_content raw_response")
    assert "Authorization" not in sanitized
    assert "Bearer" not in sanitized
    assert "reasoning_content" not in sanitized
    assert "raw_response" not in sanitized


def test_source_summary_contains_only_short_sanitized_evidence() -> None:
    class FakeSource:
        source_id = 1
        title = "A" * 200
        source_type = "wikipedia"
        score = 0.9
        content = "short evidence raw_response"

    summary = source_summary(FakeSource())
    assert len(str(summary["title"])) <= 120
    assert "raw_response" not in str(summary["evidence_snippet"])
