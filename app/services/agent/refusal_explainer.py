from collections.abc import Sequence
from typing import Protocol


MAX_SOURCE_SUMMARY_CHARS = 200
MAX_CONTENT_SNIPPET_CHARS = 80
MAX_REFUSAL_QUESTION_CHARS = 120

PROJECT_SCOPE_DESCRIPTION = (
    "我是一个面向堆石混凝土（RFC）、水工混凝土、坝工工程资料库的证据型问答系统。"
)


class RefusalSourceLike(Protocol):
    title: str
    source_type: str
    content: str | None


def build_refusal_explanation(
    *,
    category: str | None,
    refusal_reason: str | None,
    sources: Sequence[RefusalSourceLike],
) -> str | None:
    if category == "off_topic":
        return off_topic_explanation()
    if category == "evidence_insufficient":
        return evidence_insufficient_explanation(
            refusal_reason=refusal_reason,
            sources=sources,
        )
    return None


def off_topic_explanation() -> str:
    return (
        "refusal_explanation: 当前问题缺少堆石混凝土、混凝土材料、施工质量、"
        "水利工程或工程案例等领域锚点。可以改写为："
        "“请基于资料说明堆石混凝土在施工质量控制中的关键指标”，"
        "或“资料中如何描述堆石混凝土的填充性能影响因素”。"
    )


def off_topic_refusal_answer(question: str) -> str:
    safe_question = _short_question(question)
    return (
        f"{PROJECT_SCOPE_DESCRIPTION}\n\n"
        f"你的问题“{safe_question}”没有落在当前资料库和工程知识问答范围内，"
        "我不能基于本项目资料给出可靠回答。\n\n"
        "可以改问：\n"
        "- 堆石混凝土 RFC 相比常规混凝土有什么优势？\n"
        "- RFC 施工质量控制有哪些要点？\n"
        "- 资料库中是否有关于混凝土裂缝、缺陷或施工现象的图示证据？"
    )


def responsibility_refusal_answer() -> str:
    return (
        f"{PROJECT_SCOPE_DESCRIPTION}\n\n"
        "这个问题要求给出规范符合性或工程验收类结论。"
        "本系统不能替代规范审查、工程设计、第三方检测、验收判断或专家签字，"
        "因此不能直接判定工程是否合格、是否符合规范或能否用于实际工程。\n\n"
        "可以改问：\n"
        "- 资料中提到哪些配合比审查指标？\n"
        "- 相关标准或资料通常涉及哪些试验方法？\n"
        "- RFC 施工质量风险有哪些可供人工审查参考？"
    )


def evidence_insufficient_explanation(
    *,
    refusal_reason: str | None,
    sources: Sequence[RefusalSourceLike],
) -> str:
    safe_summaries = summarize_sources(sources)
    reason = sanitize_inline_text(refusal_reason or "retrieved evidence was too weak")
    if not safe_summaries:
        return (
            "refusal_explanation: 已尝试检索，但没有可安全展示的命中摘要；"
            f"当前缺口是 {reason}。建议补充更具体的材料、施工、力学、"
            "温控或工程案例关键词。"
        )

    joined = "；".join(safe_summaries)
    return (
        "refusal_explanation: 已检索到这些安全摘要："
        f"{joined}。当前缺口是 {reason}；建议补充更具体的材料、施工、"
        "力学、温控或工程案例关键词。"
    )


def summarize_sources(sources: Sequence[RefusalSourceLike]) -> list[str]:
    summaries: list[str] = []
    for source in sources[:3]:
        title = sanitize_inline_text(source.title)
        source_type = sanitize_inline_text(source.source_type)
        snippet = sanitize_inline_text(source.content or "")
        if len(snippet) > MAX_CONTENT_SNIPPET_CHARS:
            snippet = snippet[:MAX_CONTENT_SNIPPET_CHARS].rstrip() + "..."
        summary = f"{title}（{source_type}）"
        if snippet:
            summary = f"{summary}: {snippet}"
        if len(summary) > MAX_SOURCE_SUMMARY_CHARS:
            summary = summary[: MAX_SOURCE_SUMMARY_CHARS - 3].rstrip() + "..."
        summaries.append(summary)
    return summaries


def sanitize_inline_text(text: str) -> str:
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def _short_question(question: str) -> str:
    safe_question = sanitize_inline_text(question)
    if len(safe_question) <= MAX_REFUSAL_QUESTION_CHARS:
        return safe_question
    return safe_question[: MAX_REFUSAL_QUESTION_CHARS - 3].rstrip() + "..."
