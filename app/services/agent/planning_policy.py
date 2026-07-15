"""Runtime-owned planning and Route-First policy."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Sequence

from app.core.config import Settings, get_settings
from app.services.agent.evidence_identity import (
    EvidenceQueryIdentity,
    build_evidence_query_identity,
    refine_evidence_query_identity_with_llm,
)
from app.services.agent.route_first import (
    RouteDecision,
    choose_phase64_route,
    enforce_phase64_route_intent_floor,
    record_phase64_route,
)
from app.services.agent.runtime import AgentRuntime, AgentRuntimeState
from app.services.generation.chat_model import (
    ChatModelProvider,
    OpenAICompatibleChatModelProvider,
    is_deepseek_endpoint,
)
from app.services.observability.latency_trace import LatencyTrace
from app.services.retrieval.runtime import (
    RetrievalAction,
    RetrievalPlan,
    build_retrieval_action,
    build_retrieval_plan,
)


@dataclass(frozen=True)
class PlanningRequest:
    question: str
    history: tuple[str, ...]
    image_path: str | None
    trace: LatencyTrace


@dataclass(frozen=True)
class PlanningDecision:
    runtime_state: AgentRuntimeState
    identity: EvidenceQueryIdentity
    route: RouteDecision | None
    plan: RetrievalPlan | None
    action: RetrievalAction
    canonical_task: str
    used_fallback: bool
    escalation_count: int
    planner_call_count: int
    fast_path_min_selected_sources: int = 1


class PlanningPolicy:
    def __init__(
        self,
        identity_provider: ChatModelProvider | None,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._identity_provider = identity_provider
        self._settings = settings

    def plan(self, request: PlanningRequest) -> PlanningDecision:
        settings = self._settings or get_settings()
        with request.trace.span("context_assembly_latency_ms"):
            runtime = AgentRuntime()
            runtime_state = runtime.assemble(request.question, history=request.history)
        identity = build_evidence_query_identity(
            runtime_state.context.standalone_task or request.question,
            history=request.history,
        )
        identity_provider = phase64_runtime_identity_provider(
            self._identity_provider,
            settings,
        )
        route: RouteDecision | None = None
        route_first_enabled = (
            settings.agent_short_loop_enabled and settings.phase64_route_first_enabled
        )
        if route_first_enabled:
            route_started = time.perf_counter()
            route = choose_phase64_route(
                request.question,
                history=request.history,
                has_uploaded_image=bool(request.image_path),
            )
            record_phase64_route(
                request.trace,
                route,
                elapsed_ms=(time.perf_counter() - route_started) * 1000.0,
            )
            request.trace.set_value(
                "phase64_execution_graph",
                "phase64_fast" if route.kind == "fast" else "phase64_complex",
            )
            if route.kind == "complex":
                identity = refine_evidence_query_identity_with_llm(
                    runtime_state.context.standalone_task or request.question,
                    base_identity=identity,
                    provider=identity_provider,
                    history=request.history,
                    force=True,
                    trace=request.trace,
                )
        else:
            identity = refine_evidence_query_identity_with_llm(
                runtime_state.context.standalone_task or request.question,
                base_identity=identity,
                provider=identity_provider,
                history=request.history,
                force=settings.agent_short_loop_enabled,
                trace=request.trace,
            )
            request.trace.set_value(
                "phase64_execution_graph",
                "phase64_complex" if settings.agent_short_loop_enabled else "phase63_a",
            )

        if route is not None:
            identity = replace(
                identity,
                retrieval_intent=enforce_phase64_route_intent_floor(
                    identity.retrieval_intent,
                    route,
                ),
            )
        canonical_task = (
            identity.canonical_query or runtime_state.context.standalone_task or request.question
        )
        retrieval_plan = (
            build_retrieval_plan(identity.retrieval_intent, canonical_task, settings)
            if settings.retrieval_runtime_enabled
            else None
        )
        action = build_retrieval_action(identity.retrieval_intent)
        if identity.safe_for_cache_reuse and identity.canonical_query:
            runtime_state.context = replace(
                runtime_state.context,
                standalone_task=identity.canonical_query,
                contextualized=True,
                contextualization_source=identity.source,
            )
        apply_evidence_identity_diagnostics(request.trace, identity)
        if retrieval_plan is not None:
            for key, value in retrieval_plan.diagnostics().items():
                request.trace.set_value(key, value)
            plan_fallback = retrieval_plan.intent_source != "llm"
            request.trace.set_value("retrieval_plan_fallback", plan_fallback)
            request.trace.set_value(
                "retrieval_plan_fallback_reason",
                identity.reason if plan_fallback else "",
            )
        else:
            request.trace.set_value("retrieval_runtime_mode", "legacy")
            request.trace.set_value("retrieval_plan_digest", "legacy")
        request.trace.set_value("retrieval_required_tool", action.required_tool or "")
        request.trace.set_value("retrieval_forbidden_tools", list(action.forbidden_tools))
        request.trace.set_value("retrieval_action_reason", action.reason)
        request.trace.set_value("canonical_task", canonical_task)
        planner_call_count = int(request.trace.values.get("planner_call_count", 0))
        request.trace.set_value("total_model_call_count", planner_call_count)
        return PlanningDecision(
            runtime_state=runtime_state,
            identity=identity,
            route=route,
            plan=retrieval_plan,
            action=action,
            canonical_task=canonical_task,
            used_fallback=planner_call_count > 0 and identity.source != "llm",
            escalation_count=0,
            planner_call_count=planner_call_count,
            fast_path_min_selected_sources=max(
                1, int(settings.phase64_fast_path_min_selected_sources)
            ),
        )

    def escalate_fast_route(
        self,
        request: PlanningRequest,
        decision: PlanningDecision,
    ) -> PlanningDecision:
        """Spend the one permitted fast-path escalation on identity refinement."""
        if (
            decision.route is None
            or decision.route.kind != "fast"
            or decision.escalation_count >= 1
        ):
            return decision
        settings = self._settings or get_settings()
        identity = refine_evidence_query_identity_with_llm(
            decision.runtime_state.context.standalone_task or request.question,
            base_identity=decision.identity,
            provider=phase64_runtime_identity_provider(self._identity_provider, settings),
            history=request.history,
            force=True,
            trace=request.trace,
        )
        canonical_task = (
            identity.canonical_query
            or decision.runtime_state.context.standalone_task
            or request.question
        )
        retrieval_plan = (
            build_retrieval_plan(identity.retrieval_intent, canonical_task, settings)
            if settings.retrieval_runtime_enabled
            else None
        )
        action = build_retrieval_action(identity.retrieval_intent)
        request.trace.set_value("phase64_execution_graph", "phase64_complex")
        request.trace.set_value(
            "total_model_call_count",
            int(request.trace.values.get("planner_call_count", 0)),
        )
        return replace(
            decision,
            identity=identity,
            plan=retrieval_plan,
            action=action,
            canonical_task=canonical_task,
            used_fallback=(
                int(request.trace.values.get("planner_call_count", 0)) > 0
                and identity.source != "llm"
            ),
            escalation_count=1,
            planner_call_count=int(request.trace.values.get("planner_call_count", 0)),
        )


def apply_evidence_identity_diagnostics(
    trace: LatencyTrace,
    identity: EvidenceQueryIdentity,
) -> None:
    for key, value in identity.diagnostics().items():
        trace.set_value(key, value)


def phase64_runtime_identity_provider(
    provider: ChatModelProvider | None,
    settings: Settings,
) -> ChatModelProvider | None:
    """Use DeepSeek non-thinking mode for Route-First structured planning."""
    if not isinstance(provider, OpenAICompatibleChatModelProvider):
        return provider
    if not (
        settings.agent_short_loop_enabled
        and settings.phase64_route_first_enabled
        and settings.phase64_final_non_thinking_enabled
        and is_deepseek_endpoint(provider.base_url)
        and provider.model_name.strip().casefold().startswith("deepseek-v4")
    ):
        return provider
    extra_body = dict(provider.extra_body)
    extra_body["thinking"] = {"type": "disabled"}
    return replace(provider, extra_body=extra_body)
