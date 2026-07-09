from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
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
from app.services.agent.react_actions import should_search_figures
from app.services.agent.runtime import AgentRuntime, AgentRuntimeState
from app.services.agent.evidence_identity import (
    build_evidence_query_identity,
    refine_evidence_query_identity_with_llm,
)
from app.core.config import get_settings
from app.services.agent.runtime_checkpoint import (
    AgentRuntimeRunRepository,
    decide_resume,
    load_runtime_state,
    runtime_resume_diagnostics,
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
    create_chat_model_provider,
)
from app.services.observability.latency_trace import (
    LatencyTrace,
    bind_user_question_cache_key,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.hybrid_search import (
    reset_current_hyde_vector_query,
    set_current_hyde_vector_query,
)


TOOL_CALLING_DEFAULT_MAX_ITERATIONS = 3
TOOL_CALLING_HARD_MAX_ITERATIONS = 3
ALLOWED_TOOL_NAMES = frozenset(
    {"search_knowledge", "hybrid_search_knowledge", "search_figures", "search_tables"}
)
TOOL_RESULT_SNIPPET_LIMIT = 900
TOOL_RESULT_MAX_SOURCES = 8
TOOL_CALLING_MAX_EXECUTED_TOOLS_PER_ITERATION = 1
TOOL_CALLING_NEAR_DUPLICATE_THRESHOLD = 0.65
TOOL_CALLING_PREFERRED_TOOL_ORDER = {
    "hybrid_search_knowledge": 0,
    "search_knowledge": 1,
    "search_figures": 2,
    "search_tables": 3,
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


def create_runtime_identity_provider() -> ChatModelProvider | None:
    settings = get_settings()
    provider_name = (
        settings.runtime_identity_model_provider
        or settings.planner_chat_model_provider
    )
    model_name = (
        settings.runtime_identity_model_name
        or settings.planner_chat_model_name
    )
    if not provider_name.strip() or not model_name.strip():
        return None
    try:
        return create_chat_model_provider(
            provider_name=provider_name,
            model_name=model_name,
            api_key=(
                settings.runtime_identity_model_api_key
                or settings.planner_chat_model_api_key
            ),
            base_url=(
                settings.runtime_identity_model_base_url
                or settings.planner_chat_model_base_url
            ),
            temperature=settings.runtime_identity_model_temperature,
            timeout_seconds=settings.runtime_identity_model_timeout_seconds,
            max_attempts=1,
        )
    except ValueError:
        return None


def generate_hyde_vector_query(
    *,
    canonical_task: str,
    provider: ChatModelProvider | None,
    latency_trace: LatencyTrace,
) -> str:
    task = " ".join((canonical_task or "").split())
    if not task:
        latency_trace.set_value("hyde_generated", False)
        latency_trace.set_value("hyde_used_for_vector", False)
        latency_trace.set_value("hyde_reason", "empty_task")
        return ""
    if provider is None:
        latency_trace.set_value("hyde_generated", False)
        latency_trace.set_value("hyde_used_for_vector", False)
        latency_trace.set_value("hyde_reason", "provider_unavailable")
        return ""
    if str(getattr(provider, "provider_name", "")).casefold() in {"", "deterministic", "fake", "local"}:
        latency_trace.set_value("hyde_generated", False)
        latency_trace.set_value("hyde_used_for_vector", False)
        latency_trace.set_value("hyde_reason", "provider_unavailable")
        return ""
    try:
        started = time.perf_counter()
        result = provider.generate(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "Generate a concise hypothetical evidence passage for retrieval only. "
                        "Do not include citations. Do not claim it is real evidence. "
                        "Use technical terms likely to appear in source documents. "
                        "Return plain text only, under 120 words."
                    ),
                ),
                ChatMessage(role="user", content=task),
            ]
        )
        hyde_duration_ms = (time.perf_counter() - started) * 1000.0
        latency_trace.add_duration("planner_latency_ms", hyde_duration_ms)
        latency_trace.add_duration("hyde_latency_ms", hyde_duration_ms)
    except Exception:
        latency_trace.set_value("hyde_generated", False)
        latency_trace.set_value("hyde_used_for_vector", False)
        latency_trace.set_value("hyde_reason", "provider_error")
        return ""
    passage = " ".join((result.answer or "").split())
    if not passage:
        latency_trace.set_value("hyde_generated", False)
        latency_trace.set_value("hyde_used_for_vector", False)
        latency_trace.set_value("hyde_reason", "empty")
        return ""
    latency_trace.set_value("hyde_generated", True)
    latency_trace.set_value("hyde_used_for_vector", True)
    latency_trace.set_value("hyde_reason", "generated")
    latency_trace.set_value("hyde_model", f"{result.provider}/{result.model_name}")
    return f"{task}\n\nHypothetical evidence for vector retrieval only:\n{passage[:1200]}"


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
        runtime_identity_provider: ChatModelProvider | None = None,
    ) -> None:
        if final_answer_strategy not in {"baseline", "structured_final_answer"}:
            raise ValueError("unsupported tool-calling final answer strategy")
        self.final_answer_strategy = final_answer_strategy
        self.chat_model_provider = chat_model_provider
        self.db = db
        if runtime_identity_provider is not None:
            self.runtime_identity_provider = runtime_identity_provider
        elif str(chat_model_provider.provider_name).casefold() in {"deterministic", "fake", "local"}:
            self.runtime_identity_provider = None
        else:
            self.runtime_identity_provider = create_runtime_identity_provider()
        self.toolbox = AgentToolbox(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_model_provider,
            log_answers=log_answers,
        )

    def query(
        self,
        question: str,
        top_k: int = 8,
        max_tool_calls: int = TOOL_CALLING_DEFAULT_MAX_ITERATIONS,
        history: Sequence[str] | None = None,
        event_sink: ToolCallingEventSink | None = None,
        conversation_id: int | None = None,
        resume_policy: str = "auto",
        resume_run_id: str | None = None,
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

        runtime = AgentRuntime()
        runtime_state = runtime.assemble(normalized_question, history=history)
        evidence_identity = build_evidence_query_identity(
            runtime_state.context.standalone_task or normalized_question,
            history=history,
        )
        evidence_identity = refine_evidence_query_identity_with_llm(
            runtime_state.context.standalone_task or normalized_question,
            base_identity=evidence_identity,
            provider=self.runtime_identity_provider,
            history=history,
        )
        if evidence_identity.safe_for_cache_reuse and evidence_identity.canonical_query:
            runtime_state.context = replace(
                runtime_state.context,
                standalone_task=evidence_identity.canonical_query,
                contextualized=True,
                contextualization_source=evidence_identity.source,
            )
        runtime_repository = AgentRuntimeRunRepository(self.db)
        resume_decision = decide_resume(
            repository=runtime_repository,
            conversation_id=conversation_id,
            question=normalized_question,
            history=tuple(history or ()),
            resume_policy=resume_policy,
            resume_run_id=resume_run_id,
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

        topic_gate_query = " ".join(
            [
                runtime_state.context.standalone_task or normalized_question,
                *runtime_state.context.history,
            ]
        )
        if not resume_decision.should_resume and not has_topic_anchor(topic_gate_query):
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
        needs_figure_evidence = should_search_figures(normalized_question)
        figure_search_executed = False
        repeated_query_count = 0
        near_duplicate_query_count = 0
        skipped_tool_call_count = 0
        executed_tool_call_count = 0
        citation_repair_count = 0
        llm_call_count = 0
        latency_trace = LatencyTrace()
        bind_user_question_cache_key(latency_trace, normalized_question)
        apply_evidence_identity_diagnostics(latency_trace, evidence_identity)
        latency_trace.set_value(
            "canonical_task",
            evidence_identity.canonical_query
            or runtime_state.context.standalone_task
            or normalized_question,
        )
        for key, value in runtime_resume_diagnostics(resume_decision).items():
            latency_trace.set_value(key, value)
        apply_runtime_diagnostics(latency_trace, runtime_state)
        latency_token = set_current_latency_trace(latency_trace)
        hyde_token = None

        try:
            if resume_decision.should_resume and resume_decision.run is not None:
                resumed = result_from_runtime_checkpoint(
                    question=normalized_question,
                    run_state=load_runtime_state(resume_decision.run),
                    chat_model_provider=self.chat_model_provider,
                    history=history,
                    final_answer_strategy=self.final_answer_strategy,
                    runtime_state=runtime_state,
                    latency_trace=latency_trace,
                )
                runtime_repository.persist_node(
                    resume_decision.run,
                    node="final_answer_completed",
                    state={
                        **load_runtime_state(resume_decision.run),
                        "resume_completed": True,
                    },
                    status="completed",
                )
                return resumed

            semantic_cached = None
            if evidence_identity.safe_for_cache_reuse:
                semantic_cache_tool_name = semantic_cache_tool_for_identity(evidence_identity)
                latency_trace.set_value("semantic_cache_tool_name", semantic_cache_tool_name)
                semantic_cached = self.toolbox.lookup_semantic_evidence_cache(
                    evidence_identity.canonical_query
                    or runtime_state.context.standalone_task
                    or normalized_question,
                    top_k=top_k,
                    tool_name=semantic_cache_tool_name,
                )
            if semantic_cached is not None and semantic_cached.search_results:
                latency_trace.set_value("semantic_cache_hit", True)
                latency_trace.set_value("semantic_cache_reason", "tool_result_cache_hit")
                latency_trace.set_value("hyde_generated", False)
                latency_trace.set_value("hyde_used_for_vector", False)
                latency_trace.set_value("hyde_reason", "semantic_cache_hit")
                workflow_steps.append(semantic_cached.call)
                tool_calls.append(semantic_cached.call)
                search_results = list(semantic_cached.search_results)
                sources = list(semantic_cached.sources)
                runtime_state.evidence.add(
                    tool_name=semantic_cached.tool_name,
                    query=evidence_identity.canonical_query
                    or runtime_state.context.standalone_task
                    or normalized_question,
                    result_count=len(semantic_cached.search_results),
                    succeeded=semantic_cached.call.succeeded,
                )
                runtime_state.stop_reason = "semantic_evidence_cache_hit"
                runtime_state.final_decision = "answer"
                apply_runtime_diagnostics(latency_trace, runtime_state)
                self._emit_tool_result(event_sink, semantic_cached.call, iteration=1)
                return result_from_cached_evidence(
                    question=normalized_question,
                    search_results=search_results,
                    sources=sources,
                    tool_calls=tool_calls,
                    workflow_steps=workflow_steps,
                    chat_model_provider=self.chat_model_provider,
                    history=history,
                    final_answer_strategy=self.final_answer_strategy,
                    runtime_state=runtime_state,
                    latency_trace=latency_trace,
                )
            latency_trace.set_value("semantic_cache_hit", False)
            latency_trace.set_value(
                "semantic_cache_reason",
                "miss" if evidence_identity.safe_for_cache_reuse else "identity_not_reusable",
            )
            hyde_query = generate_hyde_vector_query(
                canonical_task=evidence_identity.canonical_query
                or runtime_state.context.standalone_task
                or normalized_question,
                provider=self.runtime_identity_provider,
                latency_trace=latency_trace,
            )
            if hyde_query:
                hyde_token = set_current_hyde_vector_query(hyde_query)

            active_run = None
            if conversation_id is not None:
                active_run = runtime_repository.create_run(
                    conversation_id=conversation_id,
                    question=normalized_question,
                    canonical_task=evidence_identity.canonical_query
                    or runtime_state.context.standalone_task
                    or normalized_question,
                    state={
                        "runtime_context": runtime_state.diagnostics(),
                        "evidence_identity": evidence_identity.diagnostics(),
                    },
                )
                latency_trace.set_value("runtime_run_id", active_run.run_id)

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
                    grounded_tool_calls = [
                        runtime.ground_tool_call(
                            tool_call,
                            state=runtime_state,
                            default_query=normalized_question,
                        )[0]
                        for tool_call in model_result.tool_calls
                    ]
                    apply_runtime_diagnostics(latency_trace, runtime_state)
                    iteration_executed_tool_count = 0
                    iteration_skipped_tool_count = 0
                    tool_calls_to_execute = executable_tool_call_ids(
                        grounded_tool_calls,
                        previous_tool_queries=previous_tool_queries,
                        sources_available=bool(sources),
                    )
                    for tool_call in grounded_tool_calls:
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
                        runtime_state.evidence.add(
                            tool_name=tool_result.tool_name,
                            query=query,
                            result_count=len(tool_result.search_results),
                            succeeded=tool_result.call.succeeded,
                        )
                        apply_runtime_diagnostics(latency_trace, runtime_state)
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
                        runtime_repository.persist_node(
                            active_run,
                            node="tool_execution_completed",
                            state=runtime_checkpoint_state(
                                runtime_state=runtime_state,
                                workflow_steps=workflow_steps,
                                tool_calls=tool_calls,
                                sources=sources,
                                latency_trace=latency_trace.values,
                            ),
                        )
                        if is_reranking_failure(tool_result.call):
                            refusal_reason = tool_result.call.error or tool_result.call.output_summary
                            runtime_state.stop_reason = "reranking_failed"
                            runtime_state.final_decision = "refuse"
                            apply_runtime_diagnostics(latency_trace, runtime_state)
                            runtime_repository.persist_node(
                                active_run,
                                node="reranking_failed",
                                state=runtime_checkpoint_state(
                                    runtime_state=runtime_state,
                                    workflow_steps=workflow_steps,
                                    tool_calls=tool_calls,
                                    sources=sources,
                                    latency_trace=latency_trace.values,
                                ),
                                status="failed",
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
                                runtime_state=runtime_state,
                                latency_trace=latency_trace.finalize(
                                    iteration_count=len(workflow_steps),
                                    tool_call_count=len(tool_calls),
                                ),
                            )
                        if (
                            tool_result.tool_name == "search_figures"
                            and tool_result.refused
                            and needs_figure_evidence
                            and not sources
                        ):
                            refusal_reason = (
                                tool_result.refusal_reason
                                or "No relevant figure evidence was found for the current question."
                            )
                            runtime_state.stop_reason = "figure_evidence_not_found"
                            runtime_state.final_decision = "refuse"
                            apply_runtime_diagnostics(latency_trace, runtime_state)
                            runtime_repository.persist_node(
                                active_run,
                                node="figure_evidence_not_found",
                                state=runtime_checkpoint_state(
                                    runtime_state=runtime_state,
                                    workflow_steps=workflow_steps,
                                    tool_calls=tool_calls,
                                    sources=sources,
                                    latency_trace=latency_trace.values,
                                ),
                                status="failed",
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
                                runtime_state=runtime_state,
                                latency_trace=latency_trace.finalize(
                                    iteration_count=len(workflow_steps),
                                    tool_call_count=len(tool_calls),
                                ),
                            )
                        previous_tool_queries.append(normalized_tool_query)
                        if tool_result.tool_name == "search_figures":
                            figure_search_executed = True
                        elif (
                            needs_figure_evidence
                            and tool_result.call.succeeded
                            and tool_result.search_results
                            and not figure_search_executed
                            and not any(source.image_url for source in sources)
                        ):
                            figure_query = runtime_state.context.standalone_task or normalized_question
                            figure_result = self.toolbox.search_figures(
                                figure_query,
                                top_k=min(4, top_k),
                            )
                            figure_search_executed = True
                            executed_tool_call_count += 1
                            iteration_executed_tool_count += 1
                            tool_calls.append(figure_result.call)
                            workflow_steps.append(figure_result.call)
                            runtime_state.evidence.add(
                                tool_name=figure_result.tool_name,
                                query=figure_query,
                                result_count=len(figure_result.search_results),
                                succeeded=figure_result.call.succeeded,
                            )
                            apply_runtime_diagnostics(latency_trace, runtime_state)
                            search_results = merge_search_results(
                                search_results,
                                figure_result.search_results,
                            )
                            sources = merge_sources(sources, figure_result.sources)
                            self._emit_tool_result(
                                event_sink,
                                figure_result.call,
                                iteration=iteration,
                            )

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
                            latency_trace.add_duration(
                                "citation_repair_latency_ms",
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
                            runtime_state.stop_reason = "evidence_convergence"
                            runtime_state.final_decision = "answer"
                            apply_runtime_diagnostics(latency_trace, runtime_state)
                            runtime_repository.persist_node(
                                active_run,
                                node="final_answer_completed",
                                state=runtime_checkpoint_state(
                                    runtime_state=runtime_state,
                                    workflow_steps=workflow_steps,
                                    tool_calls=tool_calls,
                                    sources=sources,
                                    latency_trace=latency_trace.values,
                                ),
                                status="completed",
                            )
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
                                runtime_state=runtime_state,
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
                        latency_trace.add_duration(
                            "citation_repair_latency_ms",
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
                        runtime_state.stop_reason = "final_content_without_citations"
                        runtime_state.final_decision = "refuse"
                        apply_runtime_diagnostics(latency_trace, runtime_state)
                        runtime_repository.persist_node(
                            active_run,
                            node="final_answer_failed",
                            state=runtime_checkpoint_state(
                                runtime_state=runtime_state,
                                workflow_steps=workflow_steps,
                                tool_calls=tool_calls,
                                sources=sources,
                                latency_trace=latency_trace.values,
                            ),
                            status="failed",
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
                            runtime_state=runtime_state,
                            latency_trace=latency_trace.finalize(
                                iteration_count=len(workflow_steps),
                                tool_call_count=len(tool_calls),
                            ),
                        )

                    runtime_state.stop_reason = "model_final_answer"
                    runtime_state.final_decision = "answer"
                    apply_runtime_diagnostics(latency_trace, runtime_state)
                    runtime_repository.persist_node(
                        active_run,
                        node="final_answer_completed",
                        state=runtime_checkpoint_state(
                            runtime_state=runtime_state,
                            workflow_steps=workflow_steps,
                            tool_calls=tool_calls,
                            sources=sources,
                            latency_trace=latency_trace.values,
                        ),
                        status="completed",
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
                        runtime_state=runtime_state,
                        latency_trace=latency_trace.finalize(
                            iteration_count=len(workflow_steps),
                            tool_call_count=len(tool_calls),
                        ),
                    )

            refusal_reason = "Tool-calling iteration limit reached."
            runtime_state.stop_reason = "iteration_limit"
            runtime_state.final_decision = "refuse"
            apply_runtime_diagnostics(latency_trace, runtime_state)
            runtime_repository.persist_node(
                active_run,
                node="iteration_limit",
                state=runtime_checkpoint_state(
                    runtime_state=runtime_state,
                    workflow_steps=workflow_steps,
                    tool_calls=tool_calls,
                    sources=sources,
                    latency_trace=latency_trace.values,
                ),
                status="failed",
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
                runtime_state=runtime_state,
                latency_trace=latency_trace.finalize(
                    iteration_count=len(workflow_steps),
                    tool_call_count=len(tool_calls),
                ),
            )
        finally:
            if hyde_token is not None:
                reset_current_hyde_vector_query(hyde_token)
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
        if tool_call.name == "search_figures":
            return self.toolbox.search_figures(query, top_k=requested_top_k)
        if tool_call.name == "search_tables":
            return self.toolbox.search_tables(query, top_k=requested_top_k)
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
                "When the user asks to see figures, photos, diagrams, curves, "
                "charts, microscopy, morphology, or other visual evidence, call "
                "search_figures before the final answer so image evidence can be "
                "shown only when it is relevant. When the user asks for table rows, "
                "tabulated data, mix-ratio tables, parameter tables, or table-based "
                "comparisons, call search_tables. "
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
            "balanced source-backed structure. Start with a direct answer in one or two cited "
            "sentences. Then add short factual bullets for every requested aspect "
            "that is supported by the retrieved evidence; use 4 to 6 bullets when "
            "the question asks for comparison, multiple dimensions, monitoring, "
            "quality control, advantages, causes, classifications, measures, "
            "or imported-corpus literature coverage. For ordinary domain list or "
            "explanation questions, do not stop at bare labels; give each bullet "
            "one explanatory clause or sentence grounded in the cited source. "
            "Only use title-only bullets when the user explicitly asks for an "
            "outline, very brief answer, keywords, or short labels. "
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
            "guessing. In evidence-gap or refusal sentences, name the concrete "
            "retrieved source title together with its marker, such as 'Title [1]', "
            "instead of referring only to generic 'source [1]', 'document [1]', "
            "'literature [1]', or 'snippet [1]'. Do not cite a source that does not support the sentence; refuse "
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
        ChatToolDefinition(
            function=ChatToolFunction(
                name="search_figures",
                description=(
                    "Read-only figure search over image-description chunks. Use "
                    "only when the user asks for or would clearly benefit from "
                    "visual evidence such as figures, photos, diagrams, curves, "
                    "charts, microscopy, or failure morphology."
                ),
                parameters=query_schema,
            )
        ),
        ChatToolDefinition(
            function=ChatToolFunction(
                name="search_tables",
                description=(
                    "Read-only search over extracted table chunks. Use for tabulated "
                    "data, mix-ratio rows, parameter tables, and table-based comparisons."
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
                "caption": truncate_text(source.caption or "", 120) or None,
                "page_number": source.page_number,
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


def is_reranking_failure(call: AgentToolCallRecord) -> bool:
    if call.succeeded:
        return False
    text = " ".join(
        part
        for part in [call.error, call.output_summary]
        if isinstance(part, str) and part
    )
    return "重排序失效" in text or "reranking failed" in text.casefold()


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
                "caption": truncate_text(source.caption or "", 120) or None,
                "page_number": source.page_number,
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
    runtime_state: AgentRuntimeState | None = None,
    latency_trace: dict[str, object],
) -> AgentQueryResult:
    latency_trace = dict(latency_trace)
    if runtime_state is not None:
        latency_trace.update(runtime_state.diagnostics())
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


def apply_runtime_diagnostics(
    latency_trace: LatencyTrace,
    runtime_state: AgentRuntimeState,
) -> None:
    for key, value in runtime_state.diagnostics().items():
        latency_trace.set_value(key, value)


def apply_evidence_identity_diagnostics(
    latency_trace: LatencyTrace,
    evidence_identity: Any,
) -> None:
    diagnostics = evidence_identity.diagnostics()
    for key, value in diagnostics.items():
        latency_trace.set_value(key, value)


def semantic_cache_tool_for_identity(evidence_identity: Any) -> str:
    intent_key = str(getattr(evidence_identity, "intent_key", "") or "")
    if intent_key == "visual_evidence":
        return "search_figures"
    if intent_key == "table_evidence":
        return "search_tables"
    return "hybrid_search_knowledge"


def runtime_checkpoint_state(
    *,
    runtime_state: AgentRuntimeState,
    workflow_steps: list[AgentToolCallRecord],
    tool_calls: list[AgentToolCallRecord],
    sources: list[AgentSourceReference],
    latency_trace: dict[str, object],
) -> dict[str, object]:
    return {
        "runtime_context": runtime_state.diagnostics(),
        "workflow_steps": [tool_call_record_to_dict(item) for item in workflow_steps[:20]],
        "tool_calls": [tool_call_record_to_dict(item) for item in tool_calls[:20]],
        "sources": [source_reference_to_dict(item) for item in sources[:12]],
        "source_chunk_ids": [
            int(source.chunk_id)
            for source in sources[:50]
            if isinstance(source.chunk_id, int)
        ],
        "latency_trace": {
            key: value
            for key, value in latency_trace.items()
            if key
            in {
                "evidence_canonical_query",
                "evidence_entity_key",
                "evidence_intent_key",
                "evidence_cache_reuse_allowed",
                "retrieval_cache_hit",
                "rerank_cache_hit",
                "tool_result_cache_hit",
                "runtime_run_id",
            }
        },
    }


def tool_call_record_to_dict(record: AgentToolCallRecord) -> dict[str, object]:
    return {
        "tool_name": record.tool_name,
        "input_summary": truncate_text(record.input_summary, 160),
        "output_summary": truncate_text(record.output_summary, 180),
        "succeeded": record.succeeded,
        "error": truncate_text(record.error or "", 180) or None,
    }


def source_reference_to_dict(source: AgentSourceReference) -> dict[str, object]:
    return {
        "source_id": source.source_id,
        "title": truncate_text(source.title, 160),
        "source_type": source.source_type,
        "status": source.status,
        "trust_level": source.trust_level,
        "fulltext_permission": source.fulltext_permission,
        "document_id": source.document_id,
        "chunk_id": source.chunk_id,
        "chunk_index": source.chunk_index,
        "url": source.url,
        "doi": source.doi,
        "content": truncate_text(source.content or "", TOOL_RESULT_SNIPPET_LIMIT),
        "score": source.score,
        "chunk_type": source.chunk_type,
        "source_image_path": source.source_image_path,
        "image_url": source.image_url,
        "caption": truncate_text(source.caption or "", 120) or None,
        "page_number": source.page_number,
        "table_content": truncate_text(source.table_content or "", 200) or None,
    }


def source_reference_from_dict(values: dict[str, object]) -> AgentSourceReference:
    return AgentSourceReference(
        source_id=str(values.get("source_id") or ""),
        title=str(values.get("title") or ""),
        source_type=str(values.get("source_type") or "unknown"),
        status=optional_str(values.get("status")),
        trust_level=optional_str(values.get("trust_level")),
        fulltext_permission=optional_str(values.get("fulltext_permission")),
        document_id=optional_int(values.get("document_id")),
        chunk_id=optional_int(values.get("chunk_id")),
        chunk_index=optional_int(values.get("chunk_index")),
        url=optional_str(values.get("url")),
        doi=optional_str(values.get("doi")),
        content=optional_str(values.get("content")),
        score=optional_float(values.get("score")),
        chunk_type=str(values.get("chunk_type") or "text"),
        source_image_path=optional_str(values.get("source_image_path")),
        image_url=optional_str(values.get("image_url")),
        caption=optional_str(values.get("caption")),
        page_number=optional_int(values.get("page_number")),
        table_content=optional_str(values.get("table_content")),
    )


def result_from_cached_evidence(
    *,
    question: str,
    search_results: list[AgentSearchItem],
    sources: list[AgentSourceReference],
    tool_calls: list[AgentToolCallRecord],
    workflow_steps: list[AgentToolCallRecord],
    chat_model_provider: ChatModelProvider,
    history: Sequence[str] | None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy,
    runtime_state: AgentRuntimeState,
    latency_trace: LatencyTrace,
) -> AgentQueryResult:
    llm_started = time.perf_counter()
    evidence_result = chat_model_provider.generate(
        evidence_answer_messages(
            question,
            sources=sources,
            history=history,
            final_answer_strategy=final_answer_strategy,
        )
    )
    latency_trace.add_duration("answer_latency_ms", (time.perf_counter() - llm_started) * 1000.0)
    allowed_source_ids = list(range(1, len(sources) + 1))
    citations = extract_citations(evidence_result.answer, allowed_source_ids)
    answer_content = evidence_result.answer
    llm_call_count = 1
    citation_repair_count = 0
    if not citations:
        repair_started = time.perf_counter()
        repair_result = chat_model_provider.generate(
            citation_repair_messages(
                question,
                draft_answer=evidence_result.answer,
                sources=sources,
                history=history,
                final_answer_strategy=final_answer_strategy,
            )
        )
        citation_repair_count = 1
        llm_call_count += 1
        latency_trace.add_duration("answer_latency_ms", (time.perf_counter() - repair_started) * 1000.0)
        latency_trace.add_duration("citation_repair_latency_ms", (time.perf_counter() - repair_started) * 1000.0)
        repair_citations = extract_citations(repair_result.answer, allowed_source_ids)
        if repair_citations:
            answer_content = repair_result.answer
            citations = repair_citations
    if citations:
        runtime_state.final_decision = "answer"
        runtime_state.stop_reason = "semantic_evidence_cache_hit"
        refused = False
        refusal_reason = None
    else:
        runtime_state.final_decision = "refuse"
        runtime_state.stop_reason = "cached_evidence_without_citations"
        refused = True
        refusal_reason = "Cached evidence answer did not include valid citations."
    apply_runtime_diagnostics(latency_trace, runtime_state)
    return result_from_tool_calling_loop(
        question=question,
        answer=answer_content,
        tool_calls=tool_calls,
        workflow_steps=workflow_steps,
        search_results=search_results,
        sources=sources,
        citations=citations,
        refused=refused,
        refusal_reason=refusal_reason,
        llm_call_count=llm_call_count,
        repeated_query_count=0,
        near_duplicate_query_count=0,
        skipped_tool_call_count=0,
        executed_tool_call_count=0,
        citation_repair_count=citation_repair_count,
        runtime_state=runtime_state,
        latency_trace=latency_trace.finalize(
            iteration_count=len(workflow_steps),
            tool_call_count=len(tool_calls),
        ),
    )


def result_from_runtime_checkpoint(
    *,
    question: str,
    run_state: dict[str, object],
    chat_model_provider: ChatModelProvider,
    history: Sequence[str] | None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy,
    runtime_state: AgentRuntimeState,
    latency_trace: LatencyTrace,
) -> AgentQueryResult:
    raw_sources = run_state.get("sources", [])
    if not isinstance(raw_sources, list):
        raw_sources = []
    sources = [
        source_reference_from_dict(item)
        for item in raw_sources
        if isinstance(item, dict)
    ]
    raw_steps = run_state.get("workflow_steps", [])
    workflow_steps = [
        AgentToolCallRecord(
            tool_name=str(item.get("tool_name") or "checkpoint"),
            input_summary=str(item.get("input_summary") or ""),
            output_summary=str(item.get("output_summary") or ""),
            succeeded=bool(item.get("succeeded")),
            error=optional_str(item.get("error")),
        )
        for item in raw_steps
        if isinstance(item, dict)
    ]
    workflow_steps.append(
        AgentToolCallRecord(
            tool_name="runtime_resume",
            input_summary="checkpoint",
            output_summary="resumed from completed evidence node",
            succeeded=True,
        )
    )
    latency_trace.set_value("runtime_resumed", True)
    latency_trace.set_value("runtime_skipped_completed_nodes", ["tool_execution"])
    latency_trace.set_value("executed_tool_call_count", 0)
    if not sources:
        runtime_state.stop_reason = "resume_checkpoint_without_sources"
        runtime_state.final_decision = "refuse"
        apply_runtime_diagnostics(latency_trace, runtime_state)
        return result_from_tool_calling_loop(
            question=question,
            answer="Runtime checkpoint did not contain reusable source evidence.",
            tool_calls=[],
            workflow_steps=workflow_steps,
            search_results=[],
            sources=[],
            citations=[],
            refused=True,
            refusal_reason="Runtime checkpoint did not contain reusable source evidence.",
            llm_call_count=0,
            repeated_query_count=0,
            near_duplicate_query_count=0,
            skipped_tool_call_count=0,
            executed_tool_call_count=0,
            citation_repair_count=0,
            runtime_state=runtime_state,
            latency_trace=latency_trace.finalize(
                iteration_count=len(workflow_steps),
                tool_call_count=0,
            ),
        )

    llm_started = time.perf_counter()
    evidence_result = chat_model_provider.generate(
        evidence_answer_messages(
            question,
            sources=sources,
            history=history,
            final_answer_strategy=final_answer_strategy,
        )
    )
    latency_trace.add_duration("answer_latency_ms", (time.perf_counter() - llm_started) * 1000.0)
    allowed_source_ids = list(range(1, len(sources) + 1))
    citations = extract_citations(evidence_result.answer, allowed_source_ids)
    runtime_state.stop_reason = "runtime_resume_completed"
    runtime_state.final_decision = "answer" if citations else "refuse"
    apply_runtime_diagnostics(latency_trace, runtime_state)
    workflow_steps.append(
        AgentToolCallRecord(
            tool_name="final_answer",
            input_summary="runtime resume",
            output_summary=truncate_text(evidence_result.answer),
            succeeded=bool(citations),
            error=None if citations else "checkpoint answer missing citations",
        )
    )
    return result_from_tool_calling_loop(
        question=question,
        answer=evidence_result.answer if citations else "Runtime checkpoint evidence could not produce cited answer.",
        tool_calls=[],
        workflow_steps=workflow_steps,
        search_results=[],
        sources=sources,
        citations=citations,
        refused=not bool(citations),
        refusal_reason=None if citations else "Runtime checkpoint evidence could not produce cited answer.",
        llm_call_count=1,
        repeated_query_count=0,
        near_duplicate_query_count=0,
        skipped_tool_call_count=0,
        executed_tool_call_count=0,
        citation_repair_count=0,
        runtime_state=runtime_state,
        latency_trace=latency_trace.finalize(
            iteration_count=len(workflow_steps),
            tool_call_count=0,
        ),
    )


def optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def optional_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
