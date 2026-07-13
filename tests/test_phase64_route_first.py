import pytest

from app.services.agent.route_first import (
    RouteDecision,
    choose_phase64_route,
    enforce_phase64_route_intent_floor,
    record_phase64_route,
)
from app.services.observability.latency_trace import LatencyTrace
from app.services.retrieval.runtime import RetrievalIntentProfile


@pytest.mark.parametrize(
    "question",
    ["堆石混凝土优势", "What are the benefits of rock-filled concrete?"],
)
def test_empty_history_ordinary_text_uses_fast_route(question: str) -> None:
    decision = choose_phase64_route(question, history=(), has_uploaded_image=False)

    assert decision.kind == "fast"
    assert decision.reason == "ordinary_text"


@pytest.mark.parametrize(
    "question",
    [
        "两者有什么关系？",
        "堆石粒径和孔隙率如何影响自密实混凝土填充效果？",
        "How does particle size affect pore structure?",
        "查参数表中的水胶比",
        "展示裂缝图片",
        "有图片资源吗？",
    ],
)
def test_explicit_complex_modalities_never_use_fast_route(question: str) -> None:
    decision = choose_phase64_route(question, history=(), has_uploaded_image=False)

    assert decision.kind == "complex"
    assert decision.reason in {
        "explicit_relationship",
        "relational_reasoning",
        "explicit_table",
        "explicit_visual",
    }


def test_followup_and_uploaded_image_are_complex() -> None:
    followup = choose_phase64_route("它呢？", history=("上一轮",), has_uploaded_image=False)
    uploaded = choose_phase64_route("分析这张图", history=(), has_uploaded_image=True)

    assert (followup.kind, followup.reason) == ("complex", "has_history")
    assert (uploaded.kind, uploaded.reason) == ("complex", "uploaded_image")


def test_route_trace_contains_only_safe_kind_reason_and_duration() -> None:
    trace = LatencyTrace()
    decision = choose_phase64_route("堆石混凝土优势", history=(), has_uploaded_image=False)

    record_phase64_route(trace, decision, elapsed_ms=12.5)

    assert trace.values["phase64_route_kind"] == "fast"
    assert trace.values["phase64_route_reason"] == "ordinary_text"
    assert trace.values["phase64_route_latency_ms"] == 12.5


def test_relational_reasoning_route_supplies_graph_intent_floor() -> None:
    profile = enforce_phase64_route_intent_floor(
        RetrievalIntentProfile(),
        RouteDecision(kind="complex", reason="relational_reasoning"),
    )

    assert profile.relationship_explicitness == "explicit"
    assert profile.relationship_intent >= 0.85
    assert profile.relationship_type == "causal_effect"
    assert profile.graph_search_mode == "local"
    assert "relationship" in profile.required_evidence_types


def test_relational_route_floor_preserves_explicit_negative_request() -> None:
    profile = enforce_phase64_route_intent_floor(
        RetrievalIntentProfile(relationship_explicitness="negative"),
        RouteDecision(kind="complex", reason="relational_reasoning"),
    )

    assert profile.relationship_explicitness == "negative"
    assert profile.relationship_type == "none"
