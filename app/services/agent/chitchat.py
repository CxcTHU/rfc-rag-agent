import re
from dataclasses import dataclass
from typing import Literal


ChitchatIntent = Literal[
    "greeting",
    "thanks",
    "goodbye",
    "acknowledgment",
    "help",
]


@dataclass(frozen=True)
class ChitchatResult:
    intent: ChitchatIntent
    answer: str
    reasoning_summary: str


CHITCHAT_RESPONSES: dict[ChitchatIntent, str] = {
    "greeting": (
        "你好，我是堆石混凝土资料库 Agent。你可以问我堆石混凝土的概念、"
        "施工工艺、水化热、充填性能、工程案例，或让我检索相关资料。"
    ),
    "thanks": "不客气。你可以继续追问某个概念、工程案例，或让我检索相关资料。",
    "goodbye": "再见。下次需要查堆石混凝土资料、引用来源或工程知识点时，可以继续来问我。",
    "acknowledgment": "好的，我会继续保持当前上下文。你可以直接提出下一个问题。",
    "help": (
        "你可以这样使用我：询问堆石混凝土概念、施工工艺、温控、充填性能、"
        "工程案例，或让我检索某个主题的资料并给出引用来源。"
    ),
}


CHITCHAT_PATTERNS: dict[ChitchatIntent, set[str]] = {
    "greeting": {
        "你好",
        "您好",
        "嗨",
        "hi",
        "hello",
        "hey",
        "早上好",
        "下午好",
        "晚上好",
    },
    "thanks": {
        "谢谢",
        "感谢",
        "多谢",
        "谢了",
        "thanks",
        "thankyou",
    },
    "goodbye": {
        "再见",
        "拜拜",
        "bye",
        "goodbye",
        "下次见",
    },
    "acknowledgment": {
        "好",
        "好的",
        "明白",
        "明白了",
        "知道了",
        "收到",
        "ok",
        "okay",
    },
    "help": {
        "帮帮我",
        "怎么用",
        "如何使用",
        "使用帮助",
        "你能做什么",
        "help",
    },
}

DOMAIN_ANCHOR_TERMS = (
    "堆石混凝土",
    "rockfilledconcrete",
    "rock-filledconcrete",
    "rfc",
    "自密实混凝土",
    "水化热",
    "温控",
    "裂缝",
    "大坝",
    "施工",
)

HELP_SUBSTRING_PATTERNS = (
    "你能做什么",
    "你能帮我做什么",
    "能帮我做什么",
    "介绍一下你能",
    "简单介绍一下你能",
    "怎么使用",
    "如何使用",
    "使用帮助",
    "whatcanyoudo",
    "howshouldiask",
)


def detect_chitchat(question: str) -> ChitchatResult | None:
    compact = normalize_chitchat_text(question)
    if not compact:
        return None

    for intent, patterns in CHITCHAT_PATTERNS.items():
        if compact in patterns:
            return chitchat_result(intent)

    if not contains_domain_anchor(compact) and any(
        pattern in compact for pattern in HELP_SUBSTRING_PATTERNS
    ):
        return chitchat_result("help")
    return None


def chitchat_result(intent: ChitchatIntent) -> ChitchatResult:
    return ChitchatResult(
        intent=intent,
        answer=CHITCHAT_RESPONSES[intent],
        reasoning_summary=(
            f"识别为闲聊短路：{intent}，直接返回预设回复，不调用检索或模型。"
        ),
    )


def contains_domain_anchor(compact: str) -> bool:
    return any(term in compact for term in DOMAIN_ANCHOR_TERMS)


def normalize_chitchat_text(text: str) -> str:
    normalized = text.strip().casefold()
    return re.sub(r"[\s!！。,.，？?~～、;；:：\"'“”‘’]+", "", normalized)
