from app.services.agent.chitchat import detect_chitchat, normalize_chitchat_text


def test_detect_chitchat_supports_social_intents() -> None:
    examples = {
        "你好！": "greeting",
        "谢谢": "thanks",
        "bye": "goodbye",
        "好的": "acknowledgment",
        "你能做什么？": "help",
    }

    for question, expected_intent in examples.items():
        result = detect_chitchat(question)
        assert result is not None
        assert result.intent == expected_intent
        assert result.answer
        assert "不调用检索或模型" in result.reasoning_summary


def test_detect_chitchat_ignores_domain_questions() -> None:
    assert detect_chitchat("What affects filling capacity?") is None
    assert detect_chitchat("检索 堆石混凝土 温控 相关资料") is None


def test_normalize_chitchat_text_compacts_case_and_punctuation() -> None:
    assert normalize_chitchat_text("  Thank you! ") == "thankyou"
    assert normalize_chitchat_text("好 的。") == "好的"
