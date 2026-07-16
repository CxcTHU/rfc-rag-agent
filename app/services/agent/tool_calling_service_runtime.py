from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any, cast

from sqlalchemy.orm import Session

from app.services.agent.checkpoint_repository import (
    AgentRuntimeRunRepository,
    CheckpointRepository,
    decide_resume,
    is_explicit_continue,
    load_runtime_state,
    runtime_resume_diagnostics,
)
from app.services.agent.evidence_state_machine import EvidenceStateMachine
from app.services.agent.final_prompt import (
    ToolCallingFinalAnswerStrategy,
    phase64_final_prompt_budgets,
)
from app.services.agent.planning_policy import PlanningPolicy, PlanningRequest
from app.services.agent.pre_tool_gates import (
    ToolCallingCoordinatorGateAdapter,
    build_tool_calling_combined_pre_tool_gate_decision,
)
from app.services.agent.run_coordinator import RunCoordinator, build_final_answer_request
from app.services.agent.runtime_contracts import CoordinatorRequest, FinalAnswerRequest, RunBudget
from app.services.agent.runtime_events import RuntimeEventBus
from app.services.agent.service import AgentQueryResult
from app.services.agent.tool_calling_support import (
    TOOL_CALLING_HARD_MAX_ITERATIONS,
    ToolCallingFinalAnswerFacade,
    agent_logger,
    generate_hyde_vector_query,
)
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.tools import AgentToolCallRecord, AgentToolbox
from app.services.generation.chat_model import ChatModelProvider
from app.services.observability.latency_trace import LatencyTrace, set_current_latency_trace, reset_current_latency_trace
from app.core.structured_logging import log_event
from app.services.agent.planning_policy import phase64_runtime_identity_provider


Phase64FinalAnswerProviderFactory = Callable[[ChatModelProvider, object], ChatModelProvider]


@dataclass(frozen=True)
class ToolCallingServiceRuntime:
    coordinator: RunCoordinator
    request: CoordinatorRequest


def compose_tool_calling_service_runtime(
    *,
    db: Session,
    toolbox: AgentToolbox,
    chat_model_provider: ChatModelProvider,
    runtime_identity_provider: ChatModelProvider | None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy,
    phase64_final_answer_provider_factory: Phase64FinalAnswerProviderFactory,
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
) -> ToolCallingServiceRuntime | AgentQueryResult:
    max_iterations = min(max_tool_calls, TOOL_CALLING_HARD_MAX_ITERATIONS)
    planning_policy = PlanningPolicy(runtime_identity_provider)
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
        image_path=image_path,
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

    runtime_repository = AgentRuntimeRunRepository(db)
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
            strategy=final_answer_strategy,
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
                runtime_identity_provider,
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
        tool_executor=ToolExecutor.for_toolbox(toolbox, event_bus=runtime_event_bus),
        evidence_machine=EvidenceStateMachine,
        final_answers=ToolCallingFinalAnswerFacade(
            chat_model_provider=phase64_final_answer_provider_factory(
                chat_model_provider,
                settings,
            ),
        ),
        final_request_builder=build_service_final_request,
        pre_tool_gate=ToolCallingCoordinatorGateAdapter(
            run_pre_tool_gate=False,
            run_resume_gate=True,
            run_semantic_cache_gate=True,
            resume_decision=resume_decision,
            chat_model_provider=chat_model_provider,
            final_answer_strategy=final_answer_strategy,
            settings=settings,
            toolbox=toolbox,
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
            chat_model_provider=chat_model_provider,
            final_answer_strategy=final_answer_strategy,
            settings=settings,
            toolbox=toolbox,
            runtime_event_bus=runtime_event_bus,
            workflow_steps=workflow_steps,
            tool_calls=tool_calls,
            resume_completion_recorder=record_resume_completed,
            defer_required_tool_gates=False,
        ),
        hyde_query_builder=build_service_hyde_query,
    )
    token_emitter = getattr(chat_model_provider, "emit_stream_token", None)
    if getattr(chat_model_provider, "stream_generate_emits_tokens", False):
        token_emitter = None

    request = CoordinatorRequest(
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
    return ToolCallingServiceRuntime(coordinator=coordinator, request=request)
