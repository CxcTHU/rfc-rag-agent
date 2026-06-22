from __future__ import annotations

from typing import Any, Literal, TypedDict

from app.services.agent.react_actions import ReActObservation, ReActStepRecord
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
)


LangGraphAgentRoute = Literal[
    "search_knowledge",
    "search_figures",
    "search_tables",
    "analyze_user_image",
    "rewrite_query",
    "answer_with_citations",
    "refuse",
    "final_answer",
]


class LangGraphAgentState(TypedDict, total=False):
    question: str
    normalized_question: str
    history: list[str]
    top_k: int
    source_id: str | None
    max_iterations: int
    iteration_count: int
    next_action: LangGraphAgentRoute
    current_query: str
    image_path: str | None
    previous_queries: list[str]
    observations: list[dict[str, Any]]
    workflow_steps: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    search_results: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    citations: list[int]
    prior_sources: list[dict[str, Any]]
    prior_citations: list[int]
    prior_answer_summary: str
    image_analysis: dict[str, object] | None
    answer: str
    refused: bool
    refusal_reason: str | None
    latency_trace: dict[str, object]
    _toolbox: Any
    _event_sink: Any
