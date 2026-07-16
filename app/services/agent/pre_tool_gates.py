from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from app.services.agent.checkpoint_repository import (
    CheckpointSnapshot,
    load_runtime_state,
)
from app.services.agent.final_answer_controller import FinalAnswerController
from app.services.agent.final_result_assembler import build_pre_tool_refusal_result
from app.services.agent.final_prompt import (
    TOOL_CALLING_DEFAULT_FINAL_ANSWER_STRATEGY,
    TOOL_RESULT_SNIPPET_LIMIT,
    ToolCallingFinalAnswerStrategy,
    citation_repair_messages,
    evidence_answer_messages,
)
from app.services.agent.refusal_explainer import (
    off_topic_refusal_answer,
    responsibility_refusal_answer,
)
from app.services.agent.runtime import AgentRuntimeState
from app.services.agent.runtime_contracts import (
    CoordinatorRequest,
    PreToolGateDecision,
)
from app.services.agent.runtime_events import RuntimeEventBus, publish_tool_call_result
from app.services.agent.tool_models import (
    AgentSourceReference,
    AgentToolCallRecord,
)
from app.services.agent.tools import AgentToolbox, truncate_text
from app.services.brain.workflow import (
    evaluate_responsibility_gate,
    extract_citations,
    has_topic_anchor,
)
from app.services.generation.chat_model import ChatModelProvider
from app.services.observability.latency_trace import LatencyTrace
from app.services.retrieval.runtime import retrieval_runtime_result_limit


def build_tool_calling_pre_tool_gate_decision(
    *,
    question: str,
    runtime_state: AgentRuntimeState,
    resume_should_resume: bool,
    image_path: str | None = None,
    latency_trace: LatencyTrace,
) -> PreToolGateDecision:
    has_uploaded_image = bool(str(image_path or "").strip())
    responsibility_gate = (
        evaluate_responsibility_gate(question)
        if not _uploaded_image_evidence_question_should_reach_image_analysis(
            question,
            has_uploaded_image=has_uploaded_image,
        )
        else None
    )
    if responsibility_gate is not None:
        latency_trace.set_value("pre_tool_gate_responsibility_checked", True)
    else:
        latency_trace.set_value("pre_tool_gate_responsibility_checked", False)
    if responsibility_gate is not None and responsibility_gate.triggered:
        return PreToolGateDecision(
            action="return",
            result=build_pre_tool_refusal_result(
                question=question,
                answer=responsibility_refusal_answer(),
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
    if (
        not resume_should_resume
        and not has_uploaded_image
        and not has_topic_anchor(topic_gate_query)
    ):
        return PreToolGateDecision(
            action="return",
            result=build_pre_tool_refusal_result(
                question=question,
                answer=off_topic_refusal_answer(question),
                refusal_reason="off_topic",
                gate_name="off_topic_gate",
                output_summary="refused=True off_topic_gate",
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


def _uploaded_image_evidence_question_should_reach_image_analysis(
    question: str,
    *,
    has_uploaded_image: bool,
) -> bool:
    if not has_uploaded_image:
        return False
    normalized = str(question or "").casefold()
    image_reference = any(term in normalized for term in ("这张图", "这张图片", "图片", "图像", "image", "photo"))
    evidence_question = any(term in normalized for term in ("支撑", "相关", "相似", "描述", "判断", "可靠"))
    high_risk_decision = any(term in normalized for term in ("开工", "投产", "验收", "是否合格", "符合规范", "用于实际工程"))
    return image_reference and evidence_question and not high_risk_decision


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

    from app.services.agent import tool_calling_service as service

    semantic_cache_tool_name = service.semantic_cache_tool_for_identity(evidence_identity)
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
    service.apply_runtime_diagnostics(latency_trace, runtime_state)
    publish_tool_call_result(
        runtime_event_bus,
        iteration=1,
        record=semantic_cached.call,
        selected_count=len(semantic_cached.search_results),
    )
    result = service.result_from_cached_evidence(
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
    image_path: str | None = None,
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
            image_path=image_path,
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
        missing = [
            name
            for name, value in {
                "settings": settings,
                "evidence_identity": evidence_identity,
                "toolbox": toolbox,
                "chat_model_provider": chat_model_provider,
                "runtime_event_bus": runtime_event_bus,
                "workflow_steps": workflow_steps,
                "tool_calls": tool_calls,
            }.items()
            if value is None
        ]
        if missing:
            raise ValueError(
                "semantic cache gate missing dependencies: " + ", ".join(missing)
            )
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
            image_path=request.image_path,
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


def runtime_checkpoint_state(
    *,
    runtime_state: AgentRuntimeState,
    workflow_steps: list[AgentToolCallRecord],
    tool_calls: list[AgentToolCallRecord],
    sources: list[AgentSourceReference],
    latency_trace: dict[str, object],
) -> dict[str, object]:
    from app.services.agent import tool_calling_service as service

    snapshot = CheckpointSnapshot(
        workflow_steps=tuple(service.tool_call_record_to_dict(item) for item in workflow_steps),
        tool_calls=tuple(service.tool_call_record_to_dict(item) for item in tool_calls),
        sources=tuple(service.source_reference_to_dict(item) for item in sources),
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


def result_from_runtime_checkpoint(
    *,
    question: str,
    run_state: dict[str, object],
    chat_model_provider: ChatModelProvider,
    history: Sequence[str] | None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy,
    runtime_state: AgentRuntimeState,
    latency_trace: LatencyTrace,
):
    from app.services.agent import tool_calling_service as service

    raw_sources = run_state.get("sources", [])
    if not isinstance(raw_sources, list):
        raw_sources = []
    sources = [
        service.source_reference_from_dict(item)
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
            error=service.optional_str(item.get("error")),
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
