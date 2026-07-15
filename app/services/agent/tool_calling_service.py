from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any, Literal, cast

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
from app.services.agent.runtime_events import (
    RuntimeEventBus,
    RuntimeEventName,
    ToolCallingRuntimeEvent,
    publish_tool_call_result,
    project_tool_calling_event,
)
from app.services.agent.planning_policy import (
    PlanningPolicy,
    PlanningRequest,
    phase64_runtime_identity_provider,
)
from app.services.agent.run_coordinator import (
    RunCoordinator,
    build_final_answer_request,
)
from app.services.agent.evidence_state_machine import EvidenceStateMachine
from app.services.agent.final_answer_controller import FinalAnswerController
from app.services.agent.final_result_assembler import (
    build_final_generation_failure_result,
    build_pre_tool_refusal_result,
    build_tool_calling_result,
)
from app.services.agent.checkpoint_repository import (
    AgentRuntimeRunRepository,
    CheckpointRepository,
    CheckpointSnapshot,
    decide_resume,
    is_explicit_continue,
    load_runtime_state,
    runtime_resume_diagnostics,
)
from app.services.agent.runtime_contracts import (
    CoordinatorRequest,
    FinalAnswerRequest,
    FinalAnswerOutcome,
    PreToolGateDecision,
    RunBudget,
    RuntimeStopReason,
    ToolExecutionRequest,
)
from app.services.agent.tool_executor import ALLOWED_TOOL_NAMES, ToolExecutor
from app.core.config import get_settings
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
    OpenAICompatibleChatModelProvider,
    ToolCallingChatModelResult,
    create_chat_model_provider,
)
from app.services.observability.latency_trace import (
    LatencyTrace,
    bind_agent_conversation_cache_scope,
    bind_user_question_cache_key,
    get_current_latency_trace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.route_context import (
    reset_phase64_route_kind,
    set_phase64_route_kind,
)
from app.services.retrieval.hybrid_search import (
    reset_current_hyde_vector_query,
    set_current_hyde_vector_query,
)
from app.services.retrieval.runtime import (
    retrieval_runtime_result_limit,
    reset_current_retrieval_plan,
    set_current_retrieval_plan,
)


TOOL_CALLING_DEFAULT_MAX_ITERATIONS = 3
TOOL_CALLING_HARD_MAX_ITERATIONS = 3
TOOL_RESULT_SNIPPET_LIMIT = 900
TOOL_RESULT_MAX_SOURCES = 8
TOOL_CALLING_MAX_EXECUTED_TOOLS_PER_ITERATION = 1
TOOL_CALLING_NEAR_DUPLICATE_THRESHOLD = 0.65
TOOL_CALLING_PREFERRED_TOOL_ORDER = {
    "hybrid_search_knowledge": 0,
    "search_figures": 1,
    "search_tables": 2,
}
ToolCallingFinalAnswerStrategy = Literal["baseline", "structured_final_answer"]
TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY: ToolCallingFinalAnswerStrategy = (
    "structured_final_answer"
)
agent_logger = logging.getLogger("rfc_rag_agent.agent")


@dataclass
class FinalPromptShape:
    character_count: int = 0
    cjk_character_count: int = 0
    source_count: int = 0
    history_character_count: int = 0
    estimated_input_tokens: int = 0
    budget_applied: bool = False

    def as_trace_values(self) -> dict[str, int]:
        return {
            "final_prompt_character_count": self.character_count,
            "final_prompt_cjk_character_count": self.cjk_character_count,
            "final_prompt_source_count": self.source_count,
            "final_prompt_history_character_count": self.history_character_count,
            "final_prompt_estimated_input_tokens": self.estimated_input_tokens,
            "final_prompt_budget_applied": self.budget_applied,
        }


ToolCallingEventSink = Callable[[ToolCallingRuntimeEvent], None]
InternalToolCallingEventSink = ToolCallingEventSink | RuntimeEventBus


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


def build_tool_calling_pre_tool_gate_decision(
    *,
    question: str,
    runtime_state: AgentRuntimeState,
    resume_should_resume: bool,
    latency_trace: LatencyTrace,
) -> PreToolGateDecision:
    responsibility_gate = evaluate_responsibility_gate(question)
    if responsibility_gate.triggered:
        return PreToolGateDecision(
            action="return",
            result=build_pre_tool_refusal_result(
                question=question,
                answer=RESPONSIBILITY_REFUSAL_ANSWER,
                refusal_reason=responsibility_gate.refusal_reason,
                gate_name="responsibility_gate",
                output_summary="refused=True responsibility_gate",
                reasoning_summary=(
                    "tool_calling_agent refused before tool loop via responsibility_gate."
                ),
                latency_trace=latency_trace,
            ),
            stop_reason="invalid_request",
            final_decision="refuse",
            sanitized_detail="responsibility_gate_triggered",
        )

    topic_gate_query = " ".join(
        [
            runtime_state.context.standalone_task or question,
            *runtime_state.context.history,
        ]
    )
    if not resume_should_resume and not has_topic_anchor(topic_gate_query):
        return PreToolGateDecision(
            action="return",
            result=build_pre_tool_refusal_result(
                question=question,
                answer="当前问题缺少项目资料库的领域锚点，无法基于堆石混凝土资料可靠回答。",
                refusal_reason="Question appears off-topic: no domain anchor was found.",
                gate_name="off_topic_gate",
                output_summary="refused=True off_topic",
                reasoning_summary=(
                    "tool_calling_agent refused before tool loop via off_topic_gate."
                ),
                latency_trace=latency_trace,
            ),
            stop_reason="invalid_request",
            final_decision="refuse",
            sanitized_detail="off_topic",
        )

    return PreToolGateDecision(action="continue")


def build_tool_calling_resume_gate_decision(
    *,
    question: str,
    resume_decision: object,
    chat_model_provider: ChatModelProvider,
    history: Sequence[str] | None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy,
    runtime_state: AgentRuntimeState,
    latency_trace: LatencyTrace,
) -> PreToolGateDecision:
    run = getattr(resume_decision, "run", None)
    if not getattr(resume_decision, "should_resume", False) or run is None:
        return PreToolGateDecision(action="continue")

    result = result_from_runtime_checkpoint(
        question=question,
        run_state=load_runtime_state(run),
        chat_model_provider=chat_model_provider,
        history=history,
        final_answer_strategy=final_answer_strategy,
        runtime_state=runtime_state,
        latency_trace=latency_trace,
    )
    return PreToolGateDecision(
        action="return",
        result=result,
        stop_reason="checkpoint_unavailable" if result.refused else "completed",
        final_decision="refuse" if result.refused else "answer",
        sanitized_detail=(
            "resume_checkpoint_without_sources"
            if result.refused
            else "runtime_resume_completed"
        ),
        citations=tuple(result.citations),
    )


def build_tool_calling_semantic_cache_gate_decision(
    *,
    question: str,
    settings: object,
    evidence_identity: object,
    toolbox: AgentToolbox,
    chat_model_provider: ChatModelProvider,
    history: Sequence[str] | None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy,
    runtime_state: AgentRuntimeState,
    latency_trace: LatencyTrace,
    runtime_event_bus: RuntimeEventBus,
    workflow_steps: list[AgentToolCallRecord],
    tool_calls: list[AgentToolCallRecord],
) -> PreToolGateDecision:
    if not (
        getattr(settings, "semantic_evidence_cache_enabled", False)
        and getattr(evidence_identity, "safe_for_cache_reuse", False)
    ):
        return PreToolGateDecision(action="continue")

    semantic_cache_tool_name = semantic_cache_tool_for_identity(evidence_identity)
    latency_trace.set_value("semantic_cache_tool_name", semantic_cache_tool_name)
    semantic_cached = toolbox.lookup_semantic_evidence_cache(
        getattr(evidence_identity, "canonical_query", None)
        or runtime_state.context.standalone_task
        or question,
        top_k=retrieval_runtime_result_limit(
            semantic_cache_tool_name,
            settings,
        ),
        tool_name=semantic_cache_tool_name,
    )
    if semantic_cached is None or not semantic_cached.search_results:
        return PreToolGateDecision(action="continue")

    latency_trace.set_value("semantic_cache_hit", True)
    latency_trace.set_value("semantic_cache_reason", "tool_result_cache_hit")
    latency_trace.set_value("hyde_generated", False)
    latency_trace.set_value("hyde_used_for_vector", False)
    latency_trace.set_value("hyde_reason", "semantic_cache_hit")
    workflow_steps.append(semantic_cached.call)
    tool_calls.append(semantic_cached.call)
    runtime_state.evidence.add(
        tool_name=semantic_cached.tool_name,
        query=getattr(evidence_identity, "canonical_query", None)
        or runtime_state.context.standalone_task
        or question,
        result_count=len(semantic_cached.search_results),
        succeeded=semantic_cached.call.succeeded,
    )
    runtime_state.set_stop_reason("semantic_evidence_cache_hit")
    runtime_state.final_decision = "answer"
    apply_runtime_diagnostics(latency_trace, runtime_state)
    publish_tool_call_result(
        runtime_event_bus,
        iteration=1,
        record=semantic_cached.call,
        selected_count=len(semantic_cached.search_results),
    )
    result = result_from_cached_evidence(
        question=question,
        search_results=list(semantic_cached.search_results),
        sources=list(semantic_cached.sources),
        tool_calls=tool_calls,
        workflow_steps=workflow_steps,
        chat_model_provider=chat_model_provider,
        history=history,
        final_answer_strategy=final_answer_strategy,
        runtime_state=runtime_state,
        latency_trace=latency_trace,
    )
    return PreToolGateDecision(
        action="return",
        result=result,
        stop_reason="insufficient_evidence" if result.refused else "completed",
        final_decision="refuse" if result.refused else "answer",
        sanitized_detail=(
            "cached_evidence_without_citations"
            if result.refused
            else "semantic_evidence_cache_hit"
        ),
        citations=tuple(result.citations),
        citation_repair_count=int(result.latency_trace.get("citation_repair_count", 0) or 0),
    )


def build_tool_calling_combined_pre_tool_gate_decision(
    *,
    question: str,
    runtime_state: AgentRuntimeState,
    latency_trace: LatencyTrace,
    run_pre_tool_gate: bool = True,
    resume_should_resume: bool = False,
    run_resume_gate: bool = False,
    resume_decision: object | None = None,
    chat_model_provider: ChatModelProvider | None = None,
    history: Sequence[str] | None = None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy = (
        TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY
    ),
    run_semantic_cache_gate: bool = False,
    settings: object | None = None,
    evidence_identity: object | None = None,
    toolbox: AgentToolbox | None = None,
    runtime_event_bus: RuntimeEventBus | None = None,
    workflow_steps: list[AgentToolCallRecord] | None = None,
    tool_calls: list[AgentToolCallRecord] | None = None,
) -> PreToolGateDecision:
    if run_pre_tool_gate:
        decision = build_tool_calling_pre_tool_gate_decision(
            question=question,
            runtime_state=runtime_state,
            resume_should_resume=resume_should_resume,
            latency_trace=latency_trace,
        )
        if decision.action == "return":
            return decision

    if run_resume_gate:
        if resume_decision is None or chat_model_provider is None:
            raise ValueError("resume gate requires resume_decision and chat_model_provider")
        decision = build_tool_calling_resume_gate_decision(
            question=question,
            resume_decision=resume_decision,
            chat_model_provider=chat_model_provider,
            history=history,
            final_answer_strategy=final_answer_strategy,
            runtime_state=runtime_state,
            latency_trace=latency_trace,
        )
        if decision.action == "return":
            return decision

    if run_semantic_cache_gate:
        if (
            settings is None
            or evidence_identity is None
            or toolbox is None
            or chat_model_provider is None
            or runtime_event_bus is None
            or workflow_steps is None
            or tool_calls is None
        ):
            raise ValueError("semantic cache gate dependencies are required")
        decision = build_tool_calling_semantic_cache_gate_decision(
            question=question,
            settings=settings,
            evidence_identity=evidence_identity,
            toolbox=toolbox,
            chat_model_provider=chat_model_provider,
            history=history,
            final_answer_strategy=final_answer_strategy,
            runtime_state=runtime_state,
            latency_trace=latency_trace,
            runtime_event_bus=runtime_event_bus,
            workflow_steps=workflow_steps,
            tool_calls=tool_calls,
        )
        if decision.action == "return":
            return decision

    return PreToolGateDecision(action="continue")


class ToolCallingCoordinatorGateAdapter:
    """Callable adapter that lets RunCoordinator reuse service-owned gates."""

    def __init__(
        self,
        *,
        run_pre_tool_gate: bool = True,
        run_resume_gate: bool = False,
        run_semantic_cache_gate: bool = False,
        resume_decision: object | None = None,
        chat_model_provider: ChatModelProvider | None = None,
        final_answer_strategy: ToolCallingFinalAnswerStrategy = (
            TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY
        ),
        settings: object | None = None,
        toolbox: AgentToolbox | None = None,
        runtime_event_bus: RuntimeEventBus | None = None,
        workflow_steps: list[AgentToolCallRecord] | None = None,
        tool_calls: list[AgentToolCallRecord] | None = None,
        resume_completion_recorder: Callable[[object], None] | None = None,
        defer_required_tool_gates: bool = True,
    ) -> None:
        self.run_pre_tool_gate = run_pre_tool_gate
        self.run_resume_gate = run_resume_gate
        self.run_semantic_cache_gate = run_semantic_cache_gate
        self.resume_decision = resume_decision
        self.chat_model_provider = chat_model_provider
        self.final_answer_strategy = final_answer_strategy
        self.settings = settings
        self.toolbox = toolbox
        self.runtime_event_bus = runtime_event_bus
        self.workflow_steps = workflow_steps
        self.tool_calls = tool_calls
        self.resume_completion_recorder = resume_completion_recorder
        self.defer_required_tool_gates = defer_required_tool_gates

    def __call__(
        self,
        request: CoordinatorRequest,
        planning: object,
        run: object,
    ) -> PreToolGateDecision:
        del run
        runtime_state = getattr(planning, "runtime_state", None)
        if runtime_state is None:
            raise ValueError("planning.runtime_state is required for pre-tool gates")
        required_tool = getattr(getattr(planning, "action", None), "required_tool", None)
        required_tool_preflight_pending = bool(str(required_tool or "").strip())
        if self.defer_required_tool_gates and required_tool_preflight_pending and (
            self.run_resume_gate or self.run_semantic_cache_gate
        ):
            request.latency_trace.set_value(
                "run_coordinator_pre_tool_gate_skip_reason",
                "required_tool_preflight_priority",
            )
            request.latency_trace.set_value(
                "run_coordinator_required_tool_preflight",
                str(required_tool),
            )
        decision = build_tool_calling_combined_pre_tool_gate_decision(
            question=request.question,
            runtime_state=runtime_state,
            latency_trace=request.latency_trace,
            run_pre_tool_gate=self.run_pre_tool_gate,
            resume_should_resume=bool(
                getattr(self.resume_decision, "should_resume", False)
            ),
            run_resume_gate=self.run_resume_gate
            and not (
                self.defer_required_tool_gates
                and required_tool_preflight_pending
            ),
            resume_decision=self.resume_decision,
            chat_model_provider=self.chat_model_provider,
            history=request.history,
            final_answer_strategy=self.final_answer_strategy,
            run_semantic_cache_gate=self.run_semantic_cache_gate
            and not (
                self.defer_required_tool_gates
                and required_tool_preflight_pending
            ),
            settings=self.settings,
            evidence_identity=getattr(planning, "identity", None),
            toolbox=self.toolbox,
            runtime_event_bus=self.runtime_event_bus,
            workflow_steps=self.workflow_steps,
            tool_calls=self.tool_calls,
        )
        if (
            decision.action == "return"
            and decision.sanitized_detail
            in {"runtime_resume_completed", "resume_checkpoint_without_sources"}
            and self.resume_completion_recorder is not None
            and getattr(self.resume_decision, "run", None) is not None
        ):
            self.resume_completion_recorder(getattr(self.resume_decision, "run"))
        return decision


class ToolCallingFinalAnswerFacade:
    """RunCoordinator-facing final answer adapter preserving service result shape."""

    def __init__(
        self,
        *,
        chat_model_provider: ChatModelProvider,
    ) -> None:
        self._chat_model_provider = chat_model_provider

    def generate(self, request: FinalAnswerRequest) -> FinalAnswerOutcome:
        return FinalAnswerController(
            self._chat_model_provider,
            answer_messages=evidence_answer_messages,
            repair_messages=citation_repair_messages,
            citation_extractor=extract_citations,
        ).generate(request)

    def refuse(self, request: FinalAnswerRequest) -> FinalAnswerOutcome:
        stop_detail = request.runtime_state.stop_reason
        if not stop_detail or stop_detail == "not_stopped":
            stop_detail = "insufficient_evidence"
            request.runtime_state.set_stop_reason(stop_detail)
        request.runtime_state.final_decision = "refuse"
        stop_reason = request.runtime_state.normalized_stop_reason or "insufficient_evidence"
        if stop_reason not in RuntimeStopReason.__args__:
            stop_reason = "insufficient_evidence"
        refusal_reason = runtime_refusal_message_for_request(request, stop_detail)
        workflow_steps = list(request.workflow_steps)
        workflow_steps.append(
            AgentToolCallRecord(
                tool_name="final_answer",
                input_summary="run coordinator refusal",
                output_summary=refusal_reason,
                succeeded=False,
                error=refusal_reason,
                step_id="final",
            )
        )
        result = build_tool_calling_result(
            question=request.question,
            answer=refusal_reason,
            tool_calls=list(request.tool_calls),
            workflow_steps=workflow_steps,
            search_results=list(request.search_results),
            sources=list(request.sources),
            citations=[],
            refused=True,
            refusal_reason=refusal_reason,
            llm_call_count=0,
            repeated_query_count=0,
            near_duplicate_query_count=0,
            skipped_tool_call_count=0,
            executed_tool_call_count=len(request.tool_calls),
            citation_repair_count=0,
            runtime_state=request.runtime_state,
            latency_trace=request.latency_trace.finalize(
                iteration_count=len(workflow_steps),
                tool_call_count=len(request.tool_calls),
            ),
        )
        return FinalAnswerController.outcome_from_result(
            result=result,
            citations=(),
            citation_repair_count=0,
            stop_reason=stop_reason,
        )


def runtime_refusal_message(stop_detail: str) -> str:
    """Return a bounded user-facing refusal reason without leaking raw internals."""

    if stop_detail == "deadline_exhausted":
        return (
            "Runtime deadline was exhausted before enough reliable evidence could "
            "be assembled."
        )
    if stop_detail == "reranking_failed":
        return (
            "Evidence reranking failed, so the agent refused to answer without "
            "reliable ranked sources."
        )
    if stop_detail == "required_evidence_missing":
        return "Required evidence was not found in the available project sources."
    if stop_detail == "completed_tool_replay_prevented":
        return (
            "Runtime checkpoint recovery prevented a duplicate completed tool "
            "execution, so the agent refused instead of replaying retrieval."
        )
    if stop_detail == "tool_budget_exhausted":
        return (
            "Runtime tool budget was exhausted before enough reliable evidence "
            "could be assembled."
        )
    if stop_detail == "tool_execution_failed":
        return (
            "Tool execution failed before the agent could assemble valid "
            "tool-backed citations."
        )
    if stop_detail in {"evidence_exhausted", "insufficient_evidence"}:
        return "Runtime evidence state refused final generation due to insufficient evidence."
    return "Runtime evidence state refused final generation."


def runtime_refusal_message_for_request(
    request: FinalAnswerRequest,
    stop_detail: str,
) -> str:
    """Return refusal text, preserving safe legacy tool-failure details when useful."""
    if stop_detail == "reranking_failed":
        for record in reversed((*request.workflow_steps, *request.tool_calls)):
            error = str(getattr(record, "error", "") or "").strip()
            if error and (
                "rerank" in error.lower()
                or "重排序" in error
                or "重排" in error
            ):
                return error
    if stop_detail == "required_evidence_missing":
        refusal_reason = str(
            request.latency_trace.values.get("runtime_tool_refusal_reason", "") or ""
        ).strip()
        if refusal_reason:
            return refusal_reason
    return runtime_refusal_message(stop_detail)


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
        max_tool_calls: int = TOOL_CALLING_DEFAULT_MAX_ITERATIONS,
        history: Sequence[str] | None = None,
        event_sink: ToolCallingEventSink | None = None,
        conversation_id: int | None = None,
        resume_policy: str = "auto",
        resume_run_id: str | None = None,
        image_path: str | None = None,
        latency_trace: LatencyTrace | None = None,
        evaluation_run_namespace: str | None = None,
    ) -> AgentQueryResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be greater than 0")

        log_event(
            agent_logger,
            "query_received",
            mode="tool_calling_agent",
            retrieval_budget_owner="runtime",
            max_tool_calls=max_tool_calls,
            final_answer_strategy=self.final_answer_strategy,
            question_summary=safe_text_summary(normalized_question, limit=80),
        )

        latency_trace = latency_trace or LatencyTrace()
        bind_user_question_cache_key(latency_trace, normalized_question)
        bind_agent_conversation_cache_scope(
            latency_trace,
            conversation_id,
            evaluation_run_namespace=evaluation_run_namespace,
        )
        runtime_event_bus = RuntimeEventBus(
            run_id=uuid.uuid4().hex,
            trace=latency_trace,
        )
        if event_sink is not None:
            legacy_event_sink = event_sink
            runtime_event_bus.subscribe(
                lambda runtime_event: legacy_event_sink(
                    project_tool_calling_event(runtime_event)
                )
            )
        settings = get_settings()
        if settings.agent_run_coordinator_enabled:
            if image_path is None:
                return self._query_with_run_coordinator(
                    question=normalized_question,
                    max_tool_calls=max_tool_calls,
                    history=history,
                    conversation_id=conversation_id,
                    resume_policy=resume_policy,
                    resume_run_id=resume_run_id,
                    image_path=image_path,
                    latency_trace=latency_trace,
                    runtime_event_bus=runtime_event_bus,
                    settings=settings,
                )
            latency_trace.set_value("run_coordinator_enabled", False)
            latency_trace.set_value(
                "run_coordinator_skip_reason",
                "uploaded_image_uses_legacy_multimodal_path",
            )
        else:
            latency_trace.set_value("run_coordinator_enabled", False)
            latency_trace.set_value("run_coordinator_skip_reason", "disabled")
        runtime_event_sink: InternalToolCallingEventSink = runtime_event_bus
        tool_executor = ToolExecutor(self.toolbox, event_bus=runtime_event_bus)
        planning_trace_token = set_current_latency_trace(latency_trace)
        try:
            planning_policy = PlanningPolicy(self.runtime_identity_provider)
            planning = planning_policy.plan(
                PlanningRequest(
                    question=normalized_question,
                    history=tuple(history or ()),
                    image_path=image_path,
                    trace=latency_trace,
                )
            )
        finally:
            reset_current_latency_trace(planning_trace_token)
        runtime = AgentRuntime()
        runtime_state = planning.runtime_state
        evidence_identity = planning.identity
        route_decision = planning.route
        retrieval_plan = planning.plan
        retrieval_action = planning.action
        runtime_identity_provider = phase64_runtime_identity_provider(
            self.runtime_identity_provider,
            settings,
        )
        runtime_repository = AgentRuntimeRunRepository(self.db)
        checkpoint_repository = CheckpointRepository(runtime_repository)
        resume_decision = decide_resume(
            repository=runtime_repository,
            conversation_id=conversation_id,
            question=normalized_question,
            history=tuple(history or ()),
            resume_policy=resume_policy,
            resume_run_id=resume_run_id,
        )

        pre_tool_gate = build_tool_calling_combined_pre_tool_gate_decision(
            question=normalized_question,
            runtime_state=runtime_state,
            resume_should_resume=resume_decision.should_resume,
            latency_trace=latency_trace,
            run_pre_tool_gate=True,
            run_resume_gate=False,
            run_semantic_cache_gate=False,
        )
        if pre_tool_gate.action == "return":
            log_event(
                agent_logger,
                "refusal_triggered",
                mode="tool_calling_agent",
                refusal_category=pre_tool_gate.sanitized_detail,
                source_count=0,
                citation_count=0,
                tool_call_count=0,
            )
            if pre_tool_gate.result is None:
                raise RuntimeError("pre-tool gate return decision did not include a result")
            return pre_tool_gate.result

        max_iterations = min(max_tool_calls, TOOL_CALLING_HARD_MAX_ITERATIONS)
        run_budget = RunBudget(
            max_tool_calls=max_tool_calls,
            max_iterations=max_iterations,
        )
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
        needs_figure_evidence = (
            retrieval_action.required_tool == "search_figures"
            or should_search_figures(normalized_question)
        )
        figure_search_executed = False
        repeated_query_count = 0
        near_duplicate_query_count = 0
        skipped_tool_call_count = 0
        executed_tool_call_count = 0
        citation_repair_count = 0
        llm_call_count = 0
        for key, value in runtime_resume_diagnostics(resume_decision).items():
            latency_trace.set_value(key, value)
        apply_runtime_diagnostics(latency_trace, runtime_state)
        latency_token = set_current_latency_trace(latency_trace)
        retrieval_token = set_current_retrieval_plan(retrieval_plan)
        phase64_route_token = set_phase64_route_kind(
            route_decision.kind
            if route_decision is not None
            else ("complex" if settings.agent_short_loop_enabled else "legacy")
        )
        hyde_token = None

        try:
            if image_path:
                image_started = time.perf_counter()
                image_tool_result = self.toolbox.analyze_user_image(
                    image_path,
                    normalized_question,
                    top_k=retrieval_runtime_result_limit("analyze_user_image", settings),
                )
                image_call = replace(image_tool_result.call, step_id="uploaded-image-analysis")
                image_tool_result = replace(image_tool_result, call=image_call)
                latency_trace.add_duration(
                    "tool_latency_ms",
                    (time.perf_counter() - image_started) * 1000.0,
                )
                tool_calls.append(image_call)
                workflow_steps.append(image_call)
                search_results = merge_search_results(
                    search_results,
                    image_tool_result.search_results,
                )
                sources = merge_sources(sources, image_tool_result.sources)
                runtime_state.evidence.add(
                    tool_name=image_tool_result.tool_name,
                    query=normalized_question,
                    result_count=len(image_tool_result.search_results),
                    succeeded=image_call.succeeded,
                )
                apply_runtime_diagnostics(latency_trace, runtime_state)
                self._emit(
                    runtime_event_sink,
                    "tool_call_start",
                    {
                        "iteration": 1,
                        "step_id": image_call.step_id,
                        "tool_name": image_call.tool_name,
                        "input_summary": image_call.input_summary,
                    },
                )
                publish_tool_call_result(
                    runtime_event_bus,
                    iteration=1,
                    record=image_call,
                )
                return outcome_from_tool_calling_loop(
                    question=normalized_question,
                    answer="" if image_tool_result.refused else (image_tool_result.answer or ""),
                    tool_calls=tool_calls,
                    workflow_steps=workflow_steps,
                    search_results=search_results,
                    sources=sources,
                    citations=list(range(1, len(sources) + 1)) if sources else [],
                    refused=image_tool_result.refused,
                    refusal_reason=image_tool_result.refusal_reason,
                    llm_call_count=0,
                    repeated_query_count=0,
                    near_duplicate_query_count=0,
                    skipped_tool_call_count=0,
                    executed_tool_call_count=1,
                    citation_repair_count=0,
                    runtime_state=runtime_state,
                    latency_trace=latency_trace.finalize(
                        iteration_count=1,
                        tool_call_count=1,
                    ),
                    stop_reason=(
                        "insufficient_evidence"
                        if image_tool_result.refused
                        else "completed"
                    ),
                    image_analysis=image_tool_result.image_analysis,
                ).result

            if retrieval_action.required_tool is not None:
                preflight_query = (
                    runtime_state.context.standalone_task or normalized_question
                )
                preflight_tool_name = retrieval_action.required_tool
                preflight_started = time.perf_counter()
                preflight_result = tool_executor.execute(
                    ToolExecutionRequest(
                        call=ChatToolCall(
                            id=f"runtime-{preflight_tool_name}",
                            name=preflight_tool_name,
                            arguments={"query": preflight_query},
                        ),
                        default_query=preflight_query,
                        iteration=1,
                    )
                ).result
                figure_search_executed = preflight_tool_name == "search_figures"
                latency_trace.add_duration(
                    "tool_latency_ms",
                    (time.perf_counter() - preflight_started) * 1000.0,
                )
                tool_calls.append(preflight_result.call)
                workflow_steps.append(preflight_result.call)
                executed_tool_call_count += 1
                search_results = merge_search_results(
                    search_results,
                    preflight_result.search_results,
                )
                sources = merge_sources(sources, preflight_result.sources)
                runtime_state.evidence.add(
                    tool_name=preflight_result.tool_name,
                    query=preflight_query,
                    result_count=len(preflight_result.search_results),
                    succeeded=preflight_result.call.succeeded,
                )
                if preflight_result.call.succeeded:
                    latency_trace.set_value(
                        "retrieval_selected_count",
                        len(preflight_result.search_results),
                    )
                    latency_trace.set_value(
                        "retrieval_selected_chunk_ids",
                        [item.chunk_id for item in preflight_result.search_results],
                    )
                apply_runtime_diagnostics(latency_trace, runtime_state)
                if not preflight_result.search_results:
                    refusal_reason = (
                        preflight_result.refusal_reason
                        or f"No relevant {preflight_tool_name} evidence was found."
                    )
                    runtime_state.set_stop_reason("required_asset_evidence_not_found")
                    runtime_state.final_decision = "refuse"
                    apply_runtime_diagnostics(latency_trace, runtime_state)
                    return outcome_from_tool_calling_loop(
                        question=normalized_question,
                        answer=refusal_reason,
                        tool_calls=tool_calls,
                        workflow_steps=workflow_steps,
                        search_results=search_results,
                        sources=sources,
                        citations=[],
                        refused=True,
                        refusal_reason=refusal_reason,
                        llm_call_count=0,
                        repeated_query_count=0,
                        near_duplicate_query_count=0,
                        skipped_tool_call_count=0,
                        executed_tool_call_count=executed_tool_call_count,
                        citation_repair_count=0,
                        runtime_state=runtime_state,
                        latency_trace=latency_trace.finalize(
                            iteration_count=len(workflow_steps),
                            tool_call_count=len(tool_calls),
                        ),
                        stop_reason="insufficient_evidence",
                    ).result

            post_preflight_gate = build_tool_calling_combined_pre_tool_gate_decision(
                question=normalized_question,
                runtime_state=runtime_state,
                latency_trace=latency_trace,
                run_pre_tool_gate=False,
                resume_should_resume=resume_decision.should_resume,
                run_resume_gate=True,
                resume_decision=resume_decision,
                chat_model_provider=self.chat_model_provider,
                history=history,
                final_answer_strategy=self.final_answer_strategy,
                run_semantic_cache_gate=True,
                settings=settings,
                evidence_identity=evidence_identity,
                toolbox=self.toolbox,
                runtime_event_bus=runtime_event_bus,
                workflow_steps=workflow_steps,
                tool_calls=tool_calls,
            )
            if post_preflight_gate.action == "return":
                if resume_decision.should_resume and resume_decision.run is not None:
                    checkpoint_repository.persist_state(
                        resume_decision.run,
                        node="final_answer_completed",
                        state={
                            **load_runtime_state(resume_decision.run),
                            "resume_completed": True,
                        },
                        status="completed",
                    )
                if post_preflight_gate.result is None:
                    raise RuntimeError(
                        "post-preflight gate return decision did not include a result"
                    )
                return post_preflight_gate.result
            latency_trace.set_value("semantic_cache_hit", False)
            latency_trace.set_value(
                "semantic_cache_reason",
                (
                    "miss"
                    if settings.semantic_evidence_cache_enabled
                    and evidence_identity.safe_for_cache_reuse
                    else (
                        "identity_not_reusable"
                        if settings.semantic_evidence_cache_enabled
                        else "disabled"
                    )
                ),
            )
            if settings.agent_short_loop_enabled:
                hyde_query = ""
                if evidence_identity.hyde_passage:
                    canonical_task = (
                        evidence_identity.canonical_query
                        or runtime_state.context.standalone_task
                        or normalized_question
                    )
                    hyde_query = (
                        f"{canonical_task}\n\nHypothetical evidence for vector retrieval only:\n"
                        f"{evidence_identity.hyde_passage}"
                    )
                    latency_trace.set_value("hyde_generated", True)
                    latency_trace.set_value("hyde_used_for_vector", True)
                    latency_trace.set_value("hyde_reason", "unified_planner")
                    latency_trace.set_value("hyde_model", evidence_identity.model_name)
                else:
                    latency_trace.set_value("hyde_generated", False)
                    latency_trace.set_value("hyde_used_for_vector", False)
                    latency_trace.set_value("hyde_reason", "planner_empty")
            else:
                hyde_query = generate_hyde_vector_query(
                    canonical_task=evidence_identity.canonical_query
                    or runtime_state.context.standalone_task
                    or normalized_question,
                    provider=runtime_identity_provider,
                    latency_trace=latency_trace,
                )
            if hyde_query:
                hyde_token = set_current_hyde_vector_query(hyde_query)

            active_run = None
            if conversation_id is not None:
                active_run = checkpoint_repository.start(
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

            final_answer_provider = phase64_final_answer_provider(
                self.chat_model_provider,
                settings,
            )

            if settings.agent_short_loop_enabled and not sources:
                short_loop_outcome = tool_executor.execute_short_loop(
                    runtime=runtime,
                    runtime_state=runtime_state,
                    retrieval_action=retrieval_action,
                    canonical_task=(
                        evidence_identity.canonical_query
                        or runtime_state.context.standalone_task
                        or normalized_question
                    ),
                    default_query=normalized_question,
                    iteration=1,
                )
                latency_trace.add_duration("tool_latency_ms", short_loop_outcome.elapsed_ms)
                short_loop_result = short_loop_outcome.result
                min_selected_sources = max(
                    1,
                    int(settings.phase64_fast_path_min_selected_sources),
                )
                if (
                    route_decision is not None
                    and route_decision.kind == "fast"
                    and len(short_loop_result.sources) < min_selected_sources
                ):
                    latency_trace.set_value("phase64_fast_escalated", True)
                    latency_trace.set_value(
                        "phase64_fast_escalation_reason",
                        "insufficient_selected_sources",
                    )
                    planning = planning_policy.escalate_fast_route(
                        PlanningRequest(
                            question=normalized_question,
                            history=tuple(history or ()),
                            image_path=image_path,
                            trace=latency_trace,
                        ),
                        planning,
                    )
                    evidence_identity = planning.identity
                    retrieval_plan = planning.plan
                    retrieval_action = planning.action
                    reset_current_retrieval_plan(retrieval_token)
                    retrieval_token = set_current_retrieval_plan(retrieval_plan)
                    reset_phase64_route_kind(phase64_route_token)
                    phase64_route_token = set_phase64_route_kind("complex")
                    if evidence_identity.hyde_passage:
                        canonical_task = (
                            evidence_identity.canonical_query
                            or runtime_state.context.standalone_task
                            or normalized_question
                        )
                        hyde_query = (
                            f"{canonical_task}\n\nHypothetical evidence for vector retrieval only:\n"
                            f"{evidence_identity.hyde_passage}"
                        )
                        hyde_token = set_current_hyde_vector_query(hyde_query)
                        latency_trace.set_value("hyde_generated", True)
                        latency_trace.set_value("hyde_used_for_vector", True)
                        latency_trace.set_value("hyde_reason", "fast_path_escalation")
                        latency_trace.set_value("hyde_model", evidence_identity.model_name)
                    short_loop_outcome = tool_executor.execute_short_loop(
                        runtime=runtime,
                        runtime_state=runtime_state,
                        retrieval_action=retrieval_action,
                        canonical_task=(
                            evidence_identity.canonical_query
                            or runtime_state.context.standalone_task
                            or normalized_question
                        ),
                        default_query=normalized_question,
                        iteration=2,
                    )
                    latency_trace.add_duration("tool_latency_ms", short_loop_outcome.elapsed_ms)
                    short_loop_result = short_loop_outcome.result
                elif route_decision is not None and route_decision.kind == "fast":
                    latency_trace.set_value("phase64_fast_escalated", False)
                    latency_trace.set_value("phase64_fast_escalation_reason", "")
                if short_loop_result.call.succeeded and short_loop_result.tool_name in ALLOWED_TOOL_NAMES:
                    latency_trace.set_value(
                        "retrieval_selected_count",
                        len(short_loop_result.search_results),
                    )
                    latency_trace.set_value(
                        "retrieval_selected_chunk_ids",
                        [item.chunk_id for item in short_loop_result.search_results],
                    )
                executed_tool_call_count += 1
                tool_calls.append(short_loop_result.call)
                workflow_steps.append(short_loop_result.call)
                runtime_state.evidence.add(
                    tool_name=short_loop_result.tool_name,
                    query=(
                        evidence_identity.canonical_query
                        or runtime_state.context.standalone_task
                        or normalized_question
                    ),
                    result_count=len(short_loop_result.search_results),
                    succeeded=short_loop_result.call.succeeded,
                )
                apply_runtime_diagnostics(latency_trace, runtime_state)
                search_results = merge_search_results(
                    search_results,
                    short_loop_result.search_results,
                )
                sources = merge_sources(sources, short_loop_result.sources)
                checkpoint_repository.persist_state(
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
                if not sources:
                    evidence_decision = EvidenceStateMachine(
                        required_tool=retrieval_action.required_tool,
                        result_count=0,
                        rerank_failed=is_reranking_failure(short_loop_result.call),
                        escalation_count=(
                            planning.escalation_count
                            if route_decision is not None and route_decision.kind == "fast"
                            else 1
                        ),
                        budget=run_budget,
                    ).decide()
                    refusal_reason = (
                        short_loop_result.refusal_reason
                        or short_loop_result.call.error
                        or short_loop_result.call.output_summary
                        or "No relevant evidence was found for the current question."
                    )
                    runtime_state.set_stop_reason(
                        "reranking_failed"
                        if evidence_decision.sanitized_detail == "reranking_failed"
                        else "short_loop_evidence_not_found"
                    )
                    runtime_state.final_decision = "refuse"
                    apply_runtime_diagnostics(latency_trace, runtime_state)
                    checkpoint_repository.persist_state(
                        active_run,
                        node=runtime_state.stop_reason,
                        state=runtime_checkpoint_state(
                            runtime_state=runtime_state,
                            workflow_steps=workflow_steps,
                            tool_calls=tool_calls,
                            sources=sources,
                            latency_trace=latency_trace.values,
                        ),
                        status="failed",
                    )
                    return outcome_from_tool_calling_loop(
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
                        stop_reason="insufficient_evidence",
                    ).result

            for iteration in range(1, max_iterations + 1):
                streaming_final_generation = bool(sources)
                self._emit(
                    runtime_event_sink,
                    "agent_step",
                    {
                        "iteration": iteration,
                        "action": (
                            "stream_final_answer"
                            if streaming_final_generation
                            else "llm_with_tools"
                        ),
                        "step_summary": (
                            "streaming final answer from retrieved evidence"
                            if streaming_final_generation
                            else "calling model with tool definitions"
                        ),
                    },
                )
                llm_started = time.perf_counter()
                streamed_by_controller = False
                if streaming_final_generation:
                    latency_trace.set_value(
                        "final_generation_call_count",
                        int(latency_trace.values["final_generation_call_count"]) + 1,
                    )
                    latency_trace.set_value(
                        "total_model_call_count",
                        int(latency_trace.values["total_model_call_count"]) + 1,
                    )
                    if hasattr(final_answer_provider, "stream_generate"):
                        final_prompt_shape = None
                        if settings.agent_short_loop_enabled:
                            final_prompt_shape = FinalPromptShape()
                            prompt_budgets = phase64_final_prompt_budgets(settings)
                        else:
                            prompt_budgets = {}
                        try:
                            streamed = FinalAnswerController(
                                final_answer_provider,
                                answer_messages=evidence_answer_messages,
                                repair_messages=citation_repair_messages,
                                citation_extractor=extract_citations,
                            ).stream_final_evidence(
                                question=normalized_question,
                                sources=sources,
                                history=history,
                                strategy=self.final_answer_strategy,
                                trace=latency_trace,
                                prompt_budgets=prompt_budgets,
                                token_emitter=getattr(
                                    final_answer_provider,
                                    "emit_stream_token",
                                    None,
                                ),
                                prompt_shape=final_prompt_shape,
                                emit_answer_tokens=False,
                            )
                        except (RuntimeError, ValueError) as exc:
                            latency_trace.add_duration(
                                "final_generation_latency_ms",
                                (time.perf_counter() - llm_started) * 1000.0,
                            )
                            return result_from_final_generation_failure(
                                question=normalized_question,
                                sources=sources,
                                search_results=search_results,
                                tool_calls=tool_calls,
                                workflow_steps=workflow_steps,
                                llm_call_count=llm_call_count + 1,
                                repeated_query_count=repeated_query_count,
                                near_duplicate_query_count=near_duplicate_query_count,
                                skipped_tool_call_count=skipped_tool_call_count,
                                executed_tool_call_count=executed_tool_call_count,
                                citation_repair_count=citation_repair_count,
                                runtime_state=runtime_state,
                                latency_trace=latency_trace,
                                error=exc,
                            )
                        streamed_by_controller = True
                        model_result = ToolCallingChatModelResult(
                            content=streamed.answer,
                            tool_calls=[],
                            provider=self.chat_model_provider.provider_name,
                            model_name=self.chat_model_provider.model_name,
                        )
                    else:
                        latency_trace.set_value("streaming_degraded", True)
                        if not hasattr(self.chat_model_provider, "generate_with_tools"):
                            raise RuntimeError(
                                "chat model provider supports neither streaming nor tool calling"
                            )
                        model_result = self.chat_model_provider.generate_with_tools(
                            messages,
                            tools,
                        )
                else:
                    latency_trace.set_value(
                        "total_model_call_count",
                        int(latency_trace.values["total_model_call_count"]) + 1,
                    )
                    if not hasattr(self.chat_model_provider, "generate_with_tools"):
                        raise RuntimeError(
                            "chat model provider does not support tool calling"
                        )
                    model_result = self.chat_model_provider.generate_with_tools(
                        messages,
                        tools,
                    )
                llm_call_count += 1
                llm_duration_ms = (time.perf_counter() - llm_started) * 1000.0
                if streaming_final_generation and not streamed_by_controller:
                    latency_trace.add_duration("final_generation_latency_ms", llm_duration_ms)
                else:
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
                        preferred_tool_name=(
                            "search_figures" if needs_figure_evidence else None
                        ),
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
                                step_id=tool_call.id,
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
                            publish_tool_call_result(
                                runtime_event_bus,
                                iteration=iteration,
                                record=repeated_record,
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
                                step_id=tool_call.id,
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
                            publish_tool_call_result(
                                runtime_event_bus,
                                iteration=iteration,
                                record=skipped_record,
                            )
                            continue

                        tool_started = time.perf_counter()
                        tool_result = tool_executor.execute(
                            ToolExecutionRequest(
                                call=tool_call,
                                default_query=normalized_question,
                                forbidden_tools=tuple(retrieval_action.forbidden_tools),
                                iteration=iteration,
                            )
                        ).result
                        if tool_result.call.succeeded and tool_result.tool_name in ALLOWED_TOOL_NAMES:
                            latency_trace.set_value(
                                "retrieval_selected_count",
                                len(tool_result.search_results),
                            )
                            latency_trace.set_value(
                                "retrieval_selected_chunk_ids",
                                [item.chunk_id for item in tool_result.search_results],
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
                        checkpoint_repository.persist_state(
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
                        evidence_decision = EvidenceStateMachine(
                            required_tool=retrieval_action.required_tool,
                            result_count=len(sources),
                            rerank_failed=is_reranking_failure(tool_result.call),
                            escalation_count=1,
                            budget=run_budget,
                        ).decide()
                        if evidence_decision.action == "refuse" and is_reranking_failure(
                            tool_result.call
                        ):
                            refusal_reason = tool_result.call.error or tool_result.call.output_summary
                            runtime_state.set_stop_reason("reranking_failed")
                            runtime_state.final_decision = "refuse"
                            apply_runtime_diagnostics(latency_trace, runtime_state)
                            checkpoint_repository.persist_state(
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
                            return outcome_from_tool_calling_loop(
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
                                stop_reason="insufficient_evidence",
                            ).result
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
                            runtime_state.set_stop_reason("figure_evidence_not_found")
                            runtime_state.final_decision = "refuse"
                            apply_runtime_diagnostics(latency_trace, runtime_state)
                            checkpoint_repository.persist_state(
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
                            return outcome_from_tool_calling_loop(
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
                                stop_reason="insufficient_evidence",
                            ).result
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
                            figure_result = tool_executor.execute(
                                ToolExecutionRequest(
                                    call=ChatToolCall(
                                        id=f"{tool_call.id}-figure-fallback",
                                        name="search_figures",
                                        arguments={"query": figure_query},
                                    ),
                                    default_query=figure_query,
                                    iteration=iteration,
                                )
                            ).result
                            if figure_result.call.succeeded:
                                latency_trace.set_value(
                                    "retrieval_selected_count",
                                    len(figure_result.search_results),
                                )
                                latency_trace.set_value(
                                    "retrieval_selected_chunk_ids",
                                    [item.chunk_id for item in figure_result.search_results],
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

                    if (
                        sources
                        and iteration_executed_tool_count == 0
                        and iteration_skipped_tool_count > 0
                    ):
                        generated = FinalAnswerController(
                            self.chat_model_provider,
                            answer_messages=evidence_answer_messages,
                            repair_messages=citation_repair_messages,
                            citation_extractor=extract_citations,
                        ).generate_final_evidence(
                            question=normalized_question,
                            sources=sources,
                            history=history,
                            strategy=self.final_answer_strategy,
                            trace=latency_trace,
                            prompt_budgets={},
                        )
                        llm_call_count += generated.llm_call_count
                        citation_repair_count += generated.citation_repair_count
                        answer_content = generated.answer
                        citations = list(generated.citations)
                        if citations:
                            runtime_state.set_stop_reason("evidence_convergence")
                            runtime_state.final_decision = "answer"
                            apply_runtime_diagnostics(latency_trace, runtime_state)
                            checkpoint_repository.persist_state(
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
                                    step_id="final",
                                )
                            )
                            return outcome_from_tool_calling_loop(
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
                                stop_reason="completed",
                            ).result
                    continue

                if model_result.content.strip():
                    latency_trace.add_duration("answer_latency_ms", llm_duration_ms)
                    answer_content = model_result.content
                    citations: list[int] = []
                    if sources:
                        validated = FinalAnswerController(
                            final_answer_provider,
                            answer_messages=evidence_answer_messages,
                            repair_messages=citation_repair_messages,
                            citation_extractor=extract_citations,
                        ).validate_model_content(
                            question=normalized_question,
                            draft_answer=model_result.content,
                            sources=sources,
                            history=history,
                            strategy=self.final_answer_strategy,
                            trace=latency_trace,
                            prompt_budgets=phase64_final_prompt_budgets(settings),
                        )
                        answer_content = validated.answer
                        citations = list(validated.citations)
                        citation_repair_count += validated.citation_repair_count
                        llm_call_count += validated.llm_call_count
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
                                step_id="final",
                            )
                        )
                        runtime_state.set_stop_reason("final_content_without_citations")
                        runtime_state.final_decision = "refuse"
                        apply_runtime_diagnostics(latency_trace, runtime_state)
                        checkpoint_repository.persist_state(
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
                        return outcome_from_tool_calling_loop(
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
                            stop_reason="insufficient_evidence",
                        ).result

                    runtime_state.set_stop_reason("model_final_answer")
                    runtime_state.final_decision = "answer"
                    apply_runtime_diagnostics(latency_trace, runtime_state)
                    checkpoint_repository.persist_state(
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
                            step_id="final",
                        )
                    )
                    return outcome_from_tool_calling_loop(
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
                        stop_reason="completed",
                    ).result

            refusal_reason = "Tool-calling iteration limit reached."
            runtime_state.set_stop_reason("iteration_limit")
            runtime_state.final_decision = "refuse"
            apply_runtime_diagnostics(latency_trace, runtime_state)
            checkpoint_repository.persist_state(
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
            return outcome_from_tool_calling_loop(
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
                stop_reason="tool_budget_exhausted",
            ).result
        finally:
            if hyde_token is not None:
                reset_current_hyde_vector_query(hyde_token)
            reset_phase64_route_kind(phase64_route_token)
            reset_current_retrieval_plan(retrieval_token)
            reset_current_latency_trace(latency_token)

    def _query_with_run_coordinator(
        self,
        *,
        question: str,
        max_tool_calls: int,
        history: Sequence[str] | None,
        conversation_id: int | None,
        resume_policy: str,
        resume_run_id: str | None,
        image_path: str | None,
        latency_trace: LatencyTrace,
        runtime_event_bus: RuntimeEventBus,
        settings: object,
    ) -> AgentQueryResult:
        max_iterations = min(max_tool_calls, TOOL_CALLING_HARD_MAX_ITERATIONS)
        planning_policy = PlanningPolicy(self.runtime_identity_provider)
        planning_trace_token = set_current_latency_trace(latency_trace)
        try:
            planning = planning_policy.plan(
                PlanningRequest(
                    question=question,
                    history=tuple(history or ()),
                    image_path=image_path,
                    trace=latency_trace,
                )
            )
        finally:
            reset_current_latency_trace(planning_trace_token)
        runtime_state = planning.runtime_state
        early_gate = build_tool_calling_combined_pre_tool_gate_decision(
            question=question,
            runtime_state=runtime_state,
            resume_should_resume=(
                resume_policy != "never"
                and conversation_id is not None
                and is_explicit_continue(question)
            ),
            latency_trace=latency_trace,
            run_pre_tool_gate=True,
            run_resume_gate=False,
            run_semantic_cache_gate=False,
        )
        if early_gate.action == "return":
            log_event(
                agent_logger,
                "refusal_triggered",
                mode="tool_calling_agent",
                refusal_category=early_gate.sanitized_detail,
                source_count=0,
                citation_count=0,
                tool_call_count=0,
            )
            if early_gate.result is None:
                raise RuntimeError("pre-tool gate return decision did not include a result")
            early_gate.result.latency_trace["run_coordinator_enabled"] = True
            early_gate.result.latency_trace["run_coordinator_skip_reason"] = ""
            return early_gate.result
        runtime_repository = AgentRuntimeRunRepository(self.db)
        checkpoint_repository = CheckpointRepository(runtime_repository)
        resume_decision = decide_resume(
            repository=runtime_repository,
            conversation_id=conversation_id,
            question=question,
            history=tuple(history or ()),
            resume_policy=resume_policy,
            resume_run_id=resume_run_id,
        )
        effective_resume_run_id = resume_run_id
        resumed_run = getattr(resume_decision, "run", None)
        if (
            not effective_resume_run_id
            and getattr(resume_decision, "should_resume", False)
            and resumed_run is not None
        ):
            effective_resume_run_id = str(getattr(resumed_run, "run_id", "") or "") or None
        for key, value in runtime_resume_diagnostics(resume_decision).items():
            latency_trace.set_value(key, value)

        def record_resume_completed(run: object) -> None:
            checkpoint_repository.persist_state(
                run,
                node="final_answer_completed",
                state={
                    **load_runtime_state(run),
                    "resume_completed": True,
                },
                status="completed",
            )

        workflow_steps: list[AgentToolCallRecord] = []
        tool_calls: list[AgentToolCallRecord] = []

        def build_service_final_request(
            request: CoordinatorRequest,
            planning: object,
            tool_outcome: object,
            evidence: object,
        ) -> FinalAnswerRequest:
            final_request = build_final_answer_request(
                request,
                planning,
                tool_outcome,
                evidence,
            )
            return replace(
                final_request,
                strategy=self.final_answer_strategy,
                prompt_budgets=phase64_final_prompt_budgets(settings),
            )

        def build_service_hyde_query(
            request: CoordinatorRequest,
            planning: object,
        ) -> str:
            identity = getattr(planning, "identity", None)
            runtime_state = getattr(planning, "runtime_state", None)
            canonical_task = (
                str(getattr(identity, "canonical_query", "") or "").strip()
                or str(getattr(planning, "canonical_task", "") or "").strip()
                or str(
                    getattr(getattr(runtime_state, "context", None), "standalone_task", "")
                    or ""
                ).strip()
                or request.question
            )
            hyde_passage = str(getattr(identity, "hyde_passage", "") or "").strip()
            if hyde_passage:
                request.latency_trace.set_value("hyde_generated", True)
                request.latency_trace.set_value("hyde_used_for_vector", True)
                request.latency_trace.set_value("hyde_reason", "unified_planner")
                request.latency_trace.set_value(
                    "hyde_model",
                    str(getattr(identity, "model_name", "") or ""),
                )
                return (
                    f"{canonical_task}\n\n"
                    "Hypothetical evidence for vector retrieval only:\n"
                    f"{hyde_passage}"
                )
            if getattr(settings, "agent_short_loop_enabled", False):
                request.latency_trace.set_value("hyde_generated", False)
                request.latency_trace.set_value("hyde_used_for_vector", False)
                request.latency_trace.set_value("hyde_reason", "planner_empty")
                return ""
            return generate_hyde_vector_query(
                canonical_task=canonical_task,
                provider=phase64_runtime_identity_provider(
                    self.runtime_identity_provider,
                    settings,
                ),
                latency_trace=request.latency_trace,
            )

        coordinator = RunCoordinator(
            planning_policy=SimpleNamespace(
                plan=lambda *_args, **_kwargs: planning,
                escalate_fast_route=planning_policy.escalate_fast_route,
            ),
            checkpoints=checkpoint_repository,
            tool_executor=ToolExecutor(self.toolbox, event_bus=runtime_event_bus),
            evidence_machine=EvidenceStateMachine,
            final_answers=ToolCallingFinalAnswerFacade(
                chat_model_provider=phase64_final_answer_provider(
                    self.chat_model_provider,
                    settings,
                ),
            ),
            final_request_builder=build_service_final_request,
            pre_tool_gate=ToolCallingCoordinatorGateAdapter(
                run_pre_tool_gate=False,
                run_resume_gate=True,
                run_semantic_cache_gate=True,
                resume_decision=resume_decision,
                chat_model_provider=self.chat_model_provider,
                final_answer_strategy=self.final_answer_strategy,
                settings=settings,
                toolbox=self.toolbox,
                runtime_event_bus=runtime_event_bus,
                workflow_steps=workflow_steps,
                tool_calls=tool_calls,
                resume_completion_recorder=record_resume_completed,
            ),
            post_preflight_gate=ToolCallingCoordinatorGateAdapter(
                run_pre_tool_gate=False,
                run_resume_gate=True,
                run_semantic_cache_gate=True,
                resume_decision=resume_decision,
                chat_model_provider=self.chat_model_provider,
                final_answer_strategy=self.final_answer_strategy,
                settings=settings,
                toolbox=self.toolbox,
                runtime_event_bus=runtime_event_bus,
                workflow_steps=workflow_steps,
                tool_calls=tool_calls,
                resume_completion_recorder=record_resume_completed,
                defer_required_tool_gates=False,
            ),
            hyde_query_builder=build_service_hyde_query,
        )
        token_emitter = getattr(self.chat_model_provider, "emit_stream_token", None)
        if getattr(self.chat_model_provider, "stream_generate_emits_tokens", False):
            token_emitter = None

        result = coordinator.run(
            CoordinatorRequest(
                question=question,
                budget=RunBudget(
                    max_tool_calls=max_tool_calls,
                    max_iterations=max_iterations,
                ),
                history=tuple(history or ()),
                event_sink=cast(Any, runtime_event_bus),
                conversation_id=conversation_id,
                resume_policy=cast(Any, resume_policy),
                resume_run_id=effective_resume_run_id,
                image_path=image_path,
                latency_trace=latency_trace,
                token_emitter=token_emitter,
            )
        )
        if isinstance(result, AgentQueryResult):
            result.latency_trace["run_coordinator_enabled"] = True
            result.latency_trace["run_coordinator_skip_reason"] = ""
        return result

    def _emit(
        self,
        event_sink: InternalToolCallingEventSink | None,
        event: str,
        payload: dict[str, object],
    ) -> None:
        if isinstance(event_sink, RuntimeEventBus):
            event_sink.emit(
                stage="planning" if event == "agent_step" else "retrieval",
                name=cast(RuntimeEventName, event),
                payload=payload,
            )
            return
        trace = get_current_latency_trace()
        if trace is not None:
            trace.mark_progress()
        if event_sink is not None:
            event_sink(ToolCallingRuntimeEvent(event=event, payload=payload))

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
    max_sources: int = TOOL_RESULT_MAX_SOURCES,
    snippet_chars: int = TOOL_RESULT_SNIPPET_LIMIT,
    history_chars: int | None = None,
    prompt_shape: FinalPromptShape | None = None,
    estimated_input_token_budget: int | None = None,
) -> list[ChatMessage]:
    history_summary = bounded_history_summary(history, history_chars)
    strategy_instruction = final_answer_strategy_instruction(final_answer_strategy)
    selected_sources = sources[: max(1, max_sources)]

    def build_messages(snippet_limit: int) -> list[ChatMessage]:
        context_lines = []
        for index, source in enumerate(selected_sources, start=1):
            context_lines.append(
                "\n".join(
                    [
                        f"[{index}] {truncate_text(source.title, 120)}",
                        f"type={source.source_type}; chunk_id={source.chunk_id}",
                        f"snippet={_bounded_prompt_snippet(source.content or '', snippet_limit)}",
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

    effective_snippet_limit = max(1, snippet_chars)
    messages = build_messages(effective_snippet_limit)
    budget_applied = False
    budget = max(0, int(estimated_input_token_budget or 0))
    if budget and selected_sources:
        minimum_messages = build_messages(1)
        if _estimate_final_prompt_tokens(minimum_messages) <= budget:
            budget_applied = True
            if _estimate_final_prompt_tokens(messages) > budget:
                low = 1
                high = effective_snippet_limit
                while low <= high:
                    candidate_limit = (low + high) // 2
                    candidate_messages = build_messages(candidate_limit)
                    if _estimate_final_prompt_tokens(candidate_messages) <= budget:
                        effective_snippet_limit = candidate_limit
                        messages = candidate_messages
                        low = candidate_limit + 1
                    else:
                        high = candidate_limit - 1
    if prompt_shape is not None:
        _record_final_prompt_shape(
            prompt_shape,
            messages=messages,
            source_count=len(selected_sources),
            history_character_count=len(history_summary),
        )
        prompt_shape.budget_applied = budget_applied
    return messages


def _bounded_prompt_snippet(text: str, limit: int) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    if limit < 3:
        return stripped[:limit]
    return truncate_text(stripped, limit)


def _estimate_final_prompt_tokens(messages: Sequence[ChatMessage]) -> int:
    prompt_text = "\n".join(message.content for message in messages)
    cjk_character_count = sum(
        1
        for character in prompt_text
        if "\u3400" <= character <= "\u4dbf"
        or "\u4e00" <= character <= "\u9fff"
        or "\uf900" <= character <= "\ufaff"
    )
    non_cjk_runs = re.findall(
        r"[^\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+",
        prompt_text,
    )
    return cjk_character_count + sum((len(run) + 3) // 4 for run in non_cjk_runs)


def _record_final_prompt_shape(
    prompt_shape: FinalPromptShape,
    *,
    messages: Sequence[ChatMessage],
    source_count: int,
    history_character_count: int,
) -> None:
    prompt_text = "\n".join(message.content for message in messages)
    cjk_character_count = sum(
        1
        for character in prompt_text
        if "\u3400" <= character <= "\u4dbf"
        or "\u4e00" <= character <= "\u9fff"
        or "\uf900" <= character <= "\ufaff"
    )
    prompt_shape.character_count = len(prompt_text)
    prompt_shape.cjk_character_count = cjk_character_count
    prompt_shape.source_count = source_count
    prompt_shape.history_character_count = history_character_count
    prompt_shape.estimated_input_tokens = _estimate_final_prompt_tokens(messages)


def citation_repair_messages(
    question: str,
    *,
    draft_answer: str,
    sources: list[AgentSourceReference],
    history: Sequence[str] | None = None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy = (
        TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY
    ),
    max_sources: int = TOOL_RESULT_MAX_SOURCES,
    snippet_chars: int = TOOL_RESULT_SNIPPET_LIMIT,
    history_chars: int | None = None,
) -> list[ChatMessage]:
    history_summary = bounded_history_summary(history, history_chars)
    strategy_instruction = final_answer_strategy_instruction(final_answer_strategy)
    context_lines = []
    for index, source in enumerate(sources[:max(1, max_sources)], start=1):
        context_lines.append(
            "\n".join(
                [
                    f"[{index}] {truncate_text(source.title, 120)}",
                    f"type={source.source_type}; chunk_id={source.chunk_id}",
                    f"snippet={truncate_text(source.content or '', max(1, snippet_chars))}",
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


def bounded_history_summary(history: Sequence[str] | None, max_chars: int | None) -> str:
    entries = [str(item) for item in (history or ()) if str(item)]
    if max_chars is None:
        return "\n".join(entries) or "(none)"
    remaining = max(0, max_chars)
    selected: list[str] = []
    for entry in reversed(entries):
        separator = 1 if selected else 0
        if remaining <= separator:
            break
        available = remaining - separator
        selected.append(entry[-available:])
        remaining -= min(len(entry), available) + separator
    return "\n".join(reversed(selected)) or "(none)"


def phase64_final_prompt_budgets(settings: Any) -> dict[str, int]:
    if not settings.agent_short_loop_enabled:
        return {}
    return {
        "max_sources": max(1, int(settings.reranking_dynamic_max_results)),
        "snippet_chars": max(1, int(settings.agent_final_snippet_chars)),
        "history_chars": max(0, int(settings.agent_final_history_chars)),
        "estimated_input_token_budget": max(
            0, int(settings.agent_final_estimated_input_token_budget)
        ),
    }


def phase64_final_answer_provider(
    provider: ChatModelProvider,
    settings: Any,
) -> ChatModelProvider:
    """Apply the Phase 64 output cap only to final answer generation."""
    if not settings.agent_short_loop_enabled:
        return provider
    if isinstance(provider, OpenAICompatibleChatModelProvider):
        route_provider = phase64_runtime_identity_provider(provider, settings)
        assert isinstance(route_provider, OpenAICompatibleChatModelProvider)
        return replace(
            route_provider,
            max_tokens=max(1, int(settings.agent_final_max_tokens)),
        )
    return provider


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


def safe_tool_input_summary(tool_call: ChatToolCall) -> str:
    query = tool_call.arguments.get("query", "")
    return f"query={truncate_text(str(query))}"


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
    preferred_tool_name: str | None = None,
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
        key=lambda call: (
            0 if call.name == preferred_tool_name else 1,
            TOOL_CALLING_PREFERRED_TOOL_ORDER.get(call.name, 99),
        )
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


def result_from_final_generation_failure(
    *,
    question: str,
    sources: list[AgentSourceReference],
    search_results: list[AgentSearchItem],
    tool_calls: list[AgentToolCallRecord],
    workflow_steps: list[AgentToolCallRecord],
    llm_call_count: int,
    repeated_query_count: int,
    near_duplicate_query_count: int,
    skipped_tool_call_count: int,
    executed_tool_call_count: int,
    citation_repair_count: int,
    runtime_state: AgentRuntimeState,
    latency_trace: LatencyTrace,
    error: Exception,
) -> AgentQueryResult:
    return build_final_generation_failure_result(
        question=question,
        sources=sources,
        search_results=search_results,
        tool_calls=tool_calls,
        workflow_steps=workflow_steps,
        llm_call_count=llm_call_count,
        repeated_query_count=repeated_query_count,
        near_duplicate_query_count=near_duplicate_query_count,
        skipped_tool_call_count=skipped_tool_call_count,
        executed_tool_call_count=executed_tool_call_count,
        citation_repair_count=citation_repair_count,
        runtime_state=runtime_state,
        latency_trace=latency_trace,
        error=error,
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
    image_analysis: dict[str, object] | None = None,
) -> AgentQueryResult:
    return build_tool_calling_result(
        question=question,
        answer=answer,
        tool_calls=tool_calls,
        sources=sources,
        search_results=search_results,
        citations=citations,
        refused=refused,
        refusal_reason=refusal_reason,
        workflow_steps=workflow_steps,
        llm_call_count=llm_call_count,
        repeated_query_count=repeated_query_count,
        near_duplicate_query_count=near_duplicate_query_count,
        skipped_tool_call_count=skipped_tool_call_count,
        executed_tool_call_count=executed_tool_call_count,
        citation_repair_count=citation_repair_count,
        runtime_state=runtime_state,
        latency_trace=latency_trace,
        image_analysis=image_analysis,
    )


def outcome_from_tool_calling_loop(
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
    stop_reason: RuntimeStopReason,
    image_analysis: dict[str, object] | None = None,
) -> FinalAnswerOutcome:
    result = result_from_tool_calling_loop(
        question=question,
        answer=answer,
        tool_calls=tool_calls,
        workflow_steps=workflow_steps,
        search_results=search_results,
        sources=sources,
        citations=citations,
        refused=refused,
        refusal_reason=refusal_reason,
        llm_call_count=llm_call_count,
        repeated_query_count=repeated_query_count,
        near_duplicate_query_count=near_duplicate_query_count,
        skipped_tool_call_count=skipped_tool_call_count,
        executed_tool_call_count=executed_tool_call_count,
        citation_repair_count=citation_repair_count,
        runtime_state=runtime_state,
        latency_trace=latency_trace,
        image_analysis=image_analysis,
    )
    return FinalAnswerController.outcome_from_result(
        result=result,
        citations=citations,
        citation_repair_count=citation_repair_count,
        stop_reason=stop_reason,
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
    snapshot = CheckpointSnapshot(
        workflow_steps=tuple(tool_call_record_to_dict(item) for item in workflow_steps),
        tool_calls=tuple(tool_call_record_to_dict(item) for item in tool_calls),
        sources=tuple(source_reference_to_dict(item) for item in sources),
        completed_tool_ids=tuple(
            item.step_id for item in tool_calls if item.succeeded and item.step_id
        ),
        safe_trace={
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
    ).to_json_dict()
    return {
        "runtime_context": runtime_state.diagnostics(),
        "workflow_steps": snapshot["workflow_steps"],
        "tool_calls": snapshot["tool_calls"],
        "sources": snapshot["sources"],
        "completed_tool_ids": snapshot["completed_tool_ids"],
        "source_chunk_ids": [
            int(source.chunk_id)
            for source in sources[:50]
            if isinstance(source.chunk_id, int)
        ],
        "latency_trace": snapshot["safe_trace"],
    }


def tool_call_record_to_dict(record: AgentToolCallRecord) -> dict[str, object]:
    return {
        "tool_name": record.tool_name,
        "input_summary": truncate_text(record.input_summary, 160),
        "output_summary": truncate_text(record.output_summary, 180),
        "succeeded": record.succeeded,
        "error": truncate_text(record.error or "", 180) or None,
        "step_id": record.step_id,
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
    return FinalAnswerController(
        chat_model_provider,
        answer_messages=evidence_answer_messages,
        repair_messages=citation_repair_messages,
        citation_extractor=extract_citations,
    ).from_cached_evidence(
        question=question,
        search_results=search_results,
        sources=sources,
        tool_calls=tool_calls,
        workflow_steps=workflow_steps,
        history=history,
        strategy=final_answer_strategy,
        runtime_state=runtime_state,
        latency_trace=latency_trace,
    ).result


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
    return FinalAnswerController(
        chat_model_provider,
        answer_messages=evidence_answer_messages,
        repair_messages=citation_repair_messages,
        citation_extractor=extract_citations,
    ).from_checkpoint(
        question=question,
        sources=sources,
        workflow_steps=workflow_steps,
        history=history,
        strategy=final_answer_strategy,
        runtime_state=runtime_state,
        latency_trace=latency_trace,
    ).result


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
