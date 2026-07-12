from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Sequence

from app.services.generation.chat_model import ChatMessage, ChatModelProvider
from app.services.retrieval.query_embedding_cache import normalize_query_text
from app.services.retrieval.runtime import (
    RetrievalIntentProfile,
    clamp_confidence,
    deterministic_intent_profile,
    normalize_explicitness,
    normalize_label,
)


CANONICALIZATION_SCHEMA = "phase58h-evidence-identity-v1"


LLM_REQUIRED_INTENTS = frozenset({"drawbacks_or_limitations", "crack_phenomena"})


INTENT_NORMALIZATION_ALIASES: dict[str, str] = {
    "advantages_or_benefits": "advantages",
    "benefits": "advantages",
    "advantage": "advantages",
    "pros": "advantages",
    "drawbacks": "drawbacks_or_limitations",
    "limitations": "drawbacks_or_limitations",
    "disadvantages": "drawbacks_or_limitations",
    "drawbacks_limitations": "drawbacks_or_limitations",
    "drawbacks_or_disadvantages": "drawbacks_or_limitations",
    "filling_performance_factors": "filling_performance",
    "filling_capacity": "filling_performance",
    "filling_ability": "filling_performance",
    "cracks": "crack_phenomena",
    "cracking": "crack_phenomena",
    "crack_patterns": "crack_phenomena",
    "crack_phenomena": "crack_phenomena",
    "causes_of_cracks": "crack_phenomena",
    "crack_causes": "crack_phenomena",
    "table": "table_evidence",
    "tables": "table_evidence",
    "parameter_table": "table_evidence",
    "visual": "visual_evidence",
    "figures": "visual_evidence",
    "images": "visual_evidence",
    "flowability_indicators": "flowability",
    "flowability_evaluation": "flowability",
    "workability": "flowability",
}


COMPARISON_TARGET_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "normal_concrete",
        ("普通混凝土", "常态混凝土", "normal concrete", "ordinary concrete", "conventional concrete"),
    ),
    (
        "roller_compacted_concrete",
        ("碾压混凝土", "rcc", "roller compacted concrete", "roller-compacted concrete"),
    ),
    (
        "self_compacting_concrete",
        ("自密实混凝土", "scc", "self compacting concrete", "self-compacting concrete"),
    ),
)


@dataclass(frozen=True)
class EvidenceQueryIdentity:
    raw_query: str
    canonical_query: str
    entity_key: str
    intent_key: str
    modifiers: tuple[str, ...] = ()
    source: str = "deterministic"
    confidence: float = 0.0
    safe_for_cache_reuse: bool = False
    reason: str = "unclassified"
    model_provider: str = ""
    model_name: str = ""
    retrieval_intent: RetrievalIntentProfile = field(
        default_factory=RetrievalIntentProfile
    )

    def diagnostics(self) -> dict[str, object]:
        return {
            "evidence_query_canonicalized": self.safe_for_cache_reuse,
            "evidence_canonical_query": truncate_identity_text(self.canonical_query, 160),
            "evidence_entity_key": truncate_identity_text(self.entity_key, 80),
            "evidence_intent_key": self.intent_key,
            "evidence_modifiers": list(self.modifiers),
            "evidence_cache_identity_source": self.source,
            "evidence_cache_identity_confidence": round(float(self.confidence), 3),
            "evidence_cache_identity_model_provider": self.model_provider,
            "evidence_cache_identity_model_name": self.model_name,
            "evidence_cache_reuse_allowed": self.safe_for_cache_reuse,
            "evidence_cache_reuse_block_reason": "" if self.safe_for_cache_reuse else self.reason,
            "evidence_cache_identity_schema": CANONICALIZATION_SCHEMA,
            **self.retrieval_intent.diagnostics(),
        }


ENTITY_ALIASES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "rock-filled concrete",
        ("堆石混凝土", "堆石砼", "rfc", "rock-filled concrete", "rock filled concrete"),
        ("堆石混凝土", "rock-filled concrete"),
    ),
    (
        "self-compacting concrete",
        ("自密实混凝土", "自密实砼", "scc", "self-compacting concrete", "self compacting concrete"),
        ("自密实混凝土", "self-compacting concrete"),
    ),
    (
        "dam crack causes",
        ("大坝裂缝成因", "大坝裂缝原因", "坝体裂缝成因", "dam crack causes", "dam cracking causes"),
        ("大坝裂缝成因",),
    ),
)


INTENT_ALIASES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "visual_evidence",
        ("图片", "图示", "配图", "照片", "曲线", "显微", "形貌", "figure", "image", "photo", "diagram", "curve"),
        ("图片", "图示", "曲线", "视觉证据"),
    ),
    (
        "table_evidence",
        ("表格", "参数表", "数据表", "列表", "table", "tabulated", "parameter table"),
        ("表格", "数据", "参数"),
    ),
    (
        "causes",
        ("成因", "原因", "机理", "致因", "cause", "causes", "reason", "mechanism"),
        ("成因", "原因", "机理"),
    ),
    (
        "advantages",
        ("优势", "优点", "优越", "长处", "好处", "benefit", "benefits", "advantage", "advantages"),
        ("优势", "优点", "优越性"),
    ),
    (
        "drawbacks_or_limitations",
        ("劣势", "缺点", "不足", "局限", "短板", "drawback", "drawbacks", "limitation", "disadvantage"),
        ("劣势", "缺点", "不足", "局限"),
    ),
    (
        "filling_performance",
        ("填充", "充填", "灌填", "填充性能", "充填性能", "filling", "fillability"),
        ("填充", "充填", "填充性能"),
    ),
    (
        "crack_phenomena",
        ("裂缝", "裂纹", "缝隙", "开裂", "crack", "cracks", "cracking", "fissure"),
        ("裂缝", "裂纹", "开裂"),
    ),
    (
        "flowability",
        ("流动性", "流动", "工作性", "工作性能", "flowability", "workability"),
        ("流动性", "工作性"),
    ),
    (
        "measures",
        ("措施", "方法", "方案", "防治", "处理", "mitigation", "measure", "method"),
        ("措施", "方法", "处理"),
    ),
    (
        "classification",
        ("类型", "分类", "种类", "category", "classification", "type"),
        ("分类", "类型"),
    ),
    (
        "definition",
        ("是什么", "概念", "定义", "definition", "what is"),
        ("定义", "概念"),
    ),
    (
        "comparison",
        ("对比", "相比", "区别", "差异", "compare", "comparison", "versus", "vs"),
        ("对比", "差异"),
    ),
)


CONSTRAINT_TERMS = (
    "相比",
    "对比",
    "区别",
    "差异",
    "最新",
    "本次",
    "这个图片",
    "上一段",
    "compare",
    "versus",
    "latest",
    "this image",
)


EXPLICIT_CONTINUE_TERMS = ("继续", "接着上次", "继续上次", "接着说", "continue", "resume")


def build_evidence_query_identity(
    query: str,
    *,
    history: Sequence[str] | None = None,
) -> EvidenceQueryIdentity:
    raw_query = normalize_query_text(query)
    if not raw_query:
        return EvidenceQueryIdentity(
            raw_query=query,
            canonical_query="",
            entity_key="",
            intent_key="",
            reason="empty_query",
            retrieval_intent=deterministic_intent_profile(query, history=history),
        )

    inherited_topic = latest_history_topic(history or ())
    entity_key, entity_terms = detect_entity(raw_query)
    intent_key, intent_terms = detect_intent(raw_query)
    if not entity_key and inherited_topic and looks_like_followup_identity_query(raw_query):
        entity_key, entity_terms = detect_entity(inherited_topic)
        if not entity_key:
            entity_key = normalize_query_text(inherited_topic)
            entity_terms = (entity_key,)
    if not intent_key and inherited_topic and looks_like_followup_identity_query(raw_query):
        intent_key, intent_terms = detect_intent(raw_query)

    if not entity_key:
        return raw_identity(raw_query, "missing_entity", intent_key=intent_key)
    if not intent_key:
        return raw_identity(raw_query, "missing_intent", entity_key=entity_key)
    if intent_key in LLM_REQUIRED_INTENTS:
        return raw_identity(raw_query, "llm_required_for_open_semantic_identity", entity_key=entity_key, intent_key=intent_key)
    modifiers = detect_modifiers(raw_query, history=history or (), intent_key=intent_key)
    if has_unsafe_constraint(raw_query, intent_key=intent_key):
        return EvidenceQueryIdentity(
            raw_query=raw_query,
            canonical_query=raw_query,
            entity_key=entity_key,
            intent_key=intent_key,
            modifiers=modifiers,
            confidence=0.45,
            safe_for_cache_reuse=False,
            reason="constraint_change",
            retrieval_intent=deterministic_intent_profile(raw_query, history=history),
        )

    canonical_query = normalize_query_text(" ".join([*entity_terms, *intent_terms, *modifiers]))
    return EvidenceQueryIdentity(
        raw_query=raw_query,
        canonical_query=canonical_query,
        entity_key=entity_key,
        intent_key=intent_key,
        modifiers=modifiers,
        confidence=0.95,
        safe_for_cache_reuse=True,
        reason="canonicalized",
        retrieval_intent=deterministic_intent_profile(raw_query, history=history),
    )


def raw_identity(
    raw_query: str,
    reason: str,
    *,
    entity_key: str = "",
    intent_key: str = "",
) -> EvidenceQueryIdentity:
    return EvidenceQueryIdentity(
        raw_query=raw_query,
        canonical_query=raw_query,
        entity_key=entity_key,
        intent_key=intent_key,
        confidence=0.0,
        safe_for_cache_reuse=False,
        reason=reason,
        retrieval_intent=deterministic_intent_profile(raw_query),
    )


def refine_evidence_query_identity_with_llm(
    query: str,
    *,
    base_identity: EvidenceQueryIdentity,
    provider: ChatModelProvider | None,
    history: Sequence[str] | None = None,
    force: bool = False,
) -> EvidenceQueryIdentity:
    if provider is None:
        return base_identity
    if base_identity.safe_for_cache_reuse and not force:
        return base_identity
    if str(getattr(provider, "provider_name", "")).casefold() in {"", "deterministic", "fake", "local"}:
        return base_identity
    try:
        result = provider.generate(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "You are an Agent Runtime semantic identity classifier. "
                        "Return JSON only. Do not answer the user question. "
                        "Decide whether similar future questions should reuse the same retrieval/tool cache identity. "
                        "Use a stable entity_key and a specific semantic intent_key. "
                        "Do not use broad polarity labels such as positive/negative/pro/con. "
                        "For synonyms, map to the same specific intent, e.g. 裂缝/缝隙/裂纹/开裂 -> crack_phenomena, "
                        "劣势/缺点/不足/局限 -> drawbacks_or_limitations. "
                        "If ambiguous, set safe_for_cache_reuse=false."
                    ),
                ),
                ChatMessage(
                    role="user",
                    content=json.dumps(
                        {
                            "query": query,
                            "history": list(history or ())[-6:],
                            "deterministic_identity": base_identity.diagnostics(),
                            "required_json_schema": {
                                "entity_key": "stable topic/entity in English or original technical term",
                                "intent_key": "specific snake_case semantic task",
                                "canonical_query": "standalone retrieval query with entity and intent terms",
                                "confidence": "0.0 to 1.0",
                                "safe_for_cache_reuse": "boolean",
                                "visual_intent": "0.0 to 1.0 routing score",
                                "table_intent": "0.0 to 1.0 routing score",
                                "relationship_intent": "0.0 to 1.0 routing score",
                                "relationship_type": "specific relation label or none",
                                "graph_search_mode": "none or local",
                                "visual_explicitness": "explicit, implicit, none, or negative",
                                "table_explicitness": "explicit, implicit, none, or negative",
                                "relationship_explicitness": "explicit, implicit, none, or negative",
                                "entities": "bounded list of relevant entity labels",
                                "required_evidence_types": "subset of text, relationship, table, figure",
                            },
                        },
                        ensure_ascii=False,
                    ),
                ),
            ]
        )
    except Exception:
        return raw_identity(
            base_identity.raw_query,
            "llm_identity_failed",
            entity_key=base_identity.entity_key,
            intent_key=base_identity.intent_key,
        )
    parsed = parse_identity_json(result.answer)
    if parsed is None:
        return raw_identity(
            base_identity.raw_query,
            "llm_identity_invalid_json",
            entity_key=base_identity.entity_key,
            intent_key=base_identity.intent_key,
        )
    entity_key = normalize_query_text(str(parsed.get("entity_key") or base_identity.entity_key))[:80]
    intent_key = canonical_intent_key(
        normalize_identity_key(str(parsed.get("intent_key") or base_identity.intent_key)),
        query=query,
        history=history or (),
        canonical_query=str(parsed.get("canonical_query") or ""),
    )
    canonical_query = normalize_query_text(str(parsed.get("canonical_query") or ""))
    modifiers = detect_modifiers(query, history=history or (), intent_key=intent_key)
    if modifiers and canonical_query:
        canonical_query = normalize_query_text(" ".join([canonical_query, *modifiers]))
    confidence = clamp_confidence(parsed.get("confidence"))
    retrieval_intent = retrieval_intent_from_json(
        parsed,
        query=query,
        history=history or (),
        source="llm",
    )
    safe = bool(parsed.get("safe_for_cache_reuse")) and confidence >= 0.65
    if not entity_key or not intent_key or not canonical_query or not safe:
        return EvidenceQueryIdentity(
            raw_query=base_identity.raw_query,
            canonical_query=canonical_query or base_identity.raw_query,
            entity_key=entity_key or base_identity.entity_key,
            intent_key=intent_key or base_identity.intent_key,
            modifiers=modifiers,
            source="llm",
            confidence=confidence,
            safe_for_cache_reuse=False,
            reason="llm_identity_not_reusable",
            model_provider=getattr(result, "provider", "") or getattr(provider, "provider_name", ""),
            model_name=getattr(result, "model_name", "") or getattr(provider, "model_name", ""),
            retrieval_intent=retrieval_intent,
        )
    return EvidenceQueryIdentity(
        raw_query=base_identity.raw_query,
        canonical_query=canonical_query,
        entity_key=entity_key,
        intent_key=intent_key,
        modifiers=modifiers,
        source="llm",
        confidence=confidence,
        safe_for_cache_reuse=True,
        reason="llm_canonicalized",
        model_provider=getattr(result, "provider", "") or getattr(provider, "provider_name", ""),
        model_name=getattr(result, "model_name", "") or getattr(provider, "model_name", ""),
        retrieval_intent=retrieval_intent,
    )


def retrieval_intent_from_json(
    values: dict[str, object],
    *,
    query: str,
    history: Sequence[str],
    source: str,
) -> RetrievalIntentProfile:
    fallback = deterministic_intent_profile(query, history=history)
    required = values.get("required_evidence_types")
    entities = values.get("entities")
    required_values = (
        [str(item) for item in required]
        if isinstance(required, list)
        else list(fallback.required_evidence_types)
    )
    visual_negative = fallback.visual_explicitness == "negative"
    table_negative = fallback.table_explicitness == "negative"
    relationship_negative = fallback.relationship_explicitness == "negative"
    visual_explicit = fallback.visual_explicitness == "explicit"
    table_explicit = fallback.table_explicitness == "explicit"
    relationship_explicit = fallback.relationship_explicitness == "explicit"
    if visual_negative:
        required_values = [item for item in required_values if item != "figure"]
    if table_negative:
        required_values = [item for item in required_values if item != "table"]
    if relationship_negative:
        required_values = [item for item in required_values if item != "relationship"]
    for evidence_type, explicit, negative in (
        ("figure", visual_explicit, visual_negative),
        ("table", table_explicit, table_negative),
        ("relationship", relationship_explicit, relationship_negative),
    ):
        if explicit and not negative and evidence_type not in required_values:
            required_values.append(evidence_type)
    return RetrievalIntentProfile(
        visual_intent=(
            0.0
            if visual_negative
            else max(
                fallback.visual_intent,
                clamp_confidence(values.get("visual_intent")),
            )
            if visual_explicit
            else values.get("visual_intent", fallback.visual_intent)
        ),
        table_intent=(
            0.0
            if table_negative
            else max(
                fallback.table_intent,
                clamp_confidence(values.get("table_intent")),
            )
            if table_explicit
            else values.get("table_intent", fallback.table_intent)
        ),
        relationship_intent=(
            0.0
            if relationship_negative
            else max(
                fallback.relationship_intent,
                clamp_confidence(values.get("relationship_intent")),
            )
            if relationship_explicit
            else values.get("relationship_intent", fallback.relationship_intent)
        ),
        relationship_type=(
            "none"
            if relationship_negative
            else normalize_label(values.get("relationship_type")) or fallback.relationship_type
        ),
        graph_search_mode=(
            "none"
            if relationship_negative
            else "local"
            if normalize_label(values.get("graph_search_mode")) == "local"
            else fallback.graph_search_mode
        ),
        visual_explicitness=(
            "negative"
            if visual_negative
            else "explicit"
            if visual_explicit
            else normalize_explicitness(values.get("visual_explicitness", fallback.visual_explicitness))
        ),
        table_explicitness=(
            "negative"
            if table_negative
            else "explicit"
            if table_explicit
            else normalize_explicitness(values.get("table_explicitness", fallback.table_explicitness))
        ),
        relationship_explicitness=(
            "negative"
            if relationship_negative
            else "explicit"
            if relationship_explicit
            else normalize_explicitness(values.get(
                "relationship_explicitness",
                fallback.relationship_explicitness,
            ))
        ),
        entities=tuple(str(item) for item in entities) if isinstance(entities, list) else fallback.entities,
        required_evidence_types=tuple(required_values),
        source=source,
    ).normalized()


def parse_identity_json(text: str) -> dict[str, object] | None:
    stripped = (text or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if match:
        stripped = match.group(0)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def normalize_identity_key(value: str) -> str:
    normalized = normalize_for_match(value)
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized[:80]


def canonical_intent_key(
    intent_key: str,
    *,
    query: str,
    history: Sequence[str],
    canonical_query: str,
) -> str:
    normalized = INTENT_NORMALIZATION_ALIASES.get(intent_key, intent_key)
    text = normalize_for_match(" ".join([query, canonical_query, latest_user_history_topic(history)]))
    if contains_any(text, ("图片", "图示", "配图", "照片", "figure", "image", "diagram")):
        return "visual_evidence"
    if contains_any(text, ("表格", "参数表", "数据表", "table", "tabulated")):
        return "table_evidence"
    if contains_any(text, ("相比", "对比", "区别", "差异", "compare", "comparison", "versus", " vs ")):
        return "comparison"
    if contains_any(text, ("成因", "原因", "机理", "致因", "cause", "causes", "reason", "mechanism")):
        return "causes"
    if contains_any(text, ("优势", "优点", "优越", "benefit", "advantage", "advantages")):
        return "advantages"
    if contains_any(text, ("劣势", "缺点", "不足", "局限", "limitation", "drawback", "disadvantage")):
        return "drawbacks_or_limitations"
    if contains_any(text, ("填充", "充填", "灌填", "filling", "fillability")):
        return "filling_performance"
    if contains_any(text, ("裂缝", "裂纹", "缝隙", "开裂", "crack", "cracking", "fissure")):
        return "crack_phenomena"
    if contains_any(text, ("流动", "工作性", "flowability", "workability")):
        return "flowability"
    return normalized


def detect_modifiers(
    query: str,
    *,
    history: Sequence[str],
    intent_key: str,
) -> tuple[str, ...]:
    if intent_key != "comparison":
        return ()
    text = normalize_for_match(" ".join([query, latest_user_history_topic(history)]))
    targets = [
        f"target={target}"
        for target, aliases in COMPARISON_TARGET_ALIASES
        if any(alias_matches(text, alias) for alias in aliases)
    ]
    return tuple(dict.fromkeys(targets))


def clamp_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(confidence, 1.0))


def detect_entity(query: str) -> tuple[str, tuple[str, ...]]:
    normalized = normalize_for_match(query)
    for entity_key, aliases, canonical_terms in ENTITY_ALIASES:
        if any(alias_matches(normalized, alias) for alias in aliases):
            return entity_key, canonical_terms
    if contains_any(normalized, ("大坝", "坝体", "dam")) and contains_any(
        normalized, ("裂缝", "裂纹", "crack", "cracking")
    ):
        return "dam_cracks", ("大坝裂缝", "dam cracks")
    if contains_any(normalized, ("堆石", "rfc", "rock filled", "rock-filled")) and contains_any(
        normalized, ("混凝土", "concrete")
    ):
        return "rock-filled concrete", ("堆石混凝土", "rock-filled concrete")
    return "", ()


def detect_intent(query: str) -> tuple[str, tuple[str, ...]]:
    normalized = normalize_for_match(query)
    for intent_key, aliases, canonical_terms in INTENT_ALIASES:
        if any(alias_matches(normalized, alias) for alias in aliases):
            return canonical_intent_key(
                intent_key,
                query=query,
                history=(),
                canonical_query=" ".join(canonical_terms),
            ), canonical_terms
    return "", ()


def alias_matches(normalized_query: str, alias: str) -> bool:
    normalized_alias = normalize_for_match(alias)
    if not normalized_alias:
        return False
    if normalized_alias.isascii() and re.fullmatch(r"[a-z0-9]+", normalized_alias):
        return re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])",
            normalized_query,
        ) is not None
    return normalized_alias in normalized_query


def normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold().replace("-", " "))


def has_unsafe_constraint(query: str, *, intent_key: str) -> bool:
    normalized = normalize_for_match(query)
    if intent_key == "comparison":
        return False
    return any(term.casefold() in normalized for term in CONSTRAINT_TERMS)


def latest_history_topic(history: Sequence[str]) -> str:
    user_topic = latest_user_history_topic(history)
    if user_topic:
        return user_topic
    for item in reversed(history):
        text = str(item)
        if is_assistant_history_item(text) or is_summary_history_item(text):
            continue
        cleaned = normalize_query_text(strip_role_prefix(text))
        if looks_like_assistant_answer(cleaned):
            continue
        if cleaned:
            return cleaned[:160]
    return ""


def strip_role_prefix(text: str) -> str:
    return re.sub(r"^\s*(user|assistant|human|ai|用户|助手)\s*[:：]\s*", "", text, flags=re.IGNORECASE)


def latest_user_history_topic(history: Sequence[str]) -> str:
    for item in reversed(history):
        text = str(item)
        if is_assistant_history_item(text) or is_summary_history_item(text):
            continue
        cleaned = normalize_query_text(strip_role_prefix(text))
        if cleaned:
            if looks_like_assistant_answer(cleaned):
                continue
            if looks_like_followup_identity_query(cleaned) and not detect_entity(cleaned)[0]:
                continue
            return cleaned[:160]
    return ""


def is_assistant_history_item(text: str) -> bool:
    stripped = (text or "").lstrip().casefold()
    return stripped.startswith(("assistant:", "ai:", "助手:", "助手："))


def is_summary_history_item(text: str) -> bool:
    stripped = (text or "").lstrip().casefold()
    return stripped.startswith(("summary:", "对话摘要:", "对话摘要："))


def looks_like_assistant_answer(text: str) -> bool:
    normalized = normalize_for_match(text)
    if len(normalized) > 220:
        return True
    answer_markers = ("根据", "检索到", "文献", "来源", "citation", "sources", "[1]", "【1】")
    return sum(marker in normalized for marker in answer_markers) >= 2


def contains_any(text: str, terms: Sequence[str]) -> bool:
    return any(term.casefold() in text for term in terms)


def looks_like_followup_identity_query(query: str) -> bool:
    compact = re.sub(r"\s+", "", query)
    return len(compact) <= 18 or any(term in normalize_for_match(query) for term in EXPLICIT_CONTINUE_TERMS)


def truncate_identity_text(text: str, limit: int) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3] + "..."
