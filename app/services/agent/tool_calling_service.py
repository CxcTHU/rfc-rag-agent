from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.services.agent.service import AgentQueryResult
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    AgentToolResult,
    AgentToolbox,
    truncate_text,
)
from app.core.structured_logging import log_event, safe_text_summary
from app.services.brain.workflow import (
    RESPONSIBILITY_REFUSAL_ANSWER,
    evaluate_responsibility_gate,
    extract_citations,
    has_topic_anchor,
)
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelProvider,
    ChatToolCall,
    ChatToolDefinition,
    ChatToolFunction,
)
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.embedding import EmbeddingProvider


TOOL_CALLING_DEFAULT_MAX_ITERATIONS = 3
TOOL_CALLING_HARD_MAX_ITERATIONS = 3
ALLOWED_TOOL_NAMES = frozenset({"search_knowledge", "hybrid_search_knowledge"})
TOOL_RESULT_SNIPPET_LIMIT = 180
TOOL_RESULT_MAX_SOURCES = 5
TOOL_CALLING_MAX_EXECUTED_TOOLS_PER_ITERATION = 1
TOOL_CALLING_NEAR_DUPLICATE_THRESHOLD = 0.65
TOOL_CALLING_PREFERRED_TOOL_ORDER = {
    "hybrid_search_knowledge": 0,
    "search_knowledge": 1,
}
ToolCallingFinalAnswerStrategy = Literal["baseline", "structured_final_answer"]
TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY: ToolCallingFinalAnswerStrategy = (
    "structured_final_answer"
)
agent_logger = logging.getLogger("rfc_rag_agent.agent")


@dataclass(frozen=True)
class ToolCallingRuntimeEvent:
    event: str
    payload: dict[str, object]


ToolCallingEventSink = Callable[[ToolCallingRuntimeEvent], None]


class ToolCallingAgentService:
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        chat_model_provider: ChatModelProvider,
        log_answers: bool = True,
        final_answer_strategy: ToolCallingFinalAnswerStrategy = (
            TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY
        ),
    ) -> None:
        if final_answer_strategy not in {"baseline", "structured_final_answer"}:
            raise ValueError("unsupported tool-calling final answer strategy")
        self.final_answer_strategy = final_answer_strategy
        self.chat_model_provider = chat_model_provider
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
        max_tool_calls: int = TOOL_CALLING_DEFAULT_MAX_ITERATIONS,
        history: Sequence[str] | None = None,
        event_sink: ToolCallingEventSink | None = None,
    ) -> AgentQueryResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be greater than 0")

        log_event(
            agent_logger,
            "query_received",
            mode="tool_calling_agent",
            top_k=top_k,
            max_tool_calls=max_tool_calls,
            final_answer_strategy=self.final_answer_strategy,
            question_summary=safe_text_summary(normalized_question, limit=80),
        )

        responsibility_gate = evaluate_responsibility_gate(normalized_question)
        if responsibility_gate.triggered:
            log_event(
                agent_logger,
                "refusal_triggered",
                mode="tool_calling_agent",
                refusal_category="responsibility_gate_triggered",
                source_count=0,
                citation_count=0,
                tool_call_count=0,
            )
            return AgentQueryResult(
                question=normalized_question,
                answer=RESPONSIBILITY_REFUSAL_ANSWER,
                tool_calls=[],
                refused=True,
                refusal_reason=responsibility_gate.refusal_reason,
                reasoning_summary="tool_calling_agent refused before tool loop via responsibility_gate.",
                mode="tool_calling_agent",
                workflow_steps=[
                    AgentToolCallRecord(
                        tool_name="responsibility_gate",
                        input_summary=truncate_text(normalized_question),
                        output_summary="refused=True responsibility_gate",
                        succeeded=True,
                    )
                ],
                iteration_count=1,
            )

        topic_gate_query = " ".join([normalized_question, *(history or [])])
        if not has_topic_anchor(topic_gate_query):
            log_event(
                agent_logger,
                "refusal_triggered",
                mode="tool_calling_agent",
                refusal_category="off_topic",
                source_count=0,
                citation_count=0,
                tool_call_count=0,
            )
            return AgentQueryResult(
                question=normalized_question,
                answer="当前问题缺少项目资料库的领域锚点，无法基于堆石混凝土资料可靠回答。",
                tool_calls=[],
                refused=True,
                refusal_reason="Question appears off-topic: no domain anchor was found.",
                reasoning_summary="tool_calling_agent refused before tool loop via off_topic_gate.",
                mode="tool_calling_agent",
                workflow_steps=[
                    AgentToolCallRecord(
                        tool_name="off_topic_gate",
                        input_summary=truncate_text(normalized_question),
                        output_summary="refused=True off_topic",
                        succeeded=True,
                    )
                ],
                iteration_count=1,
            )

        max_iterations = min(max_tool_calls, TOOL_CALLING_HARD_MAX_ITERATIONS)
        messages = tool_calling_messages(
            normalized_question,
            history=history,
            final_answer_strategy=self.final_answer_strategy,
        )
        tools = tool_calling_tool_definitions()
        tool_calls: list[AgentToolCallRecord] = []
        workflow_steps: list[AgentToolCallRecord] = []
        search_results: list[AgentSearchItem] = []
        sources: list[AgentSourceReference] = []
        previous_tool_queries: list[str] = []
        repeated_query_count = 0
        near_duplicate_query_count = 0
        skipped_tool_call_count = 0
        executed_tool_call_count = 0
        citation_repair_count = 0
        llm_call_count = 0
        latency_trace = LatencyTrace()
        latency_token = set_current_latency_trace(latency_trace)

        try:
            for iteration in range(1, max_iterations + 1):
                self._emit(
                    event_sink,
                    "agent_step",
                    {
                        "iteration": iteration,
                        "action": "llm_with_tools",
                        "step_summary": "calling model with tool definitions",
                    },
                )
                llm_started = time.perf_counter()
                if not hasattr(self.chat_model_provider, "generate_with_tools"):
                    raise RuntimeError(
                        "chat model provider does not support tool calling"
                    )
                model_result = self.chat_model_provider.generate_with_tools(messages, tools)
                llm_call_count += 1
                llm_duration_ms = (time.perf_counter() - llm_started) * 1000.0
                latency_trace.add_duration("planner_latency_ms", llm_duration_ms)

                if model_result.tool_calls:
                    messages.append(
                        ChatMessage(
                            role="assistant",
                            content="",
                            assistant_tool_calls=tuple(model_result.tool_calls),
                        )
                    )
                    iteration_executed_tool_count = 0
                    iteration_skipped_tool_count = 0
                    tool_calls_to_execute = executable_tool_call_ids(
                        model_result.tool_calls,
                        previous_tool_queries=previous_tool_queries,
                        sources_available=bool(sources),
                    )
                    for tool_call in model_result.tool_calls:
                        query = tool_query_from_call(tool_call, default_query=normalized_question)
                        normalized_tool_query = normalize_tool_query(query)
                        if is_near_duplicate_tool_query(
                            normalized_tool_query,
                            previous_tool_queries,
                        ):
                            repeated_query_count += 1
                            near_duplicate_query_count += 1
                            repeated_record = AgentToolCallRecord(
                                tool_name=tool_call.name,
                                input_summary=f"query={truncate_text(query)}",
                                output_summary="near-duplicate query skipped",
                                succeeded=False,
                                error="near-duplicate query skipped",
                            )
                            tool_calls.append(repeated_record)
                            workflow_steps.append(repeated_record)
                            skipped_tool_call_count += 1
                            iteration_skipped_tool_count += 1
                            messages.append(
                                tool_message_from_payload(
                                    tool_call,
                                    skipped_tool_result_payload(
                                        reason="near-duplicate query skipped",
                                        sources=sources,
                                    ),
                                )
                            )
                            self._emit_tool_result(
                                event_sink,
                                repeated_record,
                                iteration=iteration,
                            )
                            continue

                        if tool_call.id not in tool_calls_to_execute:
                            reason = skip_reason_for_tool_call(
                                sources_available=bool(sources),
                            )
                            skipped_record = AgentToolCallRecord(
                                tool_name=tool_call.name,
                                input_summary=f"query={truncate_text(query)}",
                                output_summary=reason,
                                succeeded=False,
                                error=reason,
                            )
                            tool_calls.append(skipped_record)
                            workflow_steps.append(skipped_record)
                            skipped_tool_call_count += 1
                            iteration_skipped_tool_count += 1
                            messages.append(
                                tool_message_from_payload(
                                    tool_call,
                                    skipped_tool_result_payload(
                                        reason=reason,
                                        sources=sources,
                                    ),
                                )
                            )
                            self._emit_tool_result(
                                event_sink,
                                skipped_record,
                                iteration=iteration,
                            )
                            continue

                        self._emit_tool_start(event_sink, tool_call, iteration)
                        tool_started = time.perf_counter()
                        tool_result = self._execute_tool_call(
                            tool_call=tool_call,
                            default_query=normalized_question,
                            top_k=top_k,
                        )
                        latency_trace.add_duration(
                            "tool_latency_ms",
                            (time.perf_counter() - tool_started) * 1000.0,
                        )
                        executed_tool_call_count += 1
                        iteration_executed_tool_count += 1
                        tool_calls.append(tool_result.call)
                        workflow_steps.append(tool_result.call)
                        search_results = merge_search_results(
                            search_results,
                            tool_result.search_results,
                        )
                        sources = merge_sources(sources, tool_result.sources)
                        messages.append(
                            tool_message_from_payload(
                                tool_call,
                                safe_tool_result_payload(tool_result, sources),
                            )
                        )
                        self._emit_tool_result(
                            event_sink,
                            tool_result.call,
                            iteration=iteration,
                        )
                        previous_tool_queries.append(normalized_tool_query)

                    if (
                        sources
                        and iteration_executed_tool_count == 0
                        and iteration_skipped_tool_count > 0
                    ):
                        llm_started = time.perf_counter()
                        evidence_result = self.chat_model_provider.generate(
                            evidence_answer_messages(
                                normalized_question,
                                sources=sources,
                                history=history,
                                final_answer_strategy=self.final_answer_strategy,
                            )
                        )
                        llm_call_count += 1
                        answer_duration_ms = (time.perf_counter() - llm_started) * 1000.0
                        latency_trace.add_duration(
                            "answer_latency_ms",
                            answer_duration_ms,
                        )
                        allowed_source_ids = list(range(1, len(sources) + 1))
                        citations = extract_citations(
                            evidence_result.answer,
                            allowed_source_ids,
                        )
                        answer_content = evidence_result.answer
                        if not citations:
                            repair_started = time.perf_counter()
                            repair_result = self.chat_model_provider.generate(
                                citation_repair_messages(
                                    normalized_question,
                                    draft_answer=evidence_result.answer,
                                    sources=sources,
                                    history=history,
                                    final_answer_strategy=self.final_answer_strategy,
                                )
                            )
                            citation_repair_count += 1
                            llm_call_count += 1
                            latency_trace.add_duration(
                                "answer_latency_ms",
                                (time.perf_counter() - repair_started) * 1000.0,
                            )
                            repair_citations = extract_citations(
                                repair_result.answer,
                                allowed_source_ids,
                            )
                            if repair_citations:
                                answer_content = repair_result.answer
                                citations = repair_citations
                        if citations:
                            workflow_steps.append(
                                AgentToolCallRecord(
                                    tool_name="final_answer",
                                    input_summary="evidence convergence",
                                    output_summary=truncate_text(answer_content),
                                    succeeded=True,
                                )
                            )
                            return result_from_tool_calling_loop(
                                question=normalized_question,
                                answer=answer_content,
                                tool_calls=tool_calls,
                                workflow_steps=workflow_steps,
                                search_results=search_results,
                                sources=sources,
                                citations=citations,
                                refused=False,
                                refusal_reason=None,
                                llm_call_count=llm_call_count,
                                repeated_query_count=repeated_query_count,
                                near_duplicate_query_count=near_duplicate_query_count,
                                skipped_tool_call_count=skipped_tool_call_count,
                                executed_tool_call_count=executed_tool_call_count,
                                citation_repair_count=citation_repair_count,
                                latency_trace=latency_trace.finalize(
                                    iteration_count=len(workflow_steps),
                                    tool_call_count=len(tool_calls),
                                ),
                            )
                    continue

                if model_result.content.strip():
                    latency_trace.add_duration("answer_latency_ms", llm_duration_ms)
                    allowed_source_ids = list(range(1, len(sources) + 1))
                    citations = extract_citations(
                        model_result.content,
                        allowed_source_ids,
                    )
                    answer_content = model_result.content
                    if sources and not citations:
                        repair_started = time.perf_counter()
                        repair_result = self.chat_model_provider.generate(
                            citation_repair_messages(
                                normalized_question,
                                draft_answer=model_result.content,
                                sources=sources,
                                history=history,
                                final_answer_strategy=self.final_answer_strategy,
                            )
                        )
                        citation_repair_count += 1
                        llm_call_count += 1
                        latency_trace.add_duration(
                            "answer_latency_ms",
                            (time.perf_counter() - repair_started) * 1000.0,
                        )
                        repair_citations = extract_citations(
                            repair_result.answer,
                            allowed_source_ids,
                        )
                        if repair_citations:
                            answer_content = repair_result.answer
                            citations = repair_citations
                    if not sources or not citations:
                        refusal_reason = (
                            "Tool-calling model returned final content without valid "
                            "tool-backed citations."
                        )
                        workflow_steps.append(
                            AgentToolCallRecord(
                                tool_name="final_answer",
                                input_summary="model content",
                                output_summary=refusal_reason,
                                succeeded=False,
                                error=refusal_reason,
                            )
                        )
                        return result_from_tool_calling_loop(
                            question=normalized_question,
                            answer=refusal_reason,
                            tool_calls=tool_calls,
                            workflow_steps=workflow_steps,
                            search_results=search_results,
                            sources=sources,
                            citations=[],
                            refused=True,
                            refusal_reason=refusal_reason,
                            llm_call_count=llm_call_count,
                            repeated_query_count=repeated_query_count,
                            near_duplicate_query_count=near_duplicate_query_count,
                            skipped_tool_call_count=skipped_tool_call_count,
                            executed_tool_call_count=executed_tool_call_count,
                            citation_repair_count=citation_repair_count,
                            latency_trace=latency_trace.finalize(
                                iteration_count=len(workflow_steps),
                                tool_call_count=len(tool_calls),
                            ),
                        )

                    workflow_steps.append(
                        AgentToolCallRecord(
                            tool_name="final_answer",
                            input_summary="model content",
                            output_summary=truncate_text(answer_content),
                            succeeded=True,
                        )
                    )
                    return result_from_tool_calling_loop(
                        question=normalized_question,
                        answer=answer_content,
                        tool_calls=tool_calls,
                        workflow_steps=workflow_steps,
                        search_results=search_results,
                        sources=sources,
                        citations=citations,
                        refused=False,
                        refusal_reason=None,
                        llm_call_count=llm_call_count,
                        repeated_query_count=repeated_query_count,
                        near_duplicate_query_count=near_duplicate_query_count,
                        skipped_tool_call_count=skipped_tool_call_count,
                        executed_tool_call_count=executed_tool_call_count,
                        citation_repair_count=citation_repair_count,
                        latency_trace=latency_trace.finalize(
                            iteration_count=len(workflow_steps),
                            tool_call_count=len(tool_calls),
                        ),
                    )

            refusal_reason = "Tool-calling iteration limit reached."
            return result_from_tool_calling_loop(
                question=normalized_question,
                answer=refusal_reason,
                tool_calls=tool_calls,
                workflow_steps=workflow_steps,
                search_results=search_results,
                sources=sources,
                citations=[],
                refused=True,
                refusal_reason=refusal_reason,
                llm_call_count=llm_call_count,
                repeated_query_count=repeated_query_count,
                near_duplicate_query_count=near_duplicate_query_count,
                skipped_tool_call_count=skipped_tool_call_count,
                executed_tool_call_count=executed_tool_call_count,
                citation_repair_count=citation_repair_count,
                latency_trace=latency_trace.finalize(
                    iteration_count=len(workflow_steps),
                    tool_call_count=len(tool_calls),
                ),
            )
        finally:
            reset_current_latency_trace(latency_token)

    def _execute_tool_call(
        self,
        *,
        tool_call: ChatToolCall,
        default_query: str,
        top_k: int,
    ) -> AgentToolResult:
        if tool_call.name not in ALLOWED_TOOL_NAMES:
            return failed_tool_call_result(
                tool_call.name,
                "unsupported tool",
                f"Tool {tool_call.name} is not allowed.",
            )

        query = tool_query_from_call(tool_call, default_query=default_query)
        requested_top_k = tool_top_k_from_call(tool_call, default_top_k=top_k)
        if tool_call.name == "search_knowledge":
            return self.toolbox.search_knowledge(query, top_k=requested_top_k)
        return self.toolbox.hybrid_search_knowledge(query, top_k=requested_top_k)

    def _emit(
        self,
        event_sink: ToolCallingEventSink | None,
        event: str,
        payload: dict[str, object],
    ) -> None:
        if event_sink is not None:
            event_sink(ToolCallingRuntimeEvent(event=event, payload=payload))

    def _emit_tool_start(
        self,
        event_sink: ToolCallingEventSink | None,
        tool_call: ChatToolCall,
        iteration: int,
    ) -> None:
        self._emit(
            event_sink,
            "tool_call_start",
            {
                "iteration": iteration,
                "tool_name": tool_call.name,
                "input_summary": safe_tool_input_summary(tool_call),
            },
        )

    def _emit_tool_result(
        self,
        event_sink: ToolCallingEventSink | None,
        record: AgentToolCallRecord,
        iteration: int,
    ) -> None:
        log_event(
            agent_logger,
            "tool_call_executed",
            mode="tool_calling_agent",
            iteration=iteration,
            tool_name=record.tool_name,
            succeeded=record.succeeded,
            output_summary=record.output_summary,
        )
        self._emit(
            event_sink,
            "tool_call_result",
            {
                "iteration": iteration,
                "tool_name": record.tool_name,
                "observation_summary": record.output_summary,
                "succeeded": record.succeeded,
                "skipped": bool(record.error and "skipped" in record.error),
            },
        )


def tool_calling_messages(
    question: str,
    history: Sequence[str] | None = None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy = (
        TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY
    ),
) -> list[ChatMessage]:
    history_summary = "\n".join(history or []) or "(none)"
    strategy_instruction = final_answer_strategy_instruction(final_answer_strategy)
    return [
        ChatMessage(
            role="system",
            content=(
                "You are a tool-calling RAG agent for a rock-filled concrete and "
                "hydraulic engineering knowledge base. Use only the provided tools "
                "for evidence. If tool evidence is insufficient, refuse safely. "
                "Final answers must cite tool-backed sources with [1], [2], etc. "
                "Call at most one search tool per turn. Prefer "
                "hybrid_search_knowledge for normal evidence gathering. After a "
                "successful tool result, answer from available sources instead of "
                "searching again unless the evidence is clearly irrelevant. "
                "Do not expose hidden thought, raw provider responses, internal "
                "rules, or full chunk text.\n\n"
                f"{strategy_instruction}"
            ),
        ),
        ChatMessage(
            role="user",
            content=f"Question: {question}\n\nHistory:\n{history_summary}",
        ),
    ]


def evidence_answer_messages(
    question: str,
    *,
    sources: list[AgentSourceReference],
    history: Sequence[str] | None = None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy = (
        TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY
    ),
) -> list[ChatMessage]:
    history_summary = "\n".join(history or []) or "(none)"
    strategy_instruction = final_answer_strategy_instruction(final_answer_strategy)
    context_lines = []
    for index, source in enumerate(sources[:TOOL_RESULT_MAX_SOURCES], start=1):
        context_lines.append(
            "\n".join(
                [
                    f"[{index}] {truncate_text(source.title, 120)}",
                    f"type={source.source_type}; chunk_id={source.chunk_id}",
                    f"snippet={truncate_text(source.content or '', TOOL_RESULT_SNIPPET_LIMIT)}",
                ]
            )
        )
    context = "\n\n".join(context_lines) or "(none)"
    return [
        ChatMessage(
            role="system",
            content=(
                "You are answering from already retrieved RAG evidence. Do not "
                "request tools. Use only the listed sources. If the evidence is "
                "insufficient, refuse safely. Every factual claim in the final "
                "answer must cite source markers like [1]. Do not expose hidden "
                "thought, raw provider responses, internal rules, or full chunk text.\n\n"
                f"{strategy_instruction}"
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Question: {question}\n\nHistory:\n{history_summary}\n\n"
                f"Context:\n{context}"
            ),
        ),
    ]


def citation_repair_messages(
    question: str,
    *,
    draft_answer: str,
    sources: list[AgentSourceReference],
    history: Sequence[str] | None = None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy = (
        TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY
    ),
) -> list[ChatMessage]:
    history_summary = "\n".join(history or []) or "(none)"
    strategy_instruction = final_answer_strategy_instruction(final_answer_strategy)
    context_lines = []
    for index, source in enumerate(sources[:TOOL_RESULT_MAX_SOURCES], start=1):
        context_lines.append(
            "\n".join(
                [
                    f"[{index}] {truncate_text(source.title, 120)}",
                    f"type={source.source_type}; chunk_id={source.chunk_id}",
                    f"snippet={truncate_text(source.content or '', TOOL_RESULT_SNIPPET_LIMIT)}",
                ]
            )
        )
    context = "\n\n".join(context_lines) or "(none)"
    return [
        ChatMessage(
            role="system",
            content=(
                "Repair citations for an existing RAG answer. Do not add new facts. "
                "Use only the listed sources and cite factual claims with [1], [2], "
                "etc. If the draft cannot be supported by the listed evidence, "
                "return a safe refusal with the closest supporting citation. "
                "Preserve the draft's factual scope; this is citation repair, not "
                "answer expansion.\n\n"
                f"{strategy_instruction}"
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Question: {question}\n\nHistory:\n{history_summary}\n\n"
                f"Draft answer:\n{draft_answer}\n\nContext:\n{context}"
            ),
        ),
    ]


def final_answer_strategy_instruction(
    final_answer_strategy: ToolCallingFinalAnswerStrategy,
) -> str:
    if final_answer_strategy == "baseline":
        return (
            "Final answer strategy: baseline. Give a concise source-backed answer "
            "using valid [N] citations from tool results."
        )
    if final_answer_strategy == "structured_final_answer":
        return (
            "Final answer strategy: structured_final_answer. Use a citation-first "
            "compact structure. Start with a direct answer in one or two cited "
            "sentences. Then add short factual bullets for every requested aspect "
            "that is supported by the retrieved evidence; use 4 to 6 bullets when "
            "the question asks for comparison, multiple dimensions, monitoring, "
            "quality control, or imported-corpus literature coverage. "
            "Each factual sentence and each factual bullet must include the closest "
            "[N] citation from retrieved sources. Keep each bullet to one supported "
            "idea; do not combine unsupported mechanisms, numeric values, advantages, "
            "limitations, or comparisons in the same uncited sentence. Do not omit "
            "a supported point only because another point has stronger evidence; "
            "include the weaker supported point with its nearest citation or mark it "
            "as an evidence gap if no source supports it. For comparison questions, "
            "cite each side separately and state the difference explicitly. If "
            "retrieved evidence supports "
            "only part of the question, answer the supported part with citations and "
            "add a brief 'evidence gap' sentence for unsupported parts instead of "
            "guessing. Do not cite a source that does not support the sentence; refuse "
            "safely only when the available sources cannot support any reliable domain "
            "answer. Do not reveal internal outline or hidden reasoning."
        )
    raise ValueError("unsupported tool-calling final answer strategy")


def tool_calling_tool_definitions() -> list[ChatToolDefinition]:
    query_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for the local RFC knowledge base.",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of results to return.",
                "minimum": 1,
                "maximum": 8,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    return [
        ChatToolDefinition(
            function=ChatToolFunction(
                name="hybrid_search_knowledge",
                description=(
                    "Read-only hybrid keyword/vector search over the local "
                    "rock-filled concrete knowledge base."
                ),
                parameters=query_schema,
            )
        ),
        ChatToolDefinition(
            function=ChatToolFunction(
                name="search_knowledge",
                description=(
                    "Read-only keyword search over the local rock-filled concrete "
                    "knowledge base."
                ),
                parameters=query_schema,
            )
        ),
    ]


def safe_tool_result_payload(
    tool_result: AgentToolResult,
    merged_sources: list[AgentSourceReference],
) -> dict[str, object]:
    source_index_by_id = {
        source.source_id: index for index, source in enumerate(merged_sources, start=1)
    }
    safe_sources: list[dict[str, object]] = []
    for source in tool_result.sources[:TOOL_RESULT_MAX_SOURCES]:
        citation_id = source_index_by_id.get(source.source_id)
        safe_sources.append(
            {
                "citation_id": citation_id,
                "source_id": source.source_id,
                "title": truncate_text(source.title, 120),
                "source_type": source.source_type,
                "chunk_id": source.chunk_id,
                "chunk_index": source.chunk_index,
                "chunk_type": source.chunk_type,
                "image_url": source.image_url,
                "score": round(float(source.score), 4) if source.score is not None else None,
                "snippet": truncate_text(source.content or "", TOOL_RESULT_SNIPPET_LIMIT),
            }
        )
    return {
        "tool_name": tool_result.tool_name,
        "succeeded": tool_result.call.succeeded,
        "refused": tool_result.refused,
        "error": tool_result.call.error,
        "summary": tool_result.call.output_summary,
        "sources": safe_sources,
    }


def skipped_tool_result_payload(
    *,
    reason: str,
    sources: list[AgentSourceReference],
) -> dict[str, object]:
    return {
        "succeeded": False,
        "refused": True,
        "error": reason,
        "instruction": (
            "Do not repeat equivalent search calls. If the listed sources are "
            "sufficient, produce the final answer with citations; otherwise refuse "
            "safely based on insufficient evidence."
        ),
        "sources": safe_sources_payload(sources),
    }


def safe_sources_payload(
    sources: list[AgentSourceReference],
) -> list[dict[str, object]]:
    safe_sources: list[dict[str, object]] = []
    for index, source in enumerate(sources[:TOOL_RESULT_MAX_SOURCES], start=1):
        safe_sources.append(
            {
                "citation_id": index,
                "source_id": source.source_id,
                "title": truncate_text(source.title, 120),
                "source_type": source.source_type,
                "chunk_id": source.chunk_id,
                "chunk_index": source.chunk_index,
                "chunk_type": source.chunk_type,
                "image_url": source.image_url,
                "score": round(float(source.score), 4) if source.score is not None else None,
                "snippet": truncate_text(source.content or "", TOOL_RESULT_SNIPPET_LIMIT),
            }
        )
    return safe_sources


def tool_message_from_payload(
    tool_call: ChatToolCall,
    payload: dict[str, object],
) -> ChatMessage:
    return ChatMessage(
        role="tool",
        content=json.dumps(payload, ensure_ascii=False),
        tool_call_id=tool_call.id,
    )


def tool_query_from_call(tool_call: ChatToolCall, default_query: str) -> str:
    query = tool_call.arguments.get("query")
    if isinstance(query, str) and query.strip():
        return query.strip()
    return default_query


def tool_top_k_from_call(tool_call: ChatToolCall, default_top_k: int) -> int:
    raw_top_k = tool_call.arguments.get("top_k")
    if isinstance(raw_top_k, int):
        return max(1, min(raw_top_k, 8))
    if isinstance(raw_top_k, str) and raw_top_k.isdigit():
        return max(1, min(int(raw_top_k), 8))
    return max(1, min(default_top_k, 8))


def safe_tool_input_summary(tool_call: ChatToolCall) -> str:
    query = tool_call.arguments.get("query", "")
    top_k = tool_call.arguments.get("top_k", "")
    return f"query={truncate_text(str(query))}; top_k={top_k}"


def normalize_tool_query(query: str) -> str:
    return " ".join(tokenize_tool_query(query))


def tokenize_tool_query(query: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", query.casefold())
    normalized_tokens: list[str] = []
    for token in tokens:
        if token in {"rfc", "rockfilled"}:
            normalized_tokens.extend(["rock", "filled", "concrete"])
        elif token == "scc":
            normalized_tokens.extend(["self", "compacting", "concrete"])
        else:
            normalized_tokens.append(token)
    return normalized_tokens


def is_near_duplicate_tool_query(
    normalized_query: str,
    previous_queries: Sequence[str],
) -> bool:
    current_tokens = set(normalized_query.split())
    if not current_tokens:
        return False
    for previous_query in previous_queries:
        previous_tokens = set(previous_query.split())
        if not previous_tokens:
            continue
        overlap = len(current_tokens & previous_tokens)
        union = len(current_tokens | previous_tokens)
        if union and overlap / union >= TOOL_CALLING_NEAR_DUPLICATE_THRESHOLD:
            return True
    return False


def executable_tool_call_ids(
    tool_calls: Sequence[ChatToolCall],
    *,
    previous_tool_queries: Sequence[str],
    sources_available: bool,
) -> set[str]:
    if sources_available:
        return set()

    candidates: list[ChatToolCall] = []
    for tool_call in tool_calls:
        if tool_call.name not in ALLOWED_TOOL_NAMES:
            candidates.append(tool_call)
            continue
        query = normalize_tool_query(tool_query_from_call(tool_call, default_query=""))
        if is_near_duplicate_tool_query(query, previous_tool_queries):
            continue
        candidates.append(tool_call)

    candidates.sort(
        key=lambda call: TOOL_CALLING_PREFERRED_TOOL_ORDER.get(call.name, 99)
    )
    return {
        call.id
        for call in candidates[:TOOL_CALLING_MAX_EXECUTED_TOOLS_PER_ITERATION]
    }


def skip_reason_for_tool_call(*, sources_available: bool) -> str:
    if sources_available:
        return "existing evidence available; tool call skipped"
    return "per-iteration search tool budget reached"


def failed_tool_call_result(
    tool_name: str,
    input_summary: str,
    error: str,
) -> AgentToolResult:
    return AgentToolResult(
        tool_name=tool_name,
        call=AgentToolCallRecord(
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=error,
            succeeded=False,
            error=error,
        ),
        refused=True,
        refusal_reason=error,
    )


def result_from_tool_calling_loop(
    *,
    question: str,
    answer: str,
    tool_calls: list[AgentToolCallRecord],
    workflow_steps: list[AgentToolCallRecord],
    search_results: list[AgentSearchItem],
    sources: list[AgentSourceReference],
    citations: list[int],
    refused: bool,
    refusal_reason: str | None,
    llm_call_count: int,
    repeated_query_count: int,
    near_duplicate_query_count: int,
    skipped_tool_call_count: int,
    executed_tool_call_count: int,
    citation_repair_count: int,
    latency_trace: dict[str, object],
) -> AgentQueryResult:
    latency_trace = dict(latency_trace)
    latency_trace["llm_call_count"] = llm_call_count
    latency_trace["repeated_query_count"] = repeated_query_count
    latency_trace["near_duplicate_query_count"] = near_duplicate_query_count
    latency_trace["skipped_tool_call_count"] = skipped_tool_call_count
    latency_trace["executed_tool_call_count"] = executed_tool_call_count
    latency_trace["citation_repair_count"] = citation_repair_count
    log_event(
        agent_logger,
        "refusal_triggered" if refused else "answer_generated",
        mode="tool_calling_agent",
        refused=refused,
        source_count=len(sources),
        citation_count=len(citations),
        tool_call_count=len(tool_calls),
        executed_tool_call_count=executed_tool_call_count,
        skipped_tool_call_count=skipped_tool_call_count,
        citation_repair_count=citation_repair_count,
        latency_ms=latency_trace.get("total_latency_ms"),
    )
    return AgentQueryResult(
        question=question,
        answer=answer,
        tool_calls=tool_calls,
        sources=sources,
        search_results=search_results,
        citations=citations,
        refused=refused,
        refusal_reason=refusal_reason,
        reasoning_summary=(
            "tool_calling_agent "
            f"llm_calls={llm_call_count}; "
            f"tool_calls={len(tool_calls)}; "
            f"executed_tool_call_count={executed_tool_call_count}; "
            f"skipped_tool_call_count={skipped_tool_call_count}; "
            f"citation_repair_count={citation_repair_count}; "
            f"repeated_query_count={repeated_query_count}"
        ),
        mode="tool_calling_agent",
        workflow_steps=workflow_steps,
        iteration_count=len(workflow_steps),
        latency_trace=latency_trace,
    )


def merge_search_results(
    existing: list[AgentSearchItem],
    new_items: list[AgentSearchItem],
) -> list[AgentSearchItem]:
    seen = {item.chunk_id for item in existing}
    merged = list(existing)
    for item in new_items:
        if item.chunk_id in seen:
            continue
        seen.add(item.chunk_id)
        merged.append(item)
    return merged


def merge_sources(
    existing: list[AgentSourceReference],
    new_items: list[AgentSourceReference],
) -> list[AgentSourceReference]:
    seen = {item.source_id for item in existing}
    merged = list(existing)
    for item in new_items:
        if item.source_id in seen:
            continue
        seen.add(item.source_id)
        merged.append(item)
    return merged
