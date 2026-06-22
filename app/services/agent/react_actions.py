from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.services.agent.tools import AgentToolResult, truncate_text


ReActActionType = Literal[
    "search_knowledge",
    "search_figures",
    "search_tables",
    "analyze_user_image",
    "rewrite_query",
    "answer_with_citations",
    "refuse",
    "final_answer",
]

READ_ONLY_REACT_ACTIONS: tuple[ReActActionType, ...] = (
    "search_knowledge",
    "search_figures",
    "search_tables",
    "analyze_user_image",
    "rewrite_query",
    "answer_with_citations",
    "refuse",
    "final_answer",
)

REACT_TOOL_TO_AGENT_TOOL: dict[ReActActionType, str | None] = {
    "search_knowledge": "hybrid_search_knowledge",
    "search_figures": "search_figures",
    "search_tables": "search_tables",
    "analyze_user_image": "analyze_user_image",
    "rewrite_query": None,
    "answer_with_citations": "answer_with_citations",
    "refuse": None,
    "final_answer": None,
}


class ReActAction(BaseModel):
    action: ReActActionType
    query: str | None = None
    question: str | None = None
    image_path: str | None = None
    answer: str | None = None
    refusal_reason: str | None = None
    reasoning_summary: str = Field(min_length=1)
    input_summary: str | None = None

    @field_validator(
        "query",
        "question",
        "image_path",
        "answer",
        "refusal_reason",
        "reasoning_summary",
        "input_summary",
    )
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_action_payload(self) -> ReActAction:
        if self.action in {
            "search_knowledge",
            "search_figures",
            "search_tables",
            "rewrite_query",
        } and not self.query:
            raise ValueError(f"{self.action} requires query")
        if self.action == "analyze_user_image" and not (self.image_path and (self.question or self.query)):
            raise ValueError("analyze_user_image requires image_path and question or query")
        if self.action == "answer_with_citations" and not (self.question or self.query):
            raise ValueError("answer_with_citations requires question or query")
        if self.action == "refuse" and not self.refusal_reason:
            raise ValueError("refuse requires refusal_reason")
        if self.action == "final_answer" and not (self.answer or self.refusal_reason):
            raise ValueError("final_answer requires answer or refusal_reason")
        return self

    def safe_input_summary(self) -> str:
        if self.input_summary:
            return truncate_text(self.input_summary)
        if self.query:
            return f"query={truncate_text(self.query)}"
        if self.question:
            return f"question={truncate_text(self.question)}"
        if self.image_path:
            return "image_path=<user_upload>"
        if self.refusal_reason:
            return f"refusal_reason={truncate_text(self.refusal_reason)}"
        return self.action


@dataclass(frozen=True)
class ReActObservation:
    action: ReActActionType
    observation_summary: str
    succeeded: bool
    tool_name: str | None = None
    query: str | None = None
    search_result_count: int = 0
    source_count: int = 0
    citation_count: int = 0
    refused: bool = False
    refusal_reason: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ReActStepRecord:
    name: str
    action: ReActActionType
    input_summary: str
    output_summary: str
    succeeded: bool
    iteration: int
    error: str | None = None


@dataclass(frozen=True)
class ReActRunResult:
    answer: str
    tool_calls: list[Any] = field(default_factory=list)
    workflow_steps: list[ReActStepRecord] = field(default_factory=list)
    observations: list[ReActObservation] = field(default_factory=list)
    iteration_count: int = 0
    refused: bool = False
    refusal_reason: str | None = None


def parse_react_action_json(
    payload: str | dict[str, Any],
    *,
    default_query: str | None = None,
) -> ReActAction:
    if isinstance(payload, str):
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("ReAct action must be valid JSON") from exc
    else:
        decoded = payload
    if not isinstance(decoded, dict):
        raise ValueError("ReAct action must be a JSON object")
    if "action" not in decoded and "next_action" in decoded:
        decoded["action"] = decoded.pop("next_action")
    if (
        decoded.get("action") == "refuse"
        and not decoded.get("refusal_reason")
        and decoded.get("reason")
    ):
        decoded["refusal_reason"] = decoded["reason"]
    if decoded.get("action") == "refuse" and not decoded.get("refusal_reason"):
        decoded["refusal_reason"] = "The agent could not produce a reliable answer from the available evidence."
    if (
        decoded.get("action") in {"search_knowledge", "search_figures", "rewrite_query"}
        and not decoded.get("query")
        and default_query
    ):
        decoded["query"] = default_query
    try:
        return ReActAction.model_validate(decoded)
    except ValidationError as exc:
        raise ValueError(f"Invalid ReAct action: {exc}") from exc


def normalize_react_query(query: str) -> str:
    return " ".join(query.casefold().strip().split())


def is_repeated_query(query: str, previous_queries: set[str]) -> bool:
    normalized = normalize_react_query(query)
    return normalized in previous_queries


def observation_from_tool_result(
    *,
    action: ReActAction,
    tool_result: AgentToolResult,
) -> ReActObservation:
    search_result_count = len(tool_result.search_results)
    source_count = len(tool_result.sources)
    citation_count = len(tool_result.citations)
    if tool_result.call.error:
        summary = truncate_text(tool_result.call.error)
    elif search_result_count:
        summary = f"returned {search_result_count} results"
    elif source_count or citation_count:
        summary = (
            f"refused={tool_result.refused}; "
            f"sources={source_count}; citations={citation_count}"
        )
    else:
        summary = tool_result.call.output_summary

    return ReActObservation(
        action=action.action,
        tool_name=tool_result.tool_name,
        query=action.query,
        observation_summary=summary,
        succeeded=tool_result.call.succeeded,
        search_result_count=search_result_count,
        source_count=source_count,
        citation_count=citation_count,
        refused=tool_result.refused,
        refusal_reason=tool_result.refusal_reason,
        error=tool_result.call.error,
    )


class DeterministicReActPlanner:
    def plan(
        self,
        *,
        question: str,
        observations: list[ReActObservation],
        previous_queries: set[str] | None = None,
        prior_source_count: int = 0,
        expand_followup: bool = False,
    ) -> ReActAction:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")

        previous_queries = previous_queries or set()
        if not observations and prior_source_count >= 3 and expand_followup:
            return ReActAction(
                action="answer_with_citations",
                question=normalized_question,
                reasoning_summary="Prior evidence from the conversation is sufficient for an expanded answer.",
            )

        if not observations and should_search_figures(question):
            return ReActAction(
                action="search_figures",
                query=normalized_question,
                reasoning_summary="The question asks for visual evidence; search figure evidence first.",
            )

        if not observations:
            return ReActAction(
                action="search_knowledge",
                query=normalized_question,
                reasoning_summary="Need to retrieve knowledge before answering.",
            )

        last = observations[-1]
        if last.error:
            return ReActAction(
                action="refuse",
                refusal_reason="Tool execution failed before reliable evidence was available.",
                reasoning_summary="Tool error requires safe refusal.",
            )

        if last.action == "search_knowledge" and last.search_result_count > 0:
            return ReActAction(
                action="answer_with_citations",
                question=normalized_question,
                reasoning_summary="Retrieved evidence is available; answer with citations.",
            )

        if last.action == "search_figures":
            return ReActAction(
                action="answer_with_citations",
                question=normalized_question,
                reasoning_summary="Figure evidence search is complete; answer with cited text evidence and available figures.",
            )

        if last.action == "search_knowledge" and last.search_result_count == 0:
            rewritten_query = f"{normalized_question} rock-filled concrete"
            if is_repeated_query(rewritten_query, previous_queries):
                return ReActAction(
                    action="refuse",
                    refusal_reason="Repeated search did not find reliable evidence.",
                    reasoning_summary="Repeated query guard requires safe refusal.",
                )
            return ReActAction(
                action="rewrite_query",
                query=rewritten_query,
                reasoning_summary="No evidence was found; rewrite the query once.",
            )

        if last.action == "rewrite_query" and last.query:
            return ReActAction(
                action="search_knowledge",
                query=last.query,
                reasoning_summary="Search again with the rewritten query.",
            )

        if last.action == "answer_with_citations" and not last.refused:
            return ReActAction(
                action="final_answer",
                answer="Final answer is available from answer_with_citations.",
                reasoning_summary="Answer tool completed successfully.",
            )

        return ReActAction(
            action="refuse",
            refusal_reason=last.refusal_reason or "Reliable evidence was not available.",
            reasoning_summary="The loop converged to refusal.",
        )


FIGURE_QUERY_TERMS = (
    "figure",
    "fig.",
    "image",
    "photo",
    "picture",
    "chart",
    "plot",
    "curve",
    "diagram",
    "flowchart",
    "microstructure",
    "show me",
    "visual",
    "图",
    "图片",
    "图表",
    "曲线",
    "流程图",
    "示意图",
    "照片",
    "形态",
    "破坏",
    "微观",
    "给我看",
    "展示",
)


def should_search_figures(question: str) -> bool:
    normalized = question.casefold()
    return any(term in normalized for term in FIGURE_QUERY_TERMS)
