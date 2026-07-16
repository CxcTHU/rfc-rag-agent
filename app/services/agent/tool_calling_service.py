from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.structured_logging import log_event, safe_text_summary
from app.services.agent.final_prompt import (
    TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY,
    TOOL_RESULT_MAX_SOURCES,
    TOOL_RESULT_SNIPPET_LIMIT,
    FinalPromptShape,
    ToolCallingFinalAnswerStrategy,
    citation_repair_messages,
    evidence_answer_messages,
    final_answer_strategy_instruction,
    phase64_final_answer_provider,
    phase64_final_prompt_budgets,
    tool_calling_messages,
)
from app.services.agent.pre_tool_gates import (
    ToolCallingCoordinatorGateAdapter,
    build_tool_calling_combined_pre_tool_gate_decision,
    build_tool_calling_pre_tool_gate_decision,
    build_tool_calling_resume_gate_decision,
    build_tool_calling_semantic_cache_gate_decision,
    result_from_runtime_checkpoint,
    runtime_checkpoint_state,
)
from app.services.agent.planning_policy import phase64_runtime_identity_provider
from app.services.agent.runtime_events import (
    RuntimeEventBus,
    ToolCallingRuntimeEvent,
    project_tool_calling_event,
)
from app.services.agent.service import AgentQueryResult
from app.services.agent.tool_calling_composition import tool_calling_tool_definitions
from app.services.agent.tool_calling_service_runtime import (
    ToolCallingServiceRuntime,
    compose_tool_calling_service_runtime,
)
from app.services.agent.tool_calling_support import (
    TOOL_CALLING_DEFAULT_MAX_ITERATIONS,
    TOOL_CALLING_HARD_MAX_ITERATIONS,
    TOOL_CALLING_MAX_EXECUTED_TOOLS_PER_ITERATION,
    TOOL_CALLING_NEAR_DUPLICATE_THRESHOLD,
    TOOL_CALLING_PREFERRED_TOOL_ORDER,
    ToolCallingFinalAnswerFacade,
    apply_runtime_diagnostics,
    create_runtime_identity_provider,
    executable_tool_call_ids,
    failed_tool_call_result,
    generate_hyde_vector_query,
    is_near_duplicate_tool_query,
    is_reranking_failure,
    normalize_tool_query,
    optional_float,
    optional_int,
    optional_str,
    outcome_from_tool_calling_loop,
    result_from_cached_evidence,
    result_from_final_generation_failure,
    result_from_tool_calling_loop,
    runtime_refusal_message,
    runtime_refusal_message_for_request,
    safe_sources_payload,
    safe_tool_input_summary,
    safe_tool_result_payload,
    semantic_cache_tool_for_identity,
    skip_reason_for_tool_call,
    skipped_tool_result_payload,
    source_reference_from_dict,
    source_reference_to_dict,
    tokenize_tool_query,
    tool_call_record_to_dict,
    tool_message_from_payload,
    tool_query_from_call,
)
from app.services.agent.tools import AgentToolbox
from app.services.generation.chat_model import ChatModelProvider, create_chat_model_provider
from app.services.observability.latency_trace import (
    LatencyTrace,
    bind_agent_conversation_cache_scope,
    bind_user_question_cache_key,
)
from app.services.retrieval.embedding import EmbeddingProvider


agent_logger = logging.getLogger("rfc_rag_agent.agent")
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
        trace = latency_trace or LatencyTrace()
        bind_user_question_cache_key(trace, normalized_question)
        bind_agent_conversation_cache_scope(
            trace,
            conversation_id,
            evaluation_run_namespace=evaluation_run_namespace,
        )
        runtime_event_bus = RuntimeEventBus(run_id=uuid.uuid4().hex, trace=trace)
        if event_sink is not None:
            runtime_event_bus.subscribe(
                lambda runtime_event: event_sink(project_tool_calling_event(runtime_event))
            )
        runtime = compose_tool_calling_service_runtime(
            db=self.db,
            toolbox=self.toolbox,
            chat_model_provider=self.chat_model_provider,
            runtime_identity_provider=self.runtime_identity_provider,
            final_answer_strategy=self.final_answer_strategy,
            phase64_final_answer_provider_factory=phase64_final_answer_provider,
            question=normalized_question,
            max_tool_calls=max_tool_calls,
            history=history,
            conversation_id=conversation_id,
            resume_policy=resume_policy,
            resume_run_id=resume_run_id,
            image_path=image_path,
            latency_trace=trace,
            runtime_event_bus=runtime_event_bus,
            settings=get_settings(),
        )
        if isinstance(runtime, AgentQueryResult):
            return runtime
        result = runtime.coordinator.run(runtime.request)
        result.latency_trace["run_coordinator_enabled"] = True
        result.latency_trace["run_coordinator_skip_reason"] = ""
        return result

    def _emit(
        self,
        event_sink: ToolCallingEventSink | RuntimeEventBus | None,
        event: str,
        payload: dict[str, object],
    ) -> None:
        if isinstance(event_sink, RuntimeEventBus):
            event_sink.emit(
                stage="planning" if event == "agent_step" else "retrieval",
                name=event,
                payload=payload,
            )  # type: ignore[arg-type]
            return
        if event_sink is not None:
            event_sink(ToolCallingRuntimeEvent(event=event, payload=payload))


__all__ = [
    "TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY",
    "TOOL_CALLING_DEFAULT_MAX_ITERATIONS",
    "TOOL_CALLING_HARD_MAX_ITERATIONS",
    "TOOL_RESULT_MAX_SOURCES",
    "TOOL_RESULT_SNIPPET_LIMIT",
    "FinalPromptShape",
    "ToolCallingAgentService",
    "ToolCallingCoordinatorGateAdapter",
    "ToolCallingEventSink",
    "ToolCallingFinalAnswerFacade",
    "ToolCallingRuntimeEvent",
    "ToolCallingServiceRuntime",
    "apply_runtime_diagnostics",
    "build_tool_calling_combined_pre_tool_gate_decision",
    "build_tool_calling_pre_tool_gate_decision",
    "build_tool_calling_resume_gate_decision",
    "build_tool_calling_semantic_cache_gate_decision",
    "citation_repair_messages",
    "create_chat_model_provider",
    "evidence_answer_messages",
    "executable_tool_call_ids",
    "final_answer_strategy_instruction",
    "phase64_final_answer_provider",
    "phase64_final_prompt_budgets",
    "phase64_runtime_identity_provider",
    "result_from_cached_evidence",
    "result_from_runtime_checkpoint",
    "runtime_checkpoint_state",
    "tool_calling_messages",
    "tool_calling_tool_definitions",
]
