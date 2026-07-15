from __future__ import annotations

import hashlib
import json
import math
import re
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass
from typing import Literal, Sequence

from app.core.config import Settings, get_settings


RetrievalExplicitness = Literal["explicit", "implicit", "none", "negative"]
GraphSearchMode = Literal["none", "local"]
ChannelRequirement = Literal["disabled", "preferred", "required"]
GraphBudgetProfile = Literal["disabled", "preferred", "relation"]
HighLevelRetrievalTool = Literal[
    "hybrid_search_knowledge",
    "search_figures",
    "search_tables",
    "analyze_user_image",
]
HighLevelEvidenceTool = Literal[
    "hybrid_search_knowledge",
    "search_figures",
    "search_tables",
]
# These two tools retrieve a different evidence modality.  Their eligibility is
# decided by Runtime intent classification, never by a test case or a domain
# keyword.  Text/relationship questions keep the hybrid tool as their sole
# evidence route.
SPECIALIZED_EVIDENCE_TOOLS: tuple[HighLevelEvidenceTool, ...] = (
    "search_figures",
    "search_tables",
)

CAUSAL_RELATIONSHIP_TERMS = (
    "因果",
    "依赖",
    "影响",
    "成因",
    "原因",
    "导致",
    "作用",
    "depends on",
    "cause",
    "causes",
    "why",
    "affect",
    "influence",
    "impact",
)
CROSS_RELATIONSHIP_TERMS = (
    "关系",
    "关联",
    "联系",
    "relationship",
    "relate",
)
STANDARD_RELATIONSHIP_TERMS = (
    "引用",
    "遵循",
    "依据",
    "适用",
    "规定",
    "定义",
    "reference",
    "referenced",
    "applicable",
    "defined by",
    "defines",
)
RELATIONSHIP_TERMS = tuple(
    dict.fromkeys(
        (
            *CAUSAL_RELATIONSHIP_TERMS,
            *CROSS_RELATIONSHIP_TERMS,
            *STANDARD_RELATIONSHIP_TERMS,
        )
    )
)
STANDARD_TERMS = ("标准", "规范", "gb/t", "gb ", "dl/t", "sl/t", "standard", "specification")
VISUAL_TERMS = ("图片", "图示", "配图", "照片", "曲线", "figure", "image", "diagram", "photo", "curve")
TABLE_TERMS = ("表格", "参数表", "数据表", "table", "tabulated", "parameter table")
VISUAL_NEGATIONS = ("不要图片", "不需要图片", "只用文字", "text only", "no image", "without image")
TABLE_NEGATIONS = (
    "不要表格",
    "不需要表格",
    "不用表格",
    "不要引用表格",
    "不引用表格",
    "不用引用表格",
    "no table",
    "without table",
    "no table citation",
)
RELATIONSHIP_NEGATIONS = (
    "不要关系分析",
    "不要分析因果",
    "不要分析因果关系",
    "不分析关系",
    "不分析因果",
    "不分析因果关系",
    "不分析实体关系",
    "不分析上下游关系",
    "无需关联",
    "no relationship analysis",
)


@dataclass(frozen=True)
class RetrievalIntentProfile:
    visual_intent: float = 0.0
    table_intent: float = 0.0
    relationship_intent: float = 0.0
    relationship_type: str = "none"
    graph_search_mode: GraphSearchMode = "none"
    visual_explicitness: RetrievalExplicitness = "none"
    table_explicitness: RetrievalExplicitness = "none"
    relationship_explicitness: RetrievalExplicitness = "none"
    entities: tuple[str, ...] = ()
    required_evidence_types: tuple[str, ...] = ()
    source: str = "deterministic"

    def normalized(self) -> "RetrievalIntentProfile":
        visual_explicitness = normalize_explicitness(self.visual_explicitness)
        table_explicitness = normalize_explicitness(self.table_explicitness)
        relationship_explicitness = normalize_explicitness(self.relationship_explicitness)
        relationship_type = normalize_label(self.relationship_type) or "none"
        graph_search_mode: GraphSearchMode = (
            "local"
            if self.graph_search_mode == "local" and relationship_type != "none"
            else "none"
        )
        required = tuple(
            dict.fromkeys(
                item
                for item in (normalize_label(value) for value in self.required_evidence_types)
                if item in {"text", "relationship", "table", "figure"}
            )
        )
        return RetrievalIntentProfile(
            visual_intent=clamp_confidence(self.visual_intent),
            table_intent=clamp_confidence(self.table_intent),
            relationship_intent=clamp_confidence(self.relationship_intent),
            relationship_type=relationship_type,
            graph_search_mode=graph_search_mode,
            visual_explicitness=visual_explicitness,
            table_explicitness=table_explicitness,
            relationship_explicitness=relationship_explicitness,
            entities=tuple(str(value).strip()[:80] for value in self.entities if str(value).strip())[:8],
            required_evidence_types=required,
            source=(self.source or "deterministic")[:40],
        )

    def diagnostics(self) -> dict[str, object]:
        profile = self.normalized()
        return {
            "retrieval_intent_source": profile.source,
            "retrieval_visual_intent": round(profile.visual_intent, 3),
            "retrieval_table_intent": round(profile.table_intent, 3),
            "retrieval_relationship_intent": round(profile.relationship_intent, 3),
            "retrieval_relationship_type": profile.relationship_type,
            "retrieval_graph_search_mode": profile.graph_search_mode,
            "retrieval_required_evidence_types": list(profile.required_evidence_types),
        }


@dataclass(frozen=True)
class RetrievalPlan:
    schema: str
    canonical_query: str
    graph_requirement: ChannelRequirement
    graph_budget_profile: GraphBudgetProfile
    graph_max_hops: int
    graph_max_matches: int
    relationship_type: str
    table_text_requirement: ChannelRequirement
    figure_caption_requirement: ChannelRequirement
    required_evidence_types: tuple[str, ...]
    intent_source: str

    def diagnostics(self) -> dict[str, object]:
        return {
            "retrieval_plan_schema": self.schema,
            "retrieval_intent_source": self.intent_source,
            "retrieval_graph_requirement": self.graph_requirement,
            "retrieval_graph_budget_profile": self.graph_budget_profile,
            "retrieval_graph_max_hops": self.graph_max_hops,
            "retrieval_graph_max_matches": self.graph_max_matches,
            "retrieval_relationship_type": self.relationship_type,
            "retrieval_table_text_requirement": self.table_text_requirement,
            "retrieval_figure_caption_requirement": self.figure_caption_requirement,
            "retrieval_required_evidence_types": list(self.required_evidence_types),
            "retrieval_plan_digest": retrieval_plan_digest(self),
        }


@dataclass(frozen=True)
class RetrievalAction:
    required_tool: HighLevelEvidenceTool | None = None
    forbidden_tools: tuple[HighLevelEvidenceTool, ...] = ()
    tool_sequence: tuple[HighLevelEvidenceTool, ...] = ()
    reason: str = "implicit"


def build_retrieval_action(profile: RetrievalIntentProfile) -> RetrievalAction:
    """Map modality intent to one code-owned high-level evidence route.

    The model may synthesize after evidence is present, but it must not promote a
    generic text question into a table/figure request.  Specialized evidence is
    therefore opt-in only through the Runtime's explicit intent decision.
    """
    normalized = profile.normalized()
    if normalized.table_explicitness == "explicit":
        return RetrievalAction(
            required_tool="search_tables",
            forbidden_tools=tuple(
                tool for tool in SPECIALIZED_EVIDENCE_TOOLS if tool != "search_tables"
            ),
            tool_sequence=("search_tables", "hybrid_search_knowledge"),
            reason="explicit_table",
        )
    if normalized.visual_explicitness == "explicit":
        return RetrievalAction(
            required_tool="search_figures",
            forbidden_tools=tuple(
                tool for tool in SPECIALIZED_EVIDENCE_TOOLS if tool != "search_figures"
            ),
            tool_sequence=("search_figures", "hybrid_search_knowledge"),
            reason="explicit_figure",
        )
    return RetrievalAction(
        forbidden_tools=SPECIALIZED_EVIDENCE_TOOLS,
        reason=(
            "explicit_negative"
            if normalized.visual_explicitness == "negative"
            or normalized.table_explicitness == "negative"
            else "implicit_text_only"
        ),
    )


def retrieval_tool_for_action(action: RetrievalAction) -> HighLevelEvidenceTool:
    """Resolve one Runtime action to exactly one public evidence tool."""
    return action.required_tool or "hybrid_search_knowledge"


def retrieval_runtime_result_limit(
    tool_name: HighLevelRetrievalTool,
    settings: Settings | None = None,
) -> int:
    """Return a code-owned result budget for one high-level retrieval action.

    Agent requests and model tool schemas deliberately expose no ``top_k``.
    Hybrid reranking still applies Dynamic-K as the final selector; this value
    merely bounds the Runtime request passed into a retrieval kernel.
    """
    active = settings or get_settings()
    dynamic_max = max(1, int(active.reranking_dynamic_max_results))
    dynamic_min = max(1, int(active.reranking_dynamic_min_results))
    if tool_name in {"hybrid_search_knowledge", "analyze_user_image"}:
        return dynamic_max
    if tool_name in {"search_figures", "search_tables"}:
        return max(dynamic_min, min(dynamic_max, int(active.reranking_recall_k)))
    raise ValueError(f"unsupported high-level retrieval tool: {tool_name}")


_CURRENT_RETRIEVAL_PLAN: ContextVar[RetrievalPlan | None] = ContextVar(
    "current_retrieval_plan",
    default=None,
)


def build_retrieval_plan(
    profile: RetrievalIntentProfile,
    canonical_query: str,
    settings: Settings | None = None,
) -> RetrievalPlan:
    active = settings or get_settings()
    normalized = profile.normalized()
    graph_requirement = graph_channel_requirement(normalized, active)
    graph_budget_profile: GraphBudgetProfile = {
        "disabled": "disabled",
        "preferred": "preferred",
        "required": "relation",
    }[graph_requirement]
    graph_max_hops = {
        "disabled": 0,
        "preferred": active.retrieval_graph_preferred_max_hops,
        "relation": active.retrieval_graph_required_max_hops,
    }[graph_budget_profile]
    graph_max_matches = {
        "disabled": 0,
        "preferred": active.retrieval_graph_preferred_max_matches,
        "relation": active.retrieval_graph_required_max_matches,
    }[graph_budget_profile]
    return RetrievalPlan(
        schema=active.retrieval_runtime_schema,
        canonical_query=" ".join(canonical_query.strip().split()),
        graph_requirement=graph_requirement,
        graph_budget_profile=graph_budget_profile,
        graph_max_hops=min(max(int(graph_max_hops), 0), 2),
        graph_max_matches=min(
            max(int(graph_max_matches), 0),
            max(int(active.hybrid_graph_max_matches), 0),
        ),
        relationship_type=normalized.relationship_type,
        table_text_requirement=channel_requirement(
            normalized.table_intent,
            normalized.table_explicitness,
            active.retrieval_relationship_preferred_threshold,
        ),
        figure_caption_requirement=channel_requirement(
            normalized.visual_intent,
            normalized.visual_explicitness,
            active.retrieval_relationship_preferred_threshold,
        ),
        required_evidence_types=normalized.required_evidence_types,
        intent_source=normalized.source,
    )


def deterministic_intent_profile(
    query: str,
    history: Sequence[str] | None = None,
) -> RetrievalIntentProfile:
    current_text = query.casefold()
    history_text = " ".join((history or ())[-3:]).casefold()
    visual_signal = current_turn_intent_signal(
        current_text,
        history_text,
        positive_terms=VISUAL_TERMS,
        negative_terms=VISUAL_NEGATIONS,
    )
    table_signal = current_turn_intent_signal(
        current_text,
        history_text,
        positive_terms=TABLE_TERMS,
        negative_terms=TABLE_NEGATIONS,
    )
    relationship_signal = current_turn_intent_signal(
        current_text,
        history_text,
        positive_terms=RELATIONSHIP_TERMS,
        negative_terms=RELATIONSHIP_NEGATIONS,
    )
    visual_negative = visual_signal == "negative"
    table_negative = table_signal == "negative"
    relationship_negative = relationship_signal == "negative"
    visual_match = visual_signal == "positive"
    table_match = table_signal == "positive"
    relationship_text = current_text if contains_any(current_text, RELATIONSHIP_TERMS) else history_text
    standard_match = contains_any(relationship_text, STANDARD_TERMS)
    causal_match = contains_any(relationship_text, CAUSAL_RELATIONSHIP_TERMS)
    cross_match = contains_any(relationship_text, CROSS_RELATIONSHIP_TERMS)
    standard_relation_match = (
        standard_match and contains_any(relationship_text, STANDARD_RELATIONSHIP_TERMS)
    )
    relationship_match = (
        relationship_signal == "positive"
        and (causal_match or cross_match or standard_relation_match)
    )
    relationship_type = "standard_reference" if standard_match and relationship_match else (
        "cross_document" if relationship_match else "none"
    )
    required: list[str] = ["text"]
    if visual_match and not visual_negative:
        required.append("figure")
    if table_match and not table_negative:
        required.append("table")
    if relationship_match and not relationship_negative:
        required.append("relationship")
    return RetrievalIntentProfile(
        visual_intent=0.0 if visual_negative else (0.85 if visual_match else 0.0),
        table_intent=0.0 if table_negative else (0.85 if table_match else 0.0),
        relationship_intent=(
            0.0 if relationship_negative else (0.85 if relationship_match else 0.0)
        ),
        relationship_type="none" if relationship_negative else relationship_type,
        graph_search_mode=(
            "local" if relationship_match and not relationship_negative else "none"
        ),
        visual_explicitness=(
            "negative" if visual_negative else ("explicit" if visual_match else "none")
        ),
        table_explicitness=(
            "negative" if table_negative else ("explicit" if table_match else "none")
        ),
        relationship_explicitness=(
            "negative"
            if relationship_negative
            else ("explicit" if relationship_match else "none")
        ),
        required_evidence_types=tuple(required),
        source="deterministic_fallback",
    )


def current_turn_intent_signal(
    current_text: str,
    history_text: str,
    *,
    positive_terms: Sequence[str],
    negative_terms: Sequence[str],
) -> Literal["positive", "negative", "none"]:
    """Apply current-turn explicit instructions before historical context."""
    if contains_any(current_text, negative_terms):
        return "negative"
    if contains_any(current_text, positive_terms):
        return "positive"
    if contains_any(history_text, negative_terms):
        return "negative"
    if contains_any(history_text, positive_terms):
        return "positive"
    return "none"


def graph_channel_requirement(
    profile: RetrievalIntentProfile,
    settings: Settings,
) -> ChannelRequirement:
    if profile.relationship_explicitness == "negative":
        return "disabled"
    if profile.graph_search_mode != "local" or profile.relationship_type == "none":
        return "disabled"
    if (
        profile.relationship_explicitness == "explicit"
        and profile.relationship_intent >= settings.retrieval_relationship_required_threshold
    ):
        return "required"
    if profile.relationship_intent >= settings.retrieval_relationship_preferred_threshold:
        return "preferred"
    return "disabled"


def channel_requirement(
    confidence: float,
    explicitness: RetrievalExplicitness,
    preferred_threshold: float,
) -> ChannelRequirement:
    if explicitness == "negative":
        return "disabled"
    if explicitness == "explicit" and confidence >= preferred_threshold:
        return "required"
    if confidence >= preferred_threshold:
        return "preferred"
    return "disabled"


def set_current_retrieval_plan(plan: RetrievalPlan | None) -> Token[RetrievalPlan | None]:
    return _CURRENT_RETRIEVAL_PLAN.set(plan)


def reset_current_retrieval_plan(token: Token[RetrievalPlan | None]) -> None:
    _CURRENT_RETRIEVAL_PLAN.reset(token)


def current_retrieval_plan() -> RetrievalPlan | None:
    return _CURRENT_RETRIEVAL_PLAN.get()


def retrieval_plan_digest(plan: RetrievalPlan | None) -> str:
    if plan is None:
        return "legacy"
    payload = json.dumps(asdict(plan), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def clamp_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(confidence):
        return 0.0
    return min(max(confidence, 0.0), 1.0)


def normalize_explicitness(value: object) -> RetrievalExplicitness:
    normalized = normalize_label(value)
    if normalized in {"explicit", "implicit", "negative"}:
        return normalized  # type: ignore[return-value]
    return "none"


def normalize_label(value: object) -> str:
    normalized = str(value or "").strip().casefold()
    normalized = re.sub(r"[^a-z0-9_\-]+", "_", normalized)
    return re.sub(r"_+", "_", normalized).strip("_")[:80]


def contains_any(text: str, terms: Sequence[str]) -> bool:
    return any(term.casefold() in text for term in terms)
