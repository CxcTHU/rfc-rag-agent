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
CORRECTION_RE = re.compile(
    r"(更正|我说错|说错了|纠正|改问|不是.+是|"
    r"不是[^，。；,;]{1,40}[，,；;]|"
    r"不是[^，。；,;]{1,40}[。.!?]?$|"
    r"\bcorrection\b|\bi meant\b|\bnot\b.+\bbut\b|\bnot\b.+\bi mean\b|"
    r"\bnot\s+[A-Za-z][^.;,]{1,60}[,;]\s*(continue|use|focus))",
    re.IGNORECASE,
)
QUESTION_ANCHOR_RE = re.compile(r"(吗|是否|是不是|是.+方法|是.+标准|专门的)")


@dataclass(frozen=True)
class MemoryItem:
    text: str
    turn_index: int = 0
    importance: float = 1.0

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("memory item text must not be empty")

    def __str__(self) -> str:
        return self.text

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.text == other
        if isinstance(other, MemoryItem):
            return (
                self.text == other.text
                and self.turn_index == other.turn_index
                and self.importance == other.importance
            )
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.text)

    def to_state_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "turn_index": self.turn_index,
            "importance": self.importance,
        }


@dataclass(frozen=True)
class SessionMemory:
    entities: tuple[MemoryItem, ...] = ()
    retrieval_anchors: tuple[MemoryItem, ...] = ()
    constraints: tuple[str, ...] = ()
    stale_anchors: tuple[MemoryItem, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.entities and not self.retrieval_anchors and not self.constraints


def build_session_memory(
    history: Sequence[str],
    *,
    max_entities: int = 8,
    max_anchors: int = 12,
    half_life: float = 5.0,
) -> SessionMemory:
    """Extract short-lived retrieval memory from the current conversation only."""

    normalized_history = [strip_history_prefix(item).strip() for item in history if item.strip()]
    if not normalized_history:
        return SessionMemory()

    current_turn = len(normalized_history)
    entity_candidates: list[MemoryItem] = []
    anchor_candidates: list[MemoryItem] = []
    for turn_index, text in enumerate(normalized_history, start=1):
        lowered = text.casefold()
        for term in DOMAIN_TERMS:
            if term.casefold() in lowered:
                target = entity_candidates if is_entity_like(term) else anchor_candidates
                target.append(
                    MemoryItem(
                        text=term,
                        turn_index=turn_index,
                        importance=memory_item_importance(
                            turn_index=turn_index,
                            current_turn=current_turn,
                            half_life=half_life,
                        ),
                    )
                )

        for token in TOKEN_RE.findall(text):
            normalized = token.strip()
            if is_anchor_like(normalized):
                anchor_candidates.append(
                    MemoryItem(
                        text=normalized,
                        turn_index=turn_index,
                        importance=memory_item_importance(
                            turn_index=turn_index,
                            current_turn=current_turn,
                            half_life=half_life,
                        ),
                    )
                )

    return SessionMemory(
        entities=tuple(rank_memory_items(entity_candidates)[:max_entities]),
        retrieval_anchors=tuple(rank_memory_items(anchor_candidates)[:max_anchors]),
    )


def refine_memory_for_question(
    question: str,
    memory: SessionMemory,
    *,
    correction_override: bool | None = None,
) -> SessionMemory:
    """Remove stale retrieval anchors when the current turn corrects prior context."""

    correction = is_correction_question(question) if correction_override is None else correction_override
    if memory.empty or not correction:
        return memory

    normalized_question = normalize_match_text(question)
    kept_anchors: list[MemoryItem] = []
    stale_anchors: list[MemoryItem] = []
    for anchor in memory.retrieval_anchors:
        normalized_anchor = normalize_match_text(anchor.text)
        if normalized_anchor and normalized_anchor in normalized_question:
            kept_anchors.append(anchor)
            continue
        if should_drop_anchor_after_correction(anchor.text):
            stale_anchors.append(anchor)
            continue
        stale_anchors.append(anchor)

    current_anchors = tuple(
        MemoryItem(text=item, turn_index=0, importance=1.0)
        for item in extract_current_question_anchors(question)
    )
    constraints = dedupe_preserve_order(
        [
            *memory.constraints,
            "用户已更正问题目标，未在当前问题重申的旧检索锚点不再用于检索",
        ]
    )
    return SessionMemory(
        entities=memory.entities,
        retrieval_anchors=tuple(dedupe_memory_items([*kept_anchors, *current_anchors])),
        constraints=tuple(constraints),
        stale_anchors=tuple(dedupe_memory_items([*memory.stale_anchors, *stale_anchors])),
    )


def format_session_memory_for_retrieval(memory: SessionMemory) -> str:
    """Format memory as a retrieval-only hint, never as citation evidence."""

    if memory.empty:
        return ""
    parts: list[str] = []
    if memory.entities:
        parts.append("entities=" + ";".join(item.text for item in memory.entities))
    if memory.retrieval_anchors:
        parts.append(
            "retrieval_anchors="
            + ";".join(item.text for item in memory.retrieval_anchors)
        )
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


def memory_item_importance(
    *,
    turn_index: int,
    current_turn: int,
    half_life: float = 5.0,
) -> float:
    if half_life <= 0:
        return 1.0
    age = max(0, current_turn - turn_index)
    return 0.5 ** (age / half_life)


def decay_session_memory(
    memory: SessionMemory,
    *,
    current_turn: int,
    half_life: float = 5.0,
) -> SessionMemory:
    return SessionMemory(
        entities=tuple(
            decay_memory_item(item, current_turn=current_turn, half_life=half_life)
            for item in memory.entities
        ),
        retrieval_anchors=tuple(
            decay_memory_item(item, current_turn=current_turn, half_life=half_life)
            for item in memory.retrieval_anchors
        ),
        constraints=memory.constraints,
        stale_anchors=tuple(
            decay_memory_item(item, current_turn=current_turn, half_life=half_life)
            for item in memory.stale_anchors
        ),
    )


def decay_memory_item(
    item: MemoryItem,
    *,
    current_turn: int,
    half_life: float,
) -> MemoryItem:
    return MemoryItem(
        text=item.text,
        turn_index=item.turn_index,
        importance=memory_item_importance(
            turn_index=item.turn_index,
            current_turn=current_turn,
            half_life=half_life,
        ),
    )


def memory_item_from_state(value: object) -> MemoryItem | None:
    if isinstance(value, MemoryItem):
        return value
    if isinstance(value, str):
        text = value.strip()
        return MemoryItem(text=text) if text else None
    if not isinstance(value, dict):
        return None
    text = str(value.get("text") or "").strip()
    if not text:
        return None
    try:
        turn_index = int(value.get("turn_index") or 0)
    except (TypeError, ValueError):
        turn_index = 0
    try:
        importance = float(value.get("importance") or 1.0)
    except (TypeError, ValueError):
        importance = 1.0
    return MemoryItem(text=text, turn_index=turn_index, importance=importance)


def rank_memory_items(values: Sequence[MemoryItem]) -> list[MemoryItem]:
    deduped = dedupe_memory_items(values)
    return sorted(deduped, key=lambda item: (-item.importance, -item.turn_index, item.text))


def dedupe_memory_items(values: Sequence[MemoryItem]) -> list[MemoryItem]:
    by_text: dict[str, MemoryItem] = {}
    for item in values:
        key = item.text.casefold()
        existing = by_text.get(key)
        if existing is None or (item.importance, item.turn_index) > (
            existing.importance,
            existing.turn_index,
        ):
            by_text[key] = item
    return list(by_text.values())


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
