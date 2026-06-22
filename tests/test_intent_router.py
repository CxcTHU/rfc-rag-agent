from app.services.agent.intent_router import (
    classify_conversation_intent,
    classify_meta_intent,
    is_followup_transform_request,
    strip_assistant_history_prefix,
)


def test_intent_router_covers_stage36_eight_intent_regression_set() -> None:
    cases = {
        "上一轮翻译": ("Translate that into Chinese.", "followup_transform"),
        "追问转述": ("把刚才答案改成要点", "followup_transform"),
        "问来源": ("请检索 filling capacity 相关资料", "domain_or_search"),
        "问模型": ("What model are you using?", "agent_meta"),
        "问为什么拒答": ("刚才为什么拒答？", "refusal_explanation"),
        "闲聊": ("你好", "domain_or_search"),
        "off-topic": ("How should I cook pasta?", "domain_or_search"),
        "正常领域问答": ("What affects filling capacity in rock-filled concrete?", "domain_or_search"),
    }

    for _label, (question, expected_intent) in cases.items():
        assert classify_conversation_intent(question) == expected_intent


def test_intent_router_meta_intents_are_stable() -> None:
    assert classify_meta_intent("你用的模型是什么？") == "agent_meta"
    assert classify_meta_intent("你能做什么？") == "capability_help"
    assert classify_meta_intent("why did you refuse?") == "refusal_explanation"
    assert classify_meta_intent("堆石混凝土填充能力") is None


def test_intent_router_followup_transform_is_short_or_pronoun_bound() -> None:
    assert is_followup_transform_request("Translate that into Chinese.")
    assert not is_followup_transform_request("\u8bf7\u8be6\u7ec6\u56de\u7b54")
    assert not is_followup_transform_request("\u5c55\u5f00\u8bf4")
    assert is_followup_transform_request("把刚才答案整理成表格")
    assert not is_followup_transform_request(
        "answer in Chinese and also search a new long technical question "
        "about rock filled concrete dam thermal control under seismic load and "
        "construction method for hydraulic engineering case review"
    )


def test_intent_router_strips_assistant_history_prefix() -> None:
    assert strip_assistant_history_prefix("Assistant: hello") == "hello"
    assert strip_assistant_history_prefix("助手：你好") == "你好"
    assert strip_assistant_history_prefix("User: hello") is None
