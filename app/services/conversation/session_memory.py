from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass


DOMAIN_TERMS = (
    "堆石混凝土",
    "自密实混凝土",
    "填充密实性",
    "填充",
    "密实",
    "流动性",
    "孔隙",
    "骨料级配",
    "施工质量",
    "质量控制",
    "温控",
    "水化热",
    "冷却管",
    "开裂",
    "耐久性",
    "抗渗",
    "弹性模量",
    "力学性能",
    "配合比",
    "规范",
    "合规",
    "碾压混凝土",
    "裂纹",
    "数值分析",
    "rock-filled concrete",
    "rfc",
    "self-compacting concrete",
    "scc",
    "flowability",
    "filling capacity",
    "filling quality",
    "aggregate grading",
    "void filling",
    "compactness",
    "thermal control",
    "hydration heat",
    "cooling pipes",
    "cracking risk",
    "durability",
    "impermeability",
    "peridynamics",
)

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}")
HISTORY_PREFIX_RE = re.compile(r"^(用户|助手|对话摘要|summary|user|assistant)[:：]\s*", re.IGNORECASE)
CORRECTION_RE = re.compile(r"(更正|我说错|说错了|纠正|改问|不是.+是)", re.IGNORECASE)
QUESTION_ANCHOR_RE = re.compile(r"(吗|是否|是不是|是.+方法|是.+标准|专门的)")


@dataclass(frozen=True)
class SessionMemory:
    entities: tuple[str, ...] = ()
    retrieval_anchors: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    stale_anchors: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.entities and not self.retrieval_anchors and not self.constraints


def build_session_memory(
    history: Sequence[str],
    *,
    max_entities: int = 8,
    max_anchors: int = 12,
) -> SessionMemory:
    """Extract short-lived retrieval memory from the current conversation only."""

    normalized_history = [strip_history_prefix(item).strip() for item in history if item.strip()]
    if not normalized_history:
        return SessionMemory()

    text = "\n".join(normalized_history)
    entities: list[str] = []
    anchors: list[str] = []
    lowered = text.casefold()
    for term in DOMAIN_TERMS:
        if term.casefold() in lowered:
            target = entities if is_entity_like(term) else anchors
            target.append(term)

    for token in TOKEN_RE.findall(text):
        normalized = token.strip()
        if is_anchor_like(normalized):
            anchors.append(normalized)

    return SessionMemory(
        entities=tuple(dedupe_preserve_order(entities)[:max_entities]),
        retrieval_anchors=tuple(dedupe_preserve_order(anchors)[:max_anchors]),
    )


def refine_memory_for_question(question: str, memory: SessionMemory) -> SessionMemory:
    """Remove stale retrieval anchors when the current turn corrects prior context."""

    if memory.empty or not is_correction_question(question):
        return memory

    normalized_question = normalize_match_text(question)
    kept_anchors: list[str] = []
    stale_anchors: list[str] = []
    for anchor in memory.retrieval_anchors:
        normalized_anchor = normalize_match_text(anchor)
        if normalized_anchor and normalized_anchor in normalized_question:
            kept_anchors.append(anchor)
            continue
        if should_drop_anchor_after_correction(anchor):
            stale_anchors.append(anchor)
            continue
        stale_anchors.append(anchor)

    current_anchors = extract_current_question_anchors(question)
    constraints = dedupe_preserve_order(
        [
            *memory.constraints,
            "用户已更正问题目标，未在当前问题重申的旧检索锚点不再用于检索",
        ]
    )
    return SessionMemory(
        entities=memory.entities,
        retrieval_anchors=tuple(dedupe_preserve_order([*kept_anchors, *current_anchors])),
        constraints=tuple(constraints),
        stale_anchors=tuple(dedupe_preserve_order([*memory.stale_anchors, *stale_anchors])),
    )


def format_session_memory_for_retrieval(memory: SessionMemory) -> str:
    """Format memory as a retrieval-only hint, never as citation evidence."""

    if memory.empty:
        return ""
    parts: list[str] = []
    if memory.entities:
        parts.append("entities=" + ";".join(memory.entities))
    if memory.retrieval_anchors:
        parts.append("retrieval_anchors=" + ";".join(memory.retrieval_anchors))
    if memory.constraints:
        parts.append("constraints=" + ";".join(memory.constraints))
    return "会话检索记忆（仅用于检索，不作为引用来源）：" + " | ".join(parts)


def augment_query_with_session_memory(question: str, memory: SessionMemory) -> str:
    memory = refine_memory_for_question(question, memory)
    hint = format_session_memory_for_retrieval(memory)
    if not hint:
        return question
    return f"{question}；{hint}"


def strip_history_prefix(value: str) -> str:
    return HISTORY_PREFIX_RE.sub("", value.strip())


def is_entity_like(term: str) -> bool:
    normalized = term.casefold()
    return any(
        marker in normalized
        for marker in (
            "堆石混凝土",
            "自密实混凝土",
            "碾压混凝土",
            "rock-filled concrete",
            "rfc",
            "scc",
            "peridynamics",
        )
    )


def is_anchor_like(token: str) -> bool:
    normalized = token.casefold()
    if len(normalized) < 2:
        return False
    stopwords = {
        "用户",
        "助手",
        "这个",
        "这类",
        "哪些",
        "什么",
        "how",
        "what",
        "the",
        "and",
        "for",
        "with",
    }
    return normalized not in stopwords


def is_correction_question(question: str) -> bool:
    return bool(CORRECTION_RE.search(question or ""))


def should_drop_anchor_after_correction(anchor: str) -> bool:
    normalized = normalize_match_text(anchor)
    if not normalized:
        return True
    if QUESTION_ANCHOR_RE.search(anchor):
        return True
    return not is_entity_like(anchor)


def extract_current_question_anchors(question: str, max_anchors: int = 6) -> tuple[str, ...]:
    normalized_question = normalize_match_text(question)
    anchors = [
        term
        for term in DOMAIN_TERMS
        if not is_entity_like(term) and normalize_match_text(term) in normalized_question
    ]
    return tuple(dedupe_preserve_order(anchors)[:max_anchors])


def normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").casefold().strip())


def dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
