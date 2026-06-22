from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.services.agent.graph_nodes import (
    analyze_image_node,
    final_answer_node,
    generate_answer_node,
    initialize_state,
    next_action_from_state,
    reset_current_event_sink,
    reset_current_planner_provider,
    refuse_node,
    reset_current_toolbox,
    rewrite_query_node,
    planner_node,
    search_figures_node,
    search_knowledge_node,
    search_tables_node,
    set_current_event_sink,
    set_current_planner_provider,
    set_current_toolbox,
    deserialize_search_items,
    deserialize_source_references,
    deserialize_steps,
    deserialize_tool_calls,
)
from app.services.agent.graph_checkpointer import create_graph_checkpointer
from app.services.agent.graph_state import LangGraphAgentRoute, LangGraphAgentState
from app.services.agent.react_service import (
    REACT_DEFAULT_MAX_ITERATIONS,
    REACT_HARD_MAX_ITERATIONS,
    ReActEventSink,
)
from app.services.agent.service import AgentQueryResult
from app.services.agent.tools import AgentToolCallRecord, AgentToolbox
from app.services.generation.chat_model import ChatModelProvider
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.embedding import EmbeddingProvider


def build_langgraph_agent_graph() -> StateGraph:
    graph = StateGraph(LangGraphAgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("search_knowledge", search_knowledge_node)
    graph.add_node("search_figures", search_figures_node)
    graph.add_node("search_tables", search_tables_node)
    graph.add_node("analyze_user_image", analyze_image_node)
    graph.add_node("rewrite_query", rewrite_query_node)
    graph.add_node("answer_with_citations", generate_answer_node)
    graph.add_node("refuse", refuse_node)
    graph.add_node("final_answer", final_answer_node)

    graph.set_entry_point("planner")
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "search_knowledge": "search_knowledge",
            "search_figures": "search_figures",
            "search_tables": "search_tables",
            "analyze_user_image": "analyze_user_image",
            "rewrite_query": "rewrite_query",
            "answer_with_citations": "answer_with_citations",
            "refuse": "refuse",
            "final_answer": "final_answer",
        },
    )
    graph.add_edge("search_knowledge", "planner")
    graph.add_edge("search_figures", "planner")
    graph.add_edge("search_tables", "planner")
    graph.add_edge("rewrite_query", "search_knowledge")
    graph.add_edge("answer_with_citations", END)
    graph.add_edge("analyze_user_image", END)
    graph.add_edge("refuse", END)
    graph.add_edge("final_answer", END)

    return graph


def route_after_planner(state: LangGraphAgentState) -> LangGraphAgentRoute:
    return next_action_from_state(state)


_COMPILED_LANGGRAPH_AGENT = None


def get_compiled_langgraph_agent():
    global _COMPILED_LANGGRAPH_AGENT
    if _COMPILED_LANGGRAPH_AGENT is None:
        _COMPILED_LANGGRAPH_AGENT = build_langgraph_agent_graph().compile()
    return _COMPILED_LANGGRAPH_AGENT


class LangGraphAgentService:
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        chat_model_provider: ChatModelProvider,
        planner_chat_provider: ChatModelProvider | None = None,
        log_answers: bool = True,
    ) -> None:
        self.planner_chat_provider = planner_chat_provider
        self.toolbox = AgentToolbox(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_model_provider,
            log_answers=log_answers,
        )

    def query(
        self,
        question: str,
        top_k: int = 5,
        max_tool_calls: int = REACT_DEFAULT_MAX_ITERATIONS,
        source_id: str | None = None,
        history: Sequence[str] | None = None,
        image_path: str | None = None,
        thread_id: str | None = None,
        event_sink: ReActEventSink | None = None,
    ) -> AgentQueryResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be greater than 0")

        latency_trace = LatencyTrace()
        latency_token = set_current_latency_trace(latency_trace)
        toolbox_token = set_current_toolbox(self.toolbox)
        event_sink_token = set_current_event_sink(event_sink)
        planner_token = set_current_planner_provider(self.planner_chat_provider)
        try:
            initial_state = initialize_state(
                question=normalized_question,
                top_k=top_k,
                max_iterations=min(max_tool_calls, REACT_HARD_MAX_ITERATIONS),
                source_id=source_id,
                history=list(history or []),
                image_path=image_path,
            )
            checkpointer_selection = create_graph_checkpointer()
            compiled_graph = build_langgraph_agent_graph().compile(
                checkpointer=checkpointer_selection.checkpointer,
            )
            graph_config = {
                "recursion_limit": 15,
                "configurable": {
                    "thread_id": thread_id or default_thread_id(normalized_question),
                },
            }
            initial_state.update(
                load_prior_evidence_from_checkpoint(
                    compiled_graph=compiled_graph,
                    config=graph_config,
                )
            )
            final_state = compiled_graph.invoke(
                initial_state,
                config=graph_config,
            )
            workflow_steps = deserialize_steps(final_state.get("workflow_steps", []))
            tool_calls = deserialize_tool_calls(final_state.get("tool_calls", []))
            search_results = deserialize_search_items(final_state.get("search_results", []))
            sources = deserialize_source_references(final_state.get("sources", []))
            latency = latency_trace.finalize(
                iteration_count=len(workflow_steps),
                tool_call_count=len(tool_calls),
            )
            latency["langgraph_checkpointer_backend"] = checkpointer_selection.backend
            latency["langgraph_checkpointer_reason"] = checkpointer_selection.reason
            return AgentQueryResult(
                question=normalized_question,
                answer=final_state.get("answer", ""),
                tool_calls=tool_calls,
                sources=sources,
                search_results=search_results,
                citations=final_state.get("citations", []),
                refused=final_state.get("refused", False),
                refusal_reason=final_state.get("refusal_reason"),
                reasoning_summary=(
                    f"langgraph_agent iterations={len(workflow_steps)}; "
                    f"tool_calls={len(tool_calls)}"
                ),
                mode="langgraph_agent",
                workflow_steps=[
                    AgentToolCallRecord(
                        tool_name=step.name,
                        input_summary=step.input_summary,
                        output_summary=step.output_summary,
                        succeeded=step.succeeded,
                        error=step.error,
                    )
                    for step in workflow_steps
                ],
                iteration_count=len(workflow_steps),
                latency_trace=latency,
                image_analysis=final_state.get("image_analysis"),
            )
        finally:
            reset_current_planner_provider(planner_token)
            reset_current_event_sink(event_sink_token)
            reset_current_toolbox(toolbox_token)
            reset_current_latency_trace(latency_token)


def default_thread_id(question: str) -> str:
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]
    return f"langgraph-agent:{digest}"


def load_prior_evidence_from_checkpoint(
    *,
    compiled_graph: Any,
    config: dict[str, Any],
) -> dict[str, Any]:
    try:
        snapshot = compiled_graph.get_state(config)
        values = getattr(snapshot, "values", None)
        if not isinstance(values, dict):
            return {}
        return compact_prior_evidence(values)
    except Exception:
        return {}


def compact_prior_evidence(state: dict[str, Any]) -> dict[str, Any]:
    sources = state.get("sources") or []
    if not isinstance(sources, list) or not sources:
        return {}
    prior_sources = compact_prior_sources(sources)
    if not prior_sources:
        return {}
    prior: dict[str, Any] = {"prior_sources": prior_sources}
    citations = state.get("citations") or []
    if isinstance(citations, list):
        prior["prior_citations"] = [
            int(value)
            for value in citations
            if isinstance(value, int) or (isinstance(value, str) and value.isdigit())
        ][:10]
    answer = str(state.get("answer") or "").strip()
    if answer:
        prior["prior_answer_summary"] = truncate_prior_answer(answer)
    return prior


def compact_prior_sources(sources: list[Any], *, limit: int = 5) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for index, source in enumerate(sources[:limit], start=1):
        if not isinstance(source, dict):
            continue
        content = str(source.get("content") or source.get("table_content") or "")[:300]
        source_id = str(source.get("source_id") or f"prior:{index}")
        compacted.append(
            {
                "source_id": source_id,
                "document_title": str(source.get("title") or source.get("document_title") or source_id),
                "heading_path": source.get("heading_path"),
                "content": content,
                "source_type": source.get("source_type") or "prior_conversation",
                "document_id": source.get("document_id"),
                "chunk_id": source.get("chunk_id"),
                "chunk_index": source.get("chunk_index"),
                "chunk_type": source.get("chunk_type") or "text",
                "caption": source.get("caption"),
                "page_number": source.get("page_number"),
                "table_content": str(source.get("table_content") or "")[:300] or None,
            }
        )
    return compacted


def truncate_prior_answer(answer: str, *, limit: int = 200) -> str:
    normalized = " ".join(answer.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip()
