from __future__ import annotations

from typing import Literal

from app.services.agent.react_actions import ReActAction, ReActActionType
from app.services.observability.latency_trace import LatencyTrace


AdaptiveRetrievalStrategy = Literal[
    "none",
    "hybrid_knowledge_search",
    "graph_enhanced_search",
    "table_search",
    "figure_search",
    "user_image_analysis",
    "query_rewrite",
    "answer_from_retrieved_evidence",
    "answer_from_prior_evidence",
    "safe_refusal",
    "final_answer",
]


ACTION_STRATEGY_MAP: dict[ReActActionType, AdaptiveRetrievalStrategy] = {
    "search_knowledge": "hybrid_knowledge_search",
    "search_graph_knowledge": "graph_enhanced_search",
    "search_tables": "table_search",
    "search_figures": "figure_search",
    "analyze_user_image": "user_image_analysis",
    "rewrite_query": "query_rewrite",
    "answer_with_citations": "answer_from_retrieved_evidence",
    "refuse": "safe_refusal",
    "final_answer": "final_answer",
}


def adaptive_strategy_for_action(
    action: ReActAction | ReActActionType,
    *,
    use_prior_evidence: bool = False,
) -> AdaptiveRetrievalStrategy:
    action_name = action.action if isinstance(action, ReActAction) else action
    if action_name == "answer_with_citations" and use_prior_evidence:
        return "answer_from_prior_evidence"
    return ACTION_STRATEGY_MAP.get(action_name, "none")


def record_adaptive_strategy(
    trace: LatencyTrace | None,
    action: ReActAction | ReActActionType,
    *,
    use_prior_evidence: bool = False,
) -> AdaptiveRetrievalStrategy:
    strategy = adaptive_strategy_for_action(
        action,
        use_prior_evidence=use_prior_evidence,
    )
    if trace is not None:
        trace.set_value("retrieval_strategy", strategy)
    return strategy
