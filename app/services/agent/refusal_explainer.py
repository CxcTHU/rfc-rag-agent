from collections.abc import Sequence
from typing import Protocol


MAX_SOURCE_SUMMARY_CHARS = 200
MAX_CONTENT_SNIPPET_CHARS = 80


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
