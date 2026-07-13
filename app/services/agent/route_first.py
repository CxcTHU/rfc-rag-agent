from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Sequence

from app.services.retrieval.runtime import RetrievalIntentProfile, deterministic_intent_profile


RouteKind = Literal["fast", "complex"]

RELATIONAL_REASONING_MARKERS = (
    "如何影响",
    "影响",
    "如何作用",
    "导致",
    "因果",
    "机制",
    "how does",
    "affect",
    "influence",
    "impact",
    "cause",
    "mechanism",
)


@dataclass(frozen=True)
class RouteDecision:
    kind: RouteKind
    reason: str


def choose_phase64_route(
    question: str,
    *,
    history: Sequence[str],
    has_uploaded_image: bool,
) -> RouteDecision:
    """Choose the narrow no-planner path without changing retrieval semantics."""
    if has_uploaded_image:
        return RouteDecision(kind="complex", reason="uploaded_image")
    if history:
        return RouteDecision(kind="complex", reason="has_history")
    if any(marker in question.casefold() for marker in RELATIONAL_REASONING_MARKERS):
        return RouteDecision(kind="complex", reason="relational_reasoning")

    profile = deterministic_intent_profile(question)
    if profile.relationship_explicitness == "explicit":
        return RouteDecision(kind="complex", reason="explicit_relationship")
    if profile.table_explicitness == "explicit":
        return RouteDecision(kind="complex", reason="explicit_table")
    if profile.visual_explicitness == "explicit":
        return RouteDecision(kind="complex", reason="explicit_visual")
    return RouteDecision(kind="fast", reason="ordinary_text")


def enforce_phase64_route_intent_floor(
    profile: RetrievalIntentProfile,
    decision: RouteDecision,
) -> RetrievalIntentProfile:
    """Retain an explicit causal-route signal if planner JSON omits it.

    This is deliberately available only to the Phase 64 B route. A negative
    relationship request remains authoritative and is never promoted.
    """
    normalized = profile.normalized()
    if (
        decision.reason != "relational_reasoning"
        or normalized.relationship_explicitness == "negative"
    ):
        return normalized

    required_evidence_types = tuple(
        dict.fromkeys((*normalized.required_evidence_types, "relationship"))
    )
    return replace(
        normalized,
        relationship_intent=max(0.85, normalized.relationship_intent),
        relationship_type=(
            normalized.relationship_type
            if normalized.relationship_type != "none"
            else "causal_effect"
        ),
        graph_search_mode="local",
        relationship_explicitness="explicit",
        required_evidence_types=required_evidence_types,
        source=f"{normalized.source}+phase64_route_floor",
    ).normalized()


def record_phase64_route(
    trace: object,
    decision: RouteDecision,
    *,
    elapsed_ms: float,
) -> None:
    """Record only stable routing diagnostics, never user content."""
    trace.set_value("phase64_route_kind", decision.kind)
    trace.set_value("phase64_route_reason", decision.reason)
    trace.add_duration("phase64_route_latency_ms", elapsed_ms)
