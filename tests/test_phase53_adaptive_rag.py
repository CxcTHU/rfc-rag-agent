from __future__ import annotations

from app.services.agent.adaptive_retrieval import adaptive_strategy_for_action
from app.services.agent.react_actions import ReActAction
from app.services.observability.latency_trace import LatencyTrace


def test_adaptive_strategy_labels_existing_planner_actions() -> None:
    assert (
        adaptive_strategy_for_action(
            ReActAction(
                action="search_knowledge",
                query="filling capacity",
                reasoning_summary="search first",
            )
        )
        == "hybrid_knowledge_search"
    )
    assert (
        adaptive_strategy_for_action(
            ReActAction(
                action="search_graph_knowledge",
                query="standard reference chain",
                reasoning_summary="graph search",
            )
        )
        == "graph_enhanced_search"
    )
    assert adaptive_strategy_for_action("search_tables") == "table_search"
    assert adaptive_strategy_for_action("search_figures") == "figure_search"
    assert adaptive_strategy_for_action("refuse") == "safe_refusal"


def test_adaptive_strategy_distinguishes_prior_evidence_answers() -> None:
    action = ReActAction(
        action="answer_with_citations",
        question="please expand",
        reasoning_summary="reuse prior evidence",
    )

    assert adaptive_strategy_for_action(action) == "answer_from_retrieved_evidence"
    assert (
        adaptive_strategy_for_action(action, use_prior_evidence=True)
        == "answer_from_prior_evidence"
    )


def test_latency_trace_defaults_to_no_retrieval_strategy() -> None:
    trace = LatencyTrace()

    assert trace.values["retrieval_strategy"] == "none"
