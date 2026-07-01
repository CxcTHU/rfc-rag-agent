from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Sequence

from app.services.agent.evidence_identity import (
    EvidenceQueryIdentity,
    build_evidence_query_identity,
)
from app.services.generation.chat_model import ChatToolCall
from app.services.observability.latency_trace import get_current_latency_trace


RuntimeFollowupType = Literal[
    "standalone",
    "visual_evidence_request",
    "table_evidence_request",
    "detail_expansion",
]


VISUAL_FOLLOWUP_TERMS = (
    "\u56fe\u7247",
    "\u56fe",
    "\u56fe\u793a",
    "\u914d\u56fe",
    "\u7167\u7247",
    "\u66f2\u7ebf",
    "\u793a\u610f\u56fe",
    "\u5f62\u6001",
    "figure",
    "image",
    "photo",
    "diagram",
    "curve",
)
TABLE_FOLLOWUP_TERMS = (
    "\u8868",
    "\u8868\u683c",
    "\u6570\u636e",
    "\u53c2\u6570",
    "\u5217\u8868",
    "table",
    "tabulated",
    "data",
    "parameter",
)
DETAIL_FOLLOWUP_TERMS = (
    "\u7ee7\u7eed",
    "\u5c55\u5f00",
    "\u8be6\u7ec6",
    "\u89e3\u91ca",
    "\u8bf4\u660e",
    "\u8865\u5145",
    "\u7b2c\u4e8c\u70b9",
    "\u4e0b\u4e00\u70b9",
    "continue",
    "detail",
    "expand",
)
GENERIC_FOLLOWUP_TERMS = (
    "\u6211\u9700\u8981",
    "\u8fd8\u6709",
    "\u9700\u8981",
    "\u652f\u6491",
    "\u76f8\u5173",
    "\u8bc1\u636e",
    "please",
    "show",
    "give me",
)


@dataclass(frozen=True)
class RuntimeContext:
    current_query: str
    history: tuple[str, ...] = ()
    recent_topic: str = ""
    inherited_topic: str = ""
    followup_type: RuntimeFollowupType = "standalone"
    standalone_task: str = ""
    contextualized: bool = False
    contextualization_source: str = "deterministic"


@dataclass(frozen=True)
class ToolArgumentGrounding:
    tool_name: str
    original_query: str
    grounded_query: str
    rewrite_applied: bool
    reason: str


@dataclass
class EvidenceAttempt:
    tool_name: str
    query: str
    result_count: int
    evidence_type: str
    succeeded: bool


@dataclass
class EvidenceState:
    attempts: list[EvidenceAttempt] = field(default_factory=list)

    def add(
        self,
        *,
        tool_name: str,
        query: str,
        result_count: int,
        succeeded: bool,
    ) -> None:
        self.attempts.append(
            EvidenceAttempt(
                tool_name=tool_name,
                query=query,
                result_count=result_count,
                evidence_type=evidence_type_for_tool(tool_name),
                succeeded=succeeded,
            )
        )

    def counts_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for attempt in self.attempts:
            counts[attempt.evidence_type] = counts.get(attempt.evidence_type, 0) + max(
                attempt.result_count, 0
            )
        return counts

    def diagnostics(self) -> list[dict[str, object]]:
        return [
            {
                "tool_name": attempt.tool_name,
                "query": truncate_runtime_text(attempt.query, 120),
                "result_count": attempt.result_count,
                "evidence_type": attempt.evidence_type,
                "succeeded": attempt.succeeded,
            }
            for attempt in self.attempts[:8]
        ]


@dataclass
class AgentRuntimeState:
    context: RuntimeContext
    evidence: EvidenceState = field(default_factory=EvidenceState)
    tool_argument_rewrites: list[ToolArgumentGrounding] = field(default_factory=list)
    stop_reason: str = "not_stopped"
    final_decision: str = "pending"

    def record_grounding(self, grounding: ToolArgumentGrounding) -> None:
        if grounding.rewrite_applied:
            self.tool_argument_rewrites.append(grounding)

    def diagnostics(self) -> dict[str, object]:
        return {
            "runtime_context_assembled": True,
            "runtime_followup_type": self.context.followup_type,
            "runtime_recent_topic": truncate_runtime_text(self.context.recent_topic, 120),
            "runtime_inherited_topic": truncate_runtime_text(
                self.context.inherited_topic, 120
            ),
            "runtime_standalone_task": truncate_runtime_text(
                self.context.standalone_task, 160
            ),
            "runtime_contextualized": self.context.contextualized,
            "runtime_contextualization_source": self.context.contextualization_source,
            "runtime_tool_arg_rewrite_count": len(self.tool_argument_rewrites),
            "runtime_tool_arg_rewrites": [
                {
                    "tool_name": item.tool_name,
                    "original_query": truncate_runtime_text(item.original_query, 100),
                    "grounded_query": truncate_runtime_text(item.grounded_query, 140),
                    "reason": item.reason,
                }
                for item in self.tool_argument_rewrites[:6]
            ],
            "runtime_evidence_attempts": self.evidence.diagnostics(),
            "runtime_evidence_counts": self.evidence.counts_by_type(),
            "runtime_stop_reason": self.stop_reason,
            "runtime_final_decision": self.final_decision,
        }


class AgentRuntime:
    """Deterministic runtime control plane for the default tool-calling agent.

    This class intentionally keeps final control in code. LLMs may later be added
    as proposal providers for contextualization, but execution and diagnostics
    remain runtime-owned.
    """

    def assemble(self, question: str, history: Sequence[str] | None = None) -> AgentRuntimeState:
        context = assemble_runtime_context(question, history=history)
        return AgentRuntimeState(context=context)

    def ground_tool_call(
        self,
        tool_call: ChatToolCall,
        *,
        state: AgentRuntimeState,
        default_query: str,
    ) -> tuple[ChatToolCall, ToolArgumentGrounding]:
        original_query = tool_query_from_arguments(tool_call.arguments, default_query)
        grounded_query, reason = grounded_query_for_tool(
            tool_name=tool_call.name,
            query=original_query,
            context=state.context,
        )
        rewrite_applied = grounded_query != original_query
        grounded_call = tool_call
        if rewrite_applied:
            grounded_args = dict(tool_call.arguments)
            grounded_args["query"] = grounded_query
            grounded_call = replace(tool_call, arguments=grounded_args)
        grounding = ToolArgumentGrounding(
            tool_name=tool_call.name,
            original_query=original_query,
            grounded_query=grounded_query,
            rewrite_applied=rewrite_applied,
            reason=reason,
        )
        state.record_grounding(grounding)
        return grounded_call, grounding


def assemble_runtime_context(
    question: str,
    *,
    history: Sequence[str] | None = None,
) -> RuntimeContext:
    normalized_question = " ".join(question.strip().split())
    normalized_history = tuple(
        " ".join(item.strip().split()) for item in (history or []) if item.strip()
    )
    recent_topic = extract_recent_topic(normalized_history)
    followup_type = classify_followup_type(normalized_question, recent_topic=recent_topic)
    inherited_topic = recent_topic if followup_type != "standalone" else ""
    if inherited_topic:
        standalone_task = build_standalone_task(
            normalized_question,
            inherited_topic=inherited_topic,
            followup_type=followup_type,
        )
    else:
        standalone_task = normalized_question
    return RuntimeContext(
        current_query=normalized_question,
        history=normalized_history,
        recent_topic=recent_topic,
        inherited_topic=inherited_topic,
        followup_type=followup_type,
        standalone_task=standalone_task,
        contextualized=bool(inherited_topic),
    )


def classify_followup_type(query: str, *, recent_topic: str) -> RuntimeFollowupType:
    if not recent_topic:
        return "standalone"
    normalized = query.casefold()
    if not looks_like_elliptical_followup(normalized):
        return "standalone"
    if contains_any(normalized, VISUAL_FOLLOWUP_TERMS):
        return "visual_evidence_request"
    if contains_any(normalized, TABLE_FOLLOWUP_TERMS):
        return "table_evidence_request"
    if contains_any(normalized, DETAIL_FOLLOWUP_TERMS):
        return "detail_expansion"
    return "standalone"


def looks_like_elliptical_followup(normalized_query: str) -> bool:
    token_count = len(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", normalized_query))
    compact_len = len(re.sub(r"\s+", "", normalized_query))
    if compact_len <= 18:
        return True
    if token_count <= 4 and contains_any(normalized_query, GENERIC_FOLLOWUP_TERMS):
        return True
    return False


def extract_recent_topic(history: Sequence[str]) -> str:
    for item in reversed(history):
        candidate = strip_history_role_prefix(item)
        if not candidate:
            continue
        if looks_like_history_answer(candidate):
            continue
        if len(candidate) > 160:
            candidate = candidate[:160]
        return trim_question_suffix(candidate)
    return ""


def strip_history_role_prefix(text: str) -> str:
    return re.sub(
        r"^\s*(user|assistant|human|ai|\u7528\u6237|\u52a9\u624b)\s*[:\uff1a]\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

def looks_like_history_answer(text: str) -> bool:
    lowered = text.casefold()
    return lowered.startswith(("answer:", "assistant:", "\u56de\u7b54\uff1a", "\u7b54\uff1a"))

def trim_question_suffix(text: str) -> str:
    return text.strip().rstrip(" ?\uff1f!\uff01\u3002")

def build_standalone_task(
    query: str,
    *,
    inherited_topic: str,
    followup_type: RuntimeFollowupType,
) -> str:
    if followup_type == "visual_evidence_request":
        visual_terms = "\u56fe\u7247 \u56fe\u793a \u7167\u7247 \u89c6\u89c9\u8bc1\u636e figure image"
        if contains_any(query, ("\u66f2\u7ebf", "curve", "plot")):
            visual_terms = f"{visual_terms} \u66f2\u7ebf curve plot"
        return f"{inherited_topic} {visual_terms}"
    if followup_type == "table_evidence_request":
        return f"{inherited_topic} \u8868\u683c \u6570\u636e \u53c2\u6570 \u5bf9\u6bd4"
    if followup_type == "detail_expansion":
        return f"{inherited_topic} \u8be6\u7ec6\u89e3\u91ca \u8865\u5145\u8bf4\u660e"
    return query

def grounded_query_for_tool(
    *,
    tool_name: str,
    query: str,
    context: RuntimeContext,
) -> tuple[str, str]:
    normalized_query = " ".join(query.strip().split())
    if not context.inherited_topic:
        return semantic_guarded_query_for_tool(
            tool_name=tool_name,
            query=normalized_query,
            context=context,
        )
    if not should_ground_tool_query(normalized_query, context=context):
        return normalized_query, "tool_query_already_specific"
    if tool_name == "search_figures":
        return (
            build_standalone_task(
                normalized_query,
                inherited_topic=context.inherited_topic,
                followup_type="visual_evidence_request",
            ),
            "grounded_visual_followup",
        )
    if tool_name == "search_tables":
        return (
            build_standalone_task(
                normalized_query,
                inherited_topic=context.inherited_topic,
                followup_type="table_evidence_request",
            ),
            "grounded_table_followup",
        )
    if tool_name in {"hybrid_search_knowledge", "search_knowledge"}:
        return context.standalone_task, "grounded_text_followup"
    return normalized_query, "unsupported_tool_not_grounded"


def semantic_guarded_query_for_tool(
    *,
    tool_name: str,
    query: str,
    context: RuntimeContext,
) -> tuple[str, str]:
    if tool_name not in {"hybrid_search_knowledge", "search_knowledge", "search_tables", "search_figures"}:
        return query, "standalone_query"
    task_identity = build_evidence_query_identity(
        context.standalone_task or context.current_query,
        history=context.history,
    )
    tool_identity = build_evidence_query_identity(query, history=context.history)
    if (
        task_identity.safe_for_cache_reuse
        and tool_identity.safe_for_cache_reuse
        and task_identity.entity_key
        and task_identity.entity_key == tool_identity.entity_key
    ):
        record_evidence_identity_on_trace(task_identity)
        if task_identity.intent_key == tool_identity.intent_key:
            return task_identity.canonical_query, "grounded_semantic_equivalent_tool_query"
        return task_identity.canonical_query, "blocked_tool_query_intent_drift"
    if (
        task_identity.entity_key
        and not task_identity.intent_key
        and tool_identity.safe_for_cache_reuse
        and task_identity.entity_key == tool_identity.entity_key
    ):
        record_evidence_identity_on_trace(tool_identity)
        return tool_identity.canonical_query, "promoted_tool_query_semantic_identity"
    return query, "standalone_query"


def record_evidence_identity_on_trace(identity: EvidenceQueryIdentity) -> None:
    trace = get_current_latency_trace()
    if trace is None:
        return
    for key, value in identity.diagnostics().items():
        trace.set_value(key, value)


def should_ground_tool_query(query: str, *, context: RuntimeContext) -> bool:
    normalized = query.casefold()
    if context.inherited_topic and context.inherited_topic in query:
        return False
    if context.followup_type != "standalone":
        return True
    return looks_like_elliptical_followup(normalized)


def evidence_type_for_tool(tool_name: str) -> str:
    if tool_name == "search_figures":
        return "figure"
    if tool_name == "search_tables":
        return "table"
    if tool_name in {"hybrid_search_knowledge", "search_knowledge"}:
        return "text"
    return "other"


def tool_query_from_arguments(arguments: dict[str, Any], default_query: str) -> str:
    query = arguments.get("query")
    if isinstance(query, str) and query.strip():
        return query.strip()
    return default_query


def contains_any(text: str, terms: Sequence[str]) -> bool:
    return any(term.casefold() in text for term in terms)


def truncate_runtime_text(text: str, limit: int) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3] + "..."
