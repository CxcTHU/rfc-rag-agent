from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from collections.abc import Sequence
from typing import Literal
from typing import Protocol
from typing import Any

from app.services.conversation.session_memory import (
    SessionMemory,
    augment_query_with_session_memory,
    build_session_memory,
    refine_memory_for_question,
    is_correction_question,
    memory_item_from_state,
)
from app.services.generation.chat_model import ChatMessage, ChatModelProvider
from app.services.retrieval.embedding import EmbeddingProvider


MEMORY_CONTEXT_SCHEMA_VERSION = 1
MEMORY_TRACE_FIELDS: tuple[str, ...] = (
    "memory_context_present",
    "memory_session_entity_count",
    "memory_session_anchor_count",
    "memory_session_stale_anchor_count",
    "memory_prior_source_count",
    "memory_prior_citation_count",
    "memory_prior_relevance_score",
    "memory_prior_relevance_passed",
    "memory_long_term_enabled",
    "memory_intent_label",
    "memory_intent_confidence",
    "memory_intent_source",
    "memory_decision_hint",
    "memory_policy_route",
    "memory_used_for_planning",
    "memory_used_for_retrieval",
    "memory_used_for_answer",
    "memory_prior_evidence_used_for_answer",
    "memory_citation_source",
    "memory_refusal_boundary",
)

MemoryIntentLabel = Literal[
    "expand_followup",
    "contextual_followup",
    "correction",
    "new_topic",
    "off_topic",
]
VALID_MEMORY_INTENTS: set[str] = {
    "expand_followup",
    "contextual_followup",
    "correction",
    "new_topic",
    "off_topic",
}

EXPAND_FOLLOWUP_TERMS = (
    "详细",
    "展开",
    "补充",
    "继续",
    "detail",
    "expand",
    "continue",
    "elaborate",
)
CONTEXT_REFERENCE_TERMS = (
    "它",
    "这个",
    "这项",
    "这种",
    "上面",
    "刚才",
    "that",
    "it",
)


@dataclass(frozen=True)
class PriorEvidenceMemory:
    sources: tuple[dict[str, Any], ...] = ()
    citations: tuple[int, ...] = ()
    answer_summary: str = ""

    @property
    def source_count(self) -> int:
        return len(self.sources)


@dataclass(frozen=True)
class PriorEvidenceRelevance:
    score: float = 0.0
    passed: bool = False
    threshold: float = 0.5
    reason: str = "no prior evidence"

    def to_state_dict(self) -> dict[str, Any]:
        return asdict(self)


class PriorEvidenceRelevanceGate:
    """Embedding-based gate for reusing prior evidence."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        *,
        threshold: float = 0.5,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.threshold = threshold

    def evaluate(
        self,
        *,
        question: str,
        prior: PriorEvidenceMemory,
        history: Sequence[str] = (),
    ) -> PriorEvidenceRelevance:
        if prior.source_count <= 0:
            return PriorEvidenceRelevance(threshold=self.threshold)
        prior_summary = prior_relevance_summary(prior)
        if not prior_summary:
            return PriorEvidenceRelevance(
                threshold=self.threshold,
                reason="prior evidence has no reusable summary",
            )
        if self.embedding_provider is None:
            return PriorEvidenceRelevance(
                score=1.0,
                passed=True,
                threshold=self.threshold,
                reason="embedding provider unavailable; prior summary present",
            )
        comparison_text = build_prior_relevance_query(question=question, history=history)
        try:
            vectors = self.embedding_provider.embed_texts(
                [comparison_text, prior_summary]
            )
        except Exception:
            return PriorEvidenceRelevance(
                threshold=self.threshold,
                reason="embedding provider failed",
            )
        if len(vectors) != 2:
            return PriorEvidenceRelevance(
                threshold=self.threshold,
                reason="embedding provider returned unexpected vector count",
            )
        score = cosine_similarity(vectors[0], vectors[1])
        return PriorEvidenceRelevance(
            score=score,
            passed=score >= self.threshold,
            threshold=self.threshold,
            reason="embedding similarity",
        )


@dataclass(frozen=True)
class LongTermMemoryState:
    enabled: bool = False
    status: str = "disabled"
    read_count: int = 0
    write_count: int = 0


@dataclass(frozen=True)
class MemoryConsent:
    user_id: str | None = None
    conversation_id: str | None = None
    long_term_memory_enabled: bool = False
    source: str = "default_disabled"


@dataclass(frozen=True)
class MemoryRetentionPolicy:
    status: str = "disabled"
    max_age_days: int | None = None
    deletion_supported: bool = True


@dataclass(frozen=True)
class MemoryDeletionRequest:
    user_id: str | None = None
    conversation_id: str | None = None
    reason: str = "user_or_policy_request"


@dataclass(frozen=True)
class MemoryAuditRecord:
    operation: str
    status: str
    user_id_present: bool = False
    conversation_id_present: bool = False
    detail: str = ""


@dataclass(frozen=True)
class MemoryPolicyDecision:
    decision_hint: str = "no_memory"
    planner_route: str = "search_without_memory"
    use_prior_evidence_for_answer: bool = False
    augment_retrieval_query: bool = False
    memory_used_for_planning: bool = False
    memory_used_for_retrieval: bool = False
    memory_used_for_answer: bool = False
    memory_citation_source: bool = False
    prior_relevance_score: float = 0.0
    prior_relevance_passed: bool = False
    refusal_boundary: str = "none"
    reason: str = "no usable memory context"

    def to_state_dict(self) -> dict[str, Any]:
        return asdict(self)

    def trace(self) -> dict[str, object]:
        return {
            "memory_policy_route": self.planner_route,
            "memory_used_for_planning": self.memory_used_for_planning,
            "memory_used_for_retrieval": self.memory_used_for_retrieval,
            "memory_used_for_answer": self.memory_used_for_answer,
            "memory_prior_evidence_used_for_answer": self.use_prior_evidence_for_answer,
            "memory_citation_source": self.memory_citation_source,
            "memory_prior_relevance_score": self.prior_relevance_score,
            "memory_prior_relevance_passed": self.prior_relevance_passed,
            "memory_refusal_boundary": self.refusal_boundary,
        }


@dataclass(frozen=True)
class MemoryIntent:
    label: MemoryIntentLabel = "new_topic"
    confidence: float = 1.0
    source: str = "deterministic"
    reason: str = "default"

    def to_state_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryIntentClassifier(Protocol):
    def classify(
        self,
        *,
        question: str,
        history: Sequence[str],
        prior_answer_summary: str = "",
    ) -> MemoryIntent:
        """Classify the current turn's relationship to short-term memory."""


class DeterministicMemoryIntentClassifier:
    """Rule-based classifier that preserves the Phase 52A-F behavior."""

    def classify(
        self,
        *,
        question: str,
        history: Sequence[str],
        prior_answer_summary: str = "",
    ) -> MemoryIntent:
        del history, prior_answer_summary
        if is_correction_question(question):
            return MemoryIntent(
                label="correction",
                confidence=1.0,
                source="deterministic",
                reason="matched correction terms",
            )
        if is_expand_followup_question(question):
            return MemoryIntent(
                label="expand_followup",
                confidence=1.0,
                source="deterministic",
                reason="matched expand follow-up terms",
            )
        if is_contextual_followup_question(question):
            return MemoryIntent(
                label="contextual_followup",
                confidence=0.9,
                source="deterministic",
                reason="matched contextual reference terms",
            )
        return MemoryIntent(
            label="new_topic",
            confidence=0.8,
            source="deterministic",
            reason="no memory intent terms matched",
        )


class LLMMemoryIntentClassifier:
    """LLM classifier with deterministic fallback for unavailable or invalid output."""

    def __init__(
        self,
        provider: ChatModelProvider,
        *,
        fallback: MemoryIntentClassifier | None = None,
    ) -> None:
        self.provider = provider
        self.fallback = fallback or DeterministicMemoryIntentClassifier()

    def classify(
        self,
        *,
        question: str,
        history: Sequence[str],
        prior_answer_summary: str = "",
    ) -> MemoryIntent:
        try:
            result = self.provider.generate(
                build_memory_intent_messages(
                    question=question,
                    history=history,
                    prior_answer_summary=prior_answer_summary,
                )
            )
            intent = parse_memory_intent_json(result.answer, source="llm")
        except Exception:
            return self.fallback.classify(
                question=question,
                history=history,
                prior_answer_summary=prior_answer_summary,
            )
        if intent.label == "new_topic" and is_expand_followup_question(question):
            return self.fallback.classify(
                question=question,
                history=history,
                prior_answer_summary=prior_answer_summary,
            )
        if intent.label == "correction" and not is_correction_question(question):
            return self.fallback.classify(
                question=question,
                history=history,
                prior_answer_summary=prior_answer_summary,
            )
        return intent


class LongTermMemoryProvider(Protocol):
    def read(self, *, user_id: str | None, conversation_id: str | None) -> LongTermMemoryState:
        """Return long-term memory state without exposing stored profile content."""

    def write(self, *, user_id: str | None, conversation_id: str | None, payload: dict[str, Any]) -> LongTermMemoryState:
        """Persist long-term memory when explicitly enabled by a future phase."""

    def delete(self, request: MemoryDeletionRequest) -> MemoryAuditRecord:
        """Delete long-term memory when a future enabled provider supports persistence."""


class DisabledLongTermMemoryProvider:
    """Default provider: long-term memory is explicitly disabled in Phase 52."""

    def read(self, *, user_id: str | None = None, conversation_id: str | None = None) -> LongTermMemoryState:
        return LongTermMemoryState()

    def write(
        self,
        *,
        user_id: str | None = None,
        conversation_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> LongTermMemoryState:
        return LongTermMemoryState()

    def delete(self, request: MemoryDeletionRequest) -> MemoryAuditRecord:
        return MemoryAuditRecord(
            operation="delete",
            status="disabled_noop",
            user_id_present=bool(request.user_id),
            conversation_id_present=bool(request.conversation_id),
            detail="long-term memory is disabled",
        )


@dataclass(frozen=True)
class AgentMemoryContext:
    session: SessionMemory = field(default_factory=SessionMemory)
    prior_evidence: PriorEvidenceMemory = field(default_factory=PriorEvidenceMemory)
    prior_relevance: PriorEvidenceRelevance = field(default_factory=PriorEvidenceRelevance)
    long_term: LongTermMemoryState = field(default_factory=LongTermMemoryState)
    intent: MemoryIntent = field(default_factory=MemoryIntent)
    decision_hint: str = "no_memory"
    policy: MemoryPolicyDecision = field(default_factory=MemoryPolicyDecision)

    @property
    def has_memory(self) -> bool:
        return (
            not self.session.empty
            or self.prior_evidence.source_count > 0
            or self.long_term.enabled
        )

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MEMORY_CONTEXT_SCHEMA_VERSION,
            "session": {
                "entities": [item.to_state_dict() for item in self.session.entities],
                "retrieval_anchors": [
                    item.to_state_dict() for item in self.session.retrieval_anchors
                ],
                "constraints": list(self.session.constraints),
                "stale_anchors": [
                    item.to_state_dict() for item in self.session.stale_anchors
                ],
            },
            "prior_evidence": {
                "sources": list(self.prior_evidence.sources),
                "citations": list(self.prior_evidence.citations),
                "answer_summary": self.prior_evidence.answer_summary,
            },
            "prior_relevance": self.prior_relevance.to_state_dict(),
            "long_term": asdict(self.long_term),
            "intent": self.intent.to_state_dict(),
            "decision_hint": self.decision_hint,
            "policy": self.policy.to_state_dict(),
        }

    def trace(self) -> dict[str, object]:
        trace = {
            "memory_context_present": self.has_memory,
            "memory_session_entity_count": len(self.session.entities),
            "memory_session_anchor_count": len(self.session.retrieval_anchors),
            "memory_session_stale_anchor_count": len(self.session.stale_anchors),
            "memory_prior_source_count": self.prior_evidence.source_count,
            "memory_prior_citation_count": len(self.prior_evidence.citations),
            "memory_prior_relevance_score": self.prior_relevance.score,
            "memory_prior_relevance_passed": self.prior_relevance.passed,
            "memory_long_term_enabled": self.long_term.enabled,
            "memory_intent_label": self.intent.label,
            "memory_intent_confidence": self.intent.confidence,
            "memory_intent_source": self.intent.source,
            "memory_decision_hint": self.decision_hint,
        }
        trace.update(self.policy.trace())
        return trace


def build_agent_memory_context(
    *,
    question: str,
    history: list[str],
    prior_evidence: dict[str, Any] | None = None,
    intent_classifier: MemoryIntentClassifier | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    relevance_gate: PriorEvidenceRelevanceGate | None = None,
) -> AgentMemoryContext:
    prior = prior_evidence_memory_from_state(prior_evidence or {})
    classifier = intent_classifier or DeterministicMemoryIntentClassifier()
    intent = classifier.classify(
        question=question,
        history=history,
        prior_answer_summary=prior.answer_summary,
    )
    session = refine_memory_for_question(
        question,
        build_session_memory(history),
        correction_override=intent.label == "correction",
    )
    prior_relevance = (relevance_gate or PriorEvidenceRelevanceGate(embedding_provider)).evaluate(
        question=question,
        prior=prior,
        history=history,
    )
    decision_hint = infer_memory_decision_hint(
        session=session,
        prior=prior,
        intent=intent,
        prior_relevance=prior_relevance,
    )
    policy = decide_memory_policy(
        session=session,
        prior=prior,
        intent=intent,
        prior_relevance=prior_relevance,
        decision_hint=decision_hint,
    )
    return AgentMemoryContext(
        session=session,
        prior_evidence=prior,
        prior_relevance=prior_relevance,
        long_term=LongTermMemoryState(),
        intent=intent,
        decision_hint=decision_hint,
        policy=policy,
    )


def agent_memory_context_from_state(value: dict[str, Any] | None) -> AgentMemoryContext:
    if not isinstance(value, dict):
        return AgentMemoryContext()
    session_raw = value.get("session") if isinstance(value.get("session"), dict) else {}
    prior_raw = value.get("prior_evidence") if isinstance(value.get("prior_evidence"), dict) else {}
    relevance_raw = value.get("prior_relevance") if isinstance(value.get("prior_relevance"), dict) else {}
    long_raw = value.get("long_term") if isinstance(value.get("long_term"), dict) else {}
    intent_raw = value.get("intent") if isinstance(value.get("intent"), dict) else {}
    policy_raw = value.get("policy") if isinstance(value.get("policy"), dict) else {}
    decision_hint = str(value.get("decision_hint") or policy_raw.get("decision_hint") or "no_memory")
    session = SessionMemory(
        entities=tuple(
            item
            for item in (
                memory_item_from_state(raw)
                for raw in session_raw.get("entities", [])
            )
            if item is not None
        ),
        retrieval_anchors=tuple(
            item
            for item in (
                memory_item_from_state(raw)
                for raw in session_raw.get("retrieval_anchors", [])
            )
            if item is not None
        ),
        constraints=tuple(str(item) for item in session_raw.get("constraints", []) if str(item).strip()),
        stale_anchors=tuple(
            item
            for item in (
                memory_item_from_state(raw)
                for raw in session_raw.get("stale_anchors", [])
            )
            if item is not None
        ),
    )
    prior = PriorEvidenceMemory(
        sources=tuple(
            item for item in prior_raw.get("sources", []) if isinstance(item, dict)
        ),
        citations=tuple(
            int(item)
            for item in prior_raw.get("citations", [])
            if isinstance(item, int) or (isinstance(item, str) and item.isdigit())
        ),
        answer_summary=str(prior_raw.get("answer_summary") or ""),
    )
    intent = memory_intent_from_state(intent_raw)
    return AgentMemoryContext(
        session=session,
        prior_evidence=prior,
        prior_relevance=prior_evidence_relevance_from_state(relevance_raw),
        long_term=LongTermMemoryState(
            enabled=bool(long_raw.get("enabled", False)),
            status=str(long_raw.get("status") or "disabled"),
            read_count=int(long_raw.get("read_count") or 0),
            write_count=int(long_raw.get("write_count") or 0),
        ),
        intent=intent,
        decision_hint=decision_hint,
        policy=memory_policy_from_state(
            policy_raw,
            session=session,
            prior=prior,
            decision_hint=decision_hint,
            prior_relevance=prior_evidence_relevance_from_state(relevance_raw),
        ),
    )


def prior_evidence_memory_from_state(state: dict[str, Any]) -> PriorEvidenceMemory:
    sources = state.get("prior_sources") or []
    citations = state.get("prior_citations") or []
    return PriorEvidenceMemory(
        sources=tuple(item for item in sources if isinstance(item, dict)),
        citations=tuple(
            int(item)
            for item in citations
            if isinstance(item, int) or (isinstance(item, str) and item.isdigit())
        ),
        answer_summary=str(state.get("prior_answer_summary") or ""),
    )


def memory_intent_from_state(value: dict[str, Any]) -> MemoryIntent:
    label = str(value.get("label") or "new_topic")
    if label not in VALID_MEMORY_INTENTS:
        label = "new_topic"
    confidence = clamp_confidence(value.get("confidence"), default=0.0)
    source = str(value.get("source") or "restored")
    reason = str(value.get("reason") or "restored from state")
    return MemoryIntent(
        label=label,  # type: ignore[arg-type]
        confidence=confidence,
        source=source,
        reason=reason,
    )


def prior_evidence_relevance_from_state(value: dict[str, Any]) -> PriorEvidenceRelevance:
    return PriorEvidenceRelevance(
        score=clamp_confidence(value.get("score"), default=0.0),
        passed=bool(value.get("passed", False)),
        threshold=clamp_confidence(value.get("threshold"), default=0.5),
        reason=str(value.get("reason") or "restored from state"),
    )


def infer_memory_decision_hint(
    *,
    session: SessionMemory,
    prior: PriorEvidenceMemory,
    intent: MemoryIntent,
    prior_relevance: PriorEvidenceRelevance,
) -> str:
    if session.stale_anchors:
        return "stale_anchor_refresh_search"
    if prior_relevance.passed and intent.label == "expand_followup":
        return "reuse_prior_evidence"
    if prior.source_count and intent.label == "contextual_followup":
        return "prior_evidence_available"
    if not session.empty:
        return "session_memory_retrieval_hint"
    return "no_memory"


def decide_memory_policy(
    *,
    session: SessionMemory,
    prior: PriorEvidenceMemory,
    intent: MemoryIntent,
    prior_relevance: PriorEvidenceRelevance,
    decision_hint: str,
) -> MemoryPolicyDecision:
    has_session = not session.empty
    has_prior = prior.source_count > 0
    planning = has_session or has_prior
    if intent.label == "off_topic":
        return MemoryPolicyDecision(
            decision_hint=decision_hint,
            planner_route="refuse_or_clarify",
            memory_used_for_planning=planning,
            prior_relevance_score=prior_relevance.score,
            prior_relevance_passed=prior_relevance.passed,
            refusal_boundary="off_topic_memory_not_applicable",
            reason="off-topic requests must not use conversation memory as evidence or retrieval context",
        )
    recent_topic_shift = has_recent_session_topic_shift(session, prior_relevance)
    use_prior = (
        prior_relevance.passed
        and not recent_topic_shift
        and not session.stale_anchors
        and intent.label == "expand_followup"
        and decision_hint == "reuse_prior_evidence"
    )
    augment_retrieval = has_session and (
        intent.label in {"contextual_followup", "correction"} or bool(session.stale_anchors)
    )

    if session.stale_anchors:
        return MemoryPolicyDecision(
            decision_hint=decision_hint,
            planner_route="refresh_search_ignore_stale_memory",
            augment_retrieval_query=augment_retrieval,
            memory_used_for_planning=planning,
            memory_used_for_retrieval=augment_retrieval,
            prior_relevance_score=prior_relevance.score,
            prior_relevance_passed=prior_relevance.passed,
            refusal_boundary="stale_anchor_requires_fresh_evidence",
            reason="stale session anchors prevent prior evidence reuse",
        )
    if use_prior:
        return MemoryPolicyDecision(
            decision_hint=decision_hint,
            planner_route="answer_from_prior_evidence",
            use_prior_evidence_for_answer=True,
            memory_used_for_planning=planning,
            memory_used_for_answer=True,
            prior_relevance_score=prior_relevance.score,
            prior_relevance_passed=prior_relevance.passed,
            reason="expand follow-up has sufficient prior evidence",
        )
    if planning:
        return MemoryPolicyDecision(
            decision_hint=decision_hint,
            planner_route="search_with_memory_context",
            augment_retrieval_query=augment_retrieval,
            memory_used_for_planning=True,
            memory_used_for_retrieval=augment_retrieval,
            prior_relevance_score=prior_relevance.score,
            prior_relevance_passed=prior_relevance.passed,
            refusal_boundary="memory_is_not_evidence",
            reason="memory may guide planning or retrieval but cannot answer without evidence",
        )
    return MemoryPolicyDecision()


def has_recent_session_topic_shift(
    session: SessionMemory,
    prior_relevance: PriorEvidenceRelevance,
    *,
    direct_reuse_threshold: float = 0.75,
) -> bool:
    if session.empty or not session.retrieval_anchors:
        return False
    latest_anchor_turn = max(item.turn_index for item in session.retrieval_anchors)
    return latest_anchor_turn >= 3 and prior_relevance.score < direct_reuse_threshold


def memory_policy_from_state(
    value: dict[str, Any],
    *,
    session: SessionMemory,
    prior: PriorEvidenceMemory,
    decision_hint: str,
    prior_relevance: PriorEvidenceRelevance | None = None,
) -> MemoryPolicyDecision:
    if not value:
        return infer_policy_from_decision_hint(
            session=session,
            prior=prior,
            decision_hint=decision_hint,
            prior_relevance=prior_relevance,
        )
    return MemoryPolicyDecision(
        decision_hint=str(value.get("decision_hint") or decision_hint),
        planner_route=str(value.get("planner_route") or "search_without_memory"),
        use_prior_evidence_for_answer=bool(value.get("use_prior_evidence_for_answer", False)),
        augment_retrieval_query=bool(value.get("augment_retrieval_query", False)),
        memory_used_for_planning=bool(value.get("memory_used_for_planning", False)),
        memory_used_for_retrieval=bool(value.get("memory_used_for_retrieval", False)),
        memory_used_for_answer=bool(value.get("memory_used_for_answer", False)),
        memory_citation_source=bool(value.get("memory_citation_source", False)),
        prior_relevance_score=float(value.get("prior_relevance_score") or 0.0),
        prior_relevance_passed=bool(value.get("prior_relevance_passed", False)),
        refusal_boundary=str(value.get("refusal_boundary") or "none"),
        reason=str(value.get("reason") or ""),
    )


def infer_policy_from_decision_hint(
    *,
    session: SessionMemory,
    prior: PriorEvidenceMemory,
    decision_hint: str,
    prior_relevance: PriorEvidenceRelevance | None = None,
) -> MemoryPolicyDecision:
    relevance = prior_relevance or PriorEvidenceRelevance()
    has_memory = not session.empty or prior.source_count > 0
    if decision_hint == "reuse_prior_evidence":
        return MemoryPolicyDecision(
            decision_hint=decision_hint,
            planner_route="answer_from_prior_evidence",
            use_prior_evidence_for_answer=True,
            memory_used_for_planning=has_memory,
            memory_used_for_answer=True,
            prior_relevance_score=relevance.score,
            prior_relevance_passed=relevance.passed,
            reason="legacy state allows prior evidence reuse",
        )
    if decision_hint == "stale_anchor_refresh_search":
        return MemoryPolicyDecision(
            decision_hint=decision_hint,
            planner_route="refresh_search_ignore_stale_memory",
            augment_retrieval_query=not session.empty,
            memory_used_for_planning=has_memory,
            memory_used_for_retrieval=not session.empty,
            prior_relevance_score=relevance.score,
            prior_relevance_passed=relevance.passed,
            refusal_boundary="stale_anchor_requires_fresh_evidence",
            reason="legacy state marks stale anchors",
        )
    if has_memory:
        return MemoryPolicyDecision(
            decision_hint=decision_hint,
            planner_route="search_with_memory_context",
            augment_retrieval_query=decision_hint == "session_memory_retrieval_hint",
            memory_used_for_planning=True,
            memory_used_for_retrieval=decision_hint == "session_memory_retrieval_hint",
            prior_relevance_score=relevance.score,
            prior_relevance_passed=relevance.passed,
            refusal_boundary="memory_is_not_evidence",
            reason="legacy state contains memory context",
        )
    return MemoryPolicyDecision(decision_hint=decision_hint)


def should_use_prior_evidence_for_answer(context: AgentMemoryContext, question: str) -> bool:
    del question
    return (
        context.policy.use_prior_evidence_for_answer
        and context.prior_evidence.source_count > 0
        and not context.session.stale_anchors
    )


def augment_query_with_agent_memory(query: str, context: AgentMemoryContext) -> str:
    if context.session.empty:
        return query
    if not context.policy.augment_retrieval_query:
        return query
    if not is_contextual_followup_question(query) and not context.session.stale_anchors:
        return query
    return augment_query_with_session_memory(query, context.session)


def is_expand_followup_question(question: str) -> bool:
    normalized = question.casefold().strip()
    return bool(normalized) and len(normalized) <= 80 and any(
        term in normalized for term in EXPAND_FOLLOWUP_TERMS
    )


def is_contextual_followup_question(question: str) -> bool:
    normalized = question.casefold()
    if any(
        term in normalized
        for term in CONTEXT_REFERENCE_TERMS
        if term not in {"it", "that"}
    ):
        return True
    return bool(re.search(r"\b(it|that)\b", normalized))


def build_prior_relevance_query(*, question: str, history: Sequence[str]) -> str:
    recent_history = " ".join(item.strip() for item in history[-3:] if item.strip())
    if recent_history:
        return f"{recent_history} {question}".strip()
    return question.strip()


def prior_relevance_summary(prior: PriorEvidenceMemory, *, limit: int = 500) -> str:
    if prior.answer_summary.strip():
        return prior.answer_summary.strip()[:limit]
    parts: list[str] = []
    for source in prior.sources[:5]:
        for key in ("content", "table_content", "document_title", "title"):
            value = str(source.get(key) or "").strip()
            if value:
                parts.append(value)
                break
    return " ".join(parts)[:limit].strip()


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def build_memory_intent_messages(
    *,
    question: str,
    history: Sequence[str],
    prior_answer_summary: str = "",
) -> list[ChatMessage]:
    recent_history = "\n".join(item.strip() for item in history[-6:] if item.strip()) or "(none)"
    prior_summary = prior_answer_summary.strip() or "(none)"
    system_prompt = (
        "Classify the user's current question for a RAG agent memory policy. "
        "Return only JSON with keys intent, confidence, and reason. "
        "Allowed intents: expand_followup, contextual_followup, correction, new_topic, off_topic."
    )
    user_prompt = (
        "Few-shot examples:\n"
        'Q: "please expand" -> {"intent":"expand_followup","confidence":0.95,"reason":"asks to expand prior answer"}\n'
        'Q: "what about that method?" -> {"intent":"contextual_followup","confidence":0.9,"reason":"refers to prior context"}\n'
        'Q: "correction, I meant thermal cracking" -> {"intent":"correction","confidence":0.95,"reason":"corrects prior anchor"}\n'
        'Q: "how do I cook pasta?" -> {"intent":"off_topic","confidence":0.8,"reason":"not about the RFC corpus"}\n\n'
        f"Recent history:\n{recent_history}\n\n"
        f"Prior answer summary:\n{prior_summary}\n\n"
        f"Current question:\n{question}\n\n"
        "Return compact JSON only."
    )
    return [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]


def parse_memory_intent_json(payload: str, *, source: str) -> MemoryIntent:
    stripped = payload.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.casefold().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("memory intent response did not contain a JSON object")
        decoded = json.loads(stripped[start : end + 1])
    if not isinstance(decoded, dict):
        raise ValueError("memory intent response must be a JSON object")
    label = str(decoded.get("intent") or decoded.get("label") or "").strip()
    if label not in VALID_MEMORY_INTENTS:
        raise ValueError(f"unsupported memory intent: {label}")
    return MemoryIntent(
        label=label,  # type: ignore[arg-type]
        confidence=clamp_confidence(decoded.get("confidence"), default=0.5),
        source=source,
        reason=str(decoded.get("reason") or "classified by LLM"),
    )


def clamp_confidence(value: Any, *, default: float) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, confidence))
