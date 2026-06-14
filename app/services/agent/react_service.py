from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import time

from sqlalchemy.orm import Session

from app.services.agent.react_actions import (
    DeterministicReActPlanner,
    ReActAction,
    ReActObservation,
    ReActStepRecord,
    is_repeated_query,
    normalize_react_query,
    observation_from_tool_result,
    parse_react_action_json,
)
from app.services.agent.service import AgentQueryResult
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    AgentToolResult,
    AgentToolbox,
    truncate_text,
)
from app.services.generation.chat_model import ChatMessage, ChatModelProvider
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.embedding import EmbeddingProvider


REACT_DEFAULT_MAX_ITERATIONS = 3
REACT_HARD_MAX_ITERATIONS = 3


@dataclass(frozen=True)
class ReActRuntimeEvent:
    event: str
    payload: dict[str, object]


ReActEventSink = Callable[[ReActRuntimeEvent], None]


class ReActAgentService:
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        chat_model_provider: ChatModelProvider,
        log_answers: bool = True,
        planner_chat_provider: ChatModelProvider | None = None,
    ) -> None:
        self.chat_model_provider = chat_model_provider
        self.planner_chat_provider = planner_chat_provider
        self.toolbox = AgentToolbox(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_model_provider,
            log_answers=log_answers,
        )
        self.deterministic_planner = DeterministicReActPlanner()

    def query(
        self,
        question: str,
        top_k: int = 5,
        max_tool_calls: int = REACT_DEFAULT_MAX_ITERATIONS,
        history: Sequence[str] | None = None,
        event_sink: ReActEventSink | None = None,
    ) -> AgentQueryResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be greater than 0")

        max_iterations = min(max_tool_calls, REACT_HARD_MAX_ITERATIONS)
        observations: list[ReActObservation] = []
        workflow_steps: list[ReActStepRecord] = []
        tool_calls: list[AgentToolCallRecord] = []
        search_results: list[AgentSearchItem] = []
        sources: list[AgentSourceReference] = []
        citations: list[int] = []
        previous_queries: set[str] = set()
        latency_trace = LatencyTrace()
        latency_token = set_current_latency_trace(latency_trace)

        try:
            llm_driven = self.planner_chat_provider is not None
            for iteration in range(1, max_iterations + 1):
                planner_started = time.perf_counter()
                if observations and observations[-1].error:
                    action = ReActAction(
                        action="refuse",
                        refusal_reason="Tool execution failed before reliable evidence was available.",
                        reasoning_summary="Tool error requires safe refusal.",
                    )
                elif (
                    not llm_driven
                    and observations
                    and observations[-1].action == "search_knowledge"
                    and observations[-1].search_result_count > 0
                ):
                    action = ReActAction(
                        action="answer_with_citations",
                        question=normalized_question,
                        reasoning_summary="Retrieved evidence is available; answer with citations.",
                    )
                else:
                    action = self._plan_action(
                        question=normalized_question,
                        observations=observations,
                        previous_queries=previous_queries,
                        history=history,
                        iteration=iteration,
                        max_iterations=max_iterations,
                    )
                latency_trace.add_duration(
                    "planner_latency_ms",
                    (time.perf_counter() - planner_started) * 1000.0,
                )
                self._emit(
                    event_sink,
                    "agent_step",
                    {
                        "iteration": iteration,
                        "action": action.action,
                        "step_summary": action.reasoning_summary,
                    },
                )

                if action.action == "search_knowledge":
                    query = action.query or normalized_question
                    if is_repeated_query(query, previous_queries):
                        observation = ReActObservation(
                            action="search_knowledge",
                            query=query,
                            observation_summary="repeated query skipped",
                            succeeded=False,
                            error="repeated query skipped",
                        )
                        observations.append(observation)
                        workflow_steps.append(step_from_observation(action, observation, iteration))
                        continue

                    previous_queries.add(normalize_react_query(query))
                    self._emit_tool_start(event_sink, action, iteration)
                    tool_started = time.perf_counter()
                    tool_result = self.toolbox.hybrid_search_knowledge(query, top_k=top_k)
                    latency_trace.add_duration(
                        "tool_latency_ms",
                        (time.perf_counter() - tool_started) * 1000.0,
                    )
                    observation = observation_from_tool_result(
                        action=action,
                        tool_result=tool_result,
                    )
                    self._emit_tool_result(event_sink, action, observation, iteration)
                    observations.append(observation)
                    workflow_steps.append(step_from_observation(action, observation, iteration))
                    tool_calls.append(tool_result.call)
                    search_results = merge_search_results(search_results, tool_result.search_results)
                    sources = merge_sources(sources, tool_result.sources)
                    continue

                if action.action == "rewrite_query":
                    observation = ReActObservation(
                        action="rewrite_query",
                        query=action.query,
                        observation_summary=f"rewritten query={truncate_text(action.query or '')}",
                        succeeded=True,
                    )
                    observations.append(observation)
                    workflow_steps.append(step_from_observation(action, observation, iteration))
                    continue

                if action.action == "answer_with_citations":
                    self._emit_tool_start(event_sink, action, iteration)
                    tool_started = time.perf_counter()
                    tool_result = self.toolbox.answer_with_citations(
                        action.question or action.query or normalized_question,
                        top_k=top_k,
                        retrieval_mode="hybrid",
                        history=history,
                    )
                    answer_duration_ms = (time.perf_counter() - tool_started) * 1000.0
                    latency_trace.add_duration("tool_latency_ms", answer_duration_ms)
                    latency_trace.add_duration("answer_latency_ms", answer_duration_ms)
                    observation = observation_from_tool_result(
                        action=action,
                        tool_result=tool_result,
                    )
                    self._emit_tool_result(event_sink, action, observation, iteration)
                    observations.append(observation)
                    workflow_steps.append(step_from_observation(action, observation, iteration))
                    tool_calls.append(tool_result.call)
                    search_results = merge_search_results(search_results, tool_result.search_results)
                    sources = merge_sources(sources, tool_result.sources)
                    citations = unique_ints([*citations, *tool_result.citations])
                    return result_from_react_tool(
                        question=normalized_question,
                        answer=tool_result.answer or "",
                        tool_calls=tool_calls,
                        workflow_steps=workflow_steps,
                        search_results=search_results,
                        sources=sources,
                        citations=citations,
                        refused=tool_result.refused,
                        refusal_reason=tool_result.refusal_reason,
                        latency_trace=latency_trace.finalize(
                            iteration_count=len(workflow_steps),
                            tool_call_count=len(tool_calls),
                        ),
                    )

                if action.action == "refuse":
                    workflow_steps.append(
                        ReActStepRecord(
                            name="refuse",
                            action="refuse",
                            input_summary=action.safe_input_summary(),
                            output_summary=action.refusal_reason or "refused",
                            succeeded=True,
                            iteration=iteration,
                        )
                    )
                    return result_from_react_tool(
                        question=normalized_question,
                        answer=refusal_answer(action.refusal_reason),
                        tool_calls=tool_calls,
                        workflow_steps=workflow_steps,
                        search_results=search_results,
                        sources=sources,
                        citations=citations,
                        refused=True,
                        refusal_reason=action.refusal_reason,
                        latency_trace=latency_trace.finalize(
                            iteration_count=len(workflow_steps),
                            tool_call_count=len(tool_calls),
                        ),
                    )

                if action.action == "final_answer":
                    workflow_steps.append(
                        ReActStepRecord(
                            name="final_answer",
                            action="final_answer",
                            input_summary=action.safe_input_summary(),
                            output_summary=truncate_text(action.answer or action.refusal_reason or ""),
                            succeeded=True,
                            iteration=iteration,
                        )
                    )
                    return result_from_react_tool(
                        question=normalized_question,
                        answer=action.answer or refusal_answer(action.refusal_reason),
                        tool_calls=tool_calls,
                        workflow_steps=workflow_steps,
                        search_results=search_results,
                        sources=sources,
                        citations=citations,
                        refused=bool(action.refusal_reason and not action.answer),
                        refusal_reason=action.refusal_reason,
                        latency_trace=latency_trace.finalize(
                            iteration_count=len(workflow_steps),
                            tool_call_count=len(tool_calls),
                        ),
                    )

            return result_from_react_tool(
                question=normalized_question,
                answer=refusal_answer("ReAct iteration limit reached."),
                tool_calls=tool_calls,
                workflow_steps=workflow_steps,
                search_results=search_results,
                sources=sources,
                citations=citations,
                refused=True,
                refusal_reason="ReAct iteration limit reached.",
                latency_trace=latency_trace.finalize(
                    iteration_count=len(workflow_steps),
                    tool_call_count=len(tool_calls),
                ),
            )
        finally:
            reset_current_latency_trace(latency_token)

    def _plan_action(
        self,
        *,
        question: str,
        observations: list[ReActObservation],
        previous_queries: set[str],
        history: Sequence[str] | None,
        iteration: int = 1,
        max_iterations: int = REACT_HARD_MAX_ITERATIONS,
    ) -> ReActAction:
        planner_provider = self.planner_chat_provider or self.chat_model_provider
        if planner_provider.provider_name == "deterministic":
            return self.deterministic_planner.plan(
                question=question,
                observations=observations,
                previous_queries=previous_queries,
            )

        messages = react_planner_messages(
            question=question,
            observations=observations,
            history=history,
            iteration=iteration,
            max_iterations=max_iterations,
        )
        result = planner_provider.generate(messages)
        try:
            return parse_react_action_json(result.answer, default_query=question)
        except ValueError:
            if observations and any(
                obs.action == "search_knowledge" and obs.search_result_count > 0
                for obs in observations
            ):
                return ReActAction(
                    action="answer_with_citations",
                    question=question,
                    reasoning_summary="Planner output was unparseable; answer with already retrieved evidence.",
                )
            return ReActAction(
                action="refuse",
                refusal_reason="Planner output was unparseable; refusing safely.",
                reasoning_summary="Planner output was unparseable; refuse safely.",
            )

    def _emit(
        self,
        event_sink: ReActEventSink | None,
        event: str,
        payload: dict[str, object],
    ) -> None:
        if event_sink is not None:
            event_sink(ReActRuntimeEvent(event=event, payload=payload))

    def _emit_tool_start(
        self,
        event_sink: ReActEventSink | None,
        action: ReActAction,
        iteration: int,
    ) -> None:
        self._emit(
            event_sink,
            "tool_call_start",
            {
                "iteration": iteration,
                "tool_name": action.action,
                "input_summary": action.safe_input_summary(),
            },
        )

    def _emit_tool_result(
        self,
        event_sink: ReActEventSink | None,
        action: ReActAction,
        observation: ReActObservation,
        iteration: int,
    ) -> None:
        self._emit(
            event_sink,
            "tool_call_result",
            {
                "iteration": iteration,
                "tool_name": action.action,
                "observation_summary": observation.observation_summary,
                "succeeded": observation.succeeded,
            },
        )


def react_planner_messages(
    *,
    question: str,
    observations: list[ReActObservation],
    history: Sequence[str] | None,
    iteration: int = 1,
    max_iterations: int = 3,
) -> list[ChatMessage]:
    observation_lines = [
        f"{idx}. action={obs.action}; query={obs.query or ''}; "
        f"succeeded={obs.succeeded}; result_count={obs.search_result_count}; "
        f"summary={obs.observation_summary}"
        for idx, obs in enumerate(observations, start=1)
    ]
    history_summary = "\n".join(history or []) or "(none)"
    observation_summary = "\n".join(observation_lines) or "(none)"
    return [
        ChatMessage(
            role="system",
            content=(
                "You are a controlled ReAct planner for a rock-filled concrete (RFC) "
                "and hydraulic engineering knowledge base. Return only one JSON object. "
                "Allowed actions: search_knowledge, rewrite_query, "
                "answer_with_citations, refuse, final_answer.\n\n"
                "Decision policy:\n"
                "- DEFAULT: if there are no observations, choose search_knowledge with "
                "  a precise query. Always search first when the topic could plausibly "
                "  appear in concrete/dam/hydraulic engineering material (any mention of "
                "  filling, flowability, self-compacting, rock-filled, RCC, RFC, dam, "
                "  concrete, mix design, thermal control, hydration, durability, etc. — "
                "  in Chinese OR English OR mixed — IS in scope).\n"
                "- Choose refuse on iteration 1 ONLY in these narrow cases: the question "
                "  is unsafe (asks for harmful, illegal, or credential info); the question "
                "  is clearly unrelated to civil/hydraulic engineering (e.g., cooking, "
                "  sports, personal advice); or the question explicitly requests a "
                "  binding engineering judgment, code-compliance ruling, or design "
                "  approval that only a licensed engineer should give.\n"
                "- If the latest search_knowledge returned results (result_count > 0), "
                "  you SHOULD choose answer_with_citations now. Only choose another "
                "  search_knowledge if existing evidence is clearly insufficient AND the "
                "  new query is materially different from previous queries.\n"
                "- If the latest search_knowledge returned 0 results, choose "
                "  rewrite_query once with a more specific query, then search again. "
                "  After a repeated empty search, choose refuse.\n"
                "- Never choose final_answer without going through "
                "  answer_with_citations first; the project requires cited answers.\n"
                "- Do not include hidden thought, raw provider response, or any private "
                "  reasoning content. Use reasoning_summary for a short safe summary "
                "  (one sentence).\n\n"
                "When in doubt, prefer search_knowledge over refuse. Iteration budget "
                "is limited; prefer the fewest necessary tool calls."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Question: {question}\n\n"
                f"History:\n{history_summary}\n\n"
                f"Observations:\n{observation_summary}\n\n"
                f"Current iteration: {iteration} / {max_iterations}"
            ),
        ),
    ]


def step_from_observation(
    action: ReActAction,
    observation: ReActObservation,
    iteration: int,
) -> ReActStepRecord:
    return ReActStepRecord(
        name=action.action,
        action=action.action,
        input_summary=action.safe_input_summary(),
        output_summary=observation.observation_summary,
        succeeded=observation.succeeded,
        iteration=iteration,
        error=observation.error,
    )


def result_from_react_tool(
    *,
    question: str,
    answer: str,
    tool_calls: list[AgentToolCallRecord],
    workflow_steps: list[ReActStepRecord],
    search_results: list[AgentSearchItem],
    sources: list[AgentSourceReference],
    citations: list[int],
    refused: bool,
    refusal_reason: str | None,
    latency_trace: dict[str, object] | None = None,
) -> AgentQueryResult:
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
            f"react_agent iterations={len(workflow_steps)}; "
            f"tool_calls={len(tool_calls)}"
        ),
        mode="react_agent",
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
        latency_trace=latency_trace or {},
    )


def refusal_answer(reason: str | None) -> str:
    return reason or "当前资料库中没有找到足够可靠的依据。"


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


def unique_ints(values: list[int]) -> list[int]:
    unique: list[int] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique
