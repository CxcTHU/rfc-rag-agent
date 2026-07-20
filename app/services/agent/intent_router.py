import re
from typing import Literal


ConversationIntent = Literal[
    "followup_transform",
    "agent_meta",
    "capability_help",
    "refusal_explanation",
    "domain_or_search",
]

FOLLOWUP_TRANSFORM_TRIGGERS = (
    "用中文",
    "中文回答",
    "翻译成中文",
    "翻译一下",
    "转述翻译",
    "转成中文",
    "换成中文",
    "重新用中文",
    "简短点",
    "总结一下",
    "整理成表格",
    "改成要点",
    "translate that",
    "translate it",
    "in chinese",
    "answer in chinese",
    "say that in chinese",
    "say it in chinese",
    "summarize that",
    "make it shorter",
    "turn that into bullets",
)

FOLLOWUP_POINT_COUNT_PATTERN = re.compile(
    r"(?:再)?(?:给|列|补充|增加|整理|总结|改成|输出)?\s*"
    r"(?:[一二三四五六七八九十两\d]+)\s*(?:点|条|个要点|项)"
)

FOLLOWUP_PRONOUNS = (
    "that",
    "it",
    "刚才",
    "上一",
    "这段",
    "这个",
    "答案",
)

MODEL_META_TRIGGERS = (
    "什么大模型",
    "什么模型",
    "你用的模型",
    "你的模型",
    "哪个模型",
    "what model",
    "which model",
    "model are you using",
)

CAPABILITY_TRIGGERS = (
    "你能做什么",
    "怎么提问",
    "支持哪些模式",
    "你是什么",
    "what can you do",
    "how should i ask",
    "what modes",
)

REFUSAL_EXPLANATION_TRIGGERS = (
    "为什么拒答",
    "为什么拒绝",
    "刚才为什么",
    "拒答原因",
    "why did you refuse",
    "why refuse",
)

FIGURE_QUERY_TERMS = (
    "figure",
    "fig.",
    "image",
    "photo",
    "picture",
    "chart",
    "plot",
    "curve",
    "diagram",
    "flowchart",
    "microstructure",
    "show me",
    "visual",
    "图",
    "图片",
    "图表",
    "曲线",
    "流程图",
    "示意图",
    "照片",
    "形态",
    "破坏",
    "微观",
    "给我看",
    "展示",
)


def classify_conversation_intent(question: str) -> ConversationIntent:
    if classify_meta_intent(question) in {
        "agent_meta",
        "capability_help",
        "refusal_explanation",
    }:
        return classify_meta_intent(question)  # type: ignore[return-value]
    if is_followup_transform_request(question):
        return "followup_transform"
    return "domain_or_search"


def classify_meta_intent(question: str) -> str | None:
    normalized = question.casefold().strip()
    if not normalized:
        return None
    if any(trigger in normalized for trigger in MODEL_META_TRIGGERS):
        return "agent_meta"
    if any(trigger in normalized for trigger in CAPABILITY_TRIGGERS):
        return "capability_help"
    if any(trigger in normalized for trigger in REFUSAL_EXPLANATION_TRIGGERS):
        return "refusal_explanation"
    return None


def is_followup_transform_request(question: str) -> bool:
    normalized = question.casefold().strip()
    if not normalized:
        return False
    if FOLLOWUP_POINT_COUNT_PATTERN.search(normalized):
        return len(normalized) <= 120
    if any(trigger in normalized for trigger in FOLLOWUP_TRANSFORM_TRIGGERS):
        return len(normalized) <= 120 or any(
            pronoun in normalized for pronoun in FOLLOWUP_PRONOUNS
        )
    return False


def should_search_figures(question: str) -> bool:
    normalized = question.casefold()
    return any(term in normalized for term in FIGURE_QUERY_TERMS)


def strip_assistant_history_prefix(item: str) -> str | None:
    stripped = item.strip()
    prefixes = ("助手：", "assistant:", "Assistant:")
    for prefix in prefixes:
        if stripped.startswith(prefix):
            content = stripped[len(prefix):].strip()
            return content or None
    return None
