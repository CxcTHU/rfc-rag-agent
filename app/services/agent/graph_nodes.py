from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from dataclasses import asdict, is_dataclass
from typing import Any

from app.services.agent.graph_state import LangGraphAgentState, LangGraphAgentRoute
from app.services.agent.memory_context import (
    AgentMemoryContext,
    agent_memory_context_from_state,
    augment_query_with_agent_memory,
    build_agent_memory_context,
    should_use_prior_evidence_for_answer,
)
from app.services.agent.react_actions import (
    DeterministicReActPlanner,
    READ_ONLY_REACT_ACTIONS,
    ReActAction,
    ReActObservation,
    ReActStepRecord,
    is_repeated_query,
    normalize_react_query,
    observation_from_tool_result,
    parse_react_action_json,
)
from app.services.agent.react_service import (
    ReActEventSink,
    ReActRuntimeEvent,
    merge_search_results,
    merge_sources,
    refusal_answer,
    unique_ints,
)
from app.services.agent.tools import AgentToolResult, AgentToolbox, truncate_text
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
)
from app.services.agent.tool_calling_service import (
    citation_repair_messages,
    evidence_answer_messages,
)
from app.services.brain.workflow import (
    RESPONSIBILITY_REFUSAL_ANSWER,
    evaluate_responsibility_gate,
    extract_citations,
    has_topic_anchor,
)
from app.services.generation.chat_model import ChatMessage, ChatModelProvider
from app.services.observability.latency_trace import (
    get_current_latency_trace,
    latency_timer,
)


_CURRENT_TOOLBOX: ContextVar[AgentToolbox | None] = ContextVar(
    "langgraph_agent_toolbox",
    default=None,
)
_CURRENT_EVENT_SINK: ContextVar[ReActEventSink | None] = ContextVar(
    "langgraph_agent_event_sink",
    default=None,
)
_CURRENT_PLANNER_PROVIDER: ContextVar[ChatModelProvider | None] = ContextVar(
    "langgraph_agent_planner_provider",
    default=None,
)

logger = logging.getLogger(__name__)


def initialize_state(
    *,
    question: str,
    top_k: int = 5,
    max_iterations: int = 3,
    source_id: str | None = None,
    history: list[str] | None = None,
    image_path: str | None = None,
    toolbox: AgentToolbox | None = None,
) -> LangGraphAgentState:
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be greater than 0")
    state: LangGraphAgentState = {
        "question": normalized_question,
        "normalized_question": normalized_question,
        "history": [item.strip() for item in (history or []) if item.strip()],
        "top_k": top_k,
        "source_id": source_id,
        "max_iterations": min(max_iterations, 3),
        "iteration_count": 0,
        "previous_queries": [],
        "observations": [],
        "workflow_steps": [],
        "tool_calls": [],
        "search_results": [],
        "sources": [],
        "citations": [],
        "prior_sources": [],
        "prior_citations": [],
        "prior_answer_summary": "",
        "memory_context": {},
        "image_path": image_path,
        "image_analysis": None,
        "answer": "",
        "refused": False,
        "refusal_reason": None,
    }
    if toolbox is not None:
        state["_toolbox"] = toolbox
    return state


def memory_context_for_state(
    state: LangGraphAgentState,
    question: str,
) -> AgentMemoryContext:
    memory_context = agent_memory_context_from_state(state.get("memory_context"))
    if memory_context.has_memory or not state.get("prior_sources"):
        return memory_context
    return build_agent_memory_context(
        question=question,
        history=list(state.get("history", [])),
        prior_evidence={
            "prior_sources": state.get("prior_sources", []),
            "prior_citations": state.get("prior_citations", []),
            "prior_answer_summary": state.get("prior_answer_summary", ""),
        },
    )


def planner_node(state: LangGraphAgentState) -> dict[str, Any]:
    question = _question(state)
    observations = deserialize_observations(state.get("observations", []))
    memory_context = memory_context_for_state(state, question)
    prior_sources = deserialize_prior_source_references(
        list(memory_context.prior_evidence.sources) or state.get("prior_sources", [])
    )
    iteration = int(state.get("iteration_count", 0)) + 1
    max_iterations = int(state.get("max_iterations", 3))
    last_observation = observations[-1] if observations else None

    if state.get("image_path") and not observations:
        _record_planner_model("deterministic")
        action = ReActAction(
            action="analyze_user_image",
            image_path=state.get("image_path"),
            question=question,
            reasoning_summary="A user-uploaded image is attached; analyze it before answering.",
        )
    elif last_observation and last_observation.action == "search_knowledge" and last_observation.search_result_count > 0:
        _record_planner_model("deterministic")
        action = ReActAction(
            action="answer_with_citations",
            question=question,
            reasoning_summary="Retrieved evidence is available; answer with citations.",
        )
    elif last_observation and last_observation.action == "search_figures":
        _record_planner_model("deterministic")
        action = ReActAction(
            action="answer_with_citations",
            question=question,
            reasoning_summary="Figure evidence search is complete; answer with citations.",
        )
    elif last_observation and last_observation.action == "search_tables" and last_observation.search_result_count > 0:
        _record_planner_model("deterministic")
        action = ReActAction(
            action="answer_with_citations",
            question=question,
            reasoning_summary="Table evidence is available; answer with citations.",
        )
    elif iteration > max_iterations:
        return {
            "next_action": "refuse",
            "current_query": question,
            "iteration_count": iteration,
            "refusal_reason": "LangGraph Agent iteration limit reached.",
        }
    elif last_observation and last_observation.action == "search_tables" and last_observation.search_result_count == 0:
        _record_planner_model("deterministic")
        action = ReActAction(
            action="rewrite_query",
            query=f"{question} table data",
            reasoning_summary="No table evidence was found; rewrite the query once.",
        )
    elif not observations and query_requests_table(question):
        _record_planner_model("deterministic")
        action = ReActAction(
            action="search_tables",
            query=question,
            reasoning_summary="The question asks for tabulated evidence; search table chunks first.",
        )
    else:
        action = _plan_route_action(
            question=question,
            observations=observations,
            previous_queries=set(state.get("previous_queries", [])),
            prior_sources=prior_sources,
            prior_answer_summary=(
                memory_context.prior_evidence.answer_summary
                or state.get("prior_answer_summary", "")
            ),
            memory_context=memory_context,
        )

    _emit(
        "agent_step",
        {
            "iteration": iteration,
            "action": "llm_with_tools",
            "step_summary": f"Selected {action.action}: {action.reasoning_summary}",
        },
    )
    planner_step = ReActStepRecord(
        name="llm_with_tools",
        action=action.action,
        input_summary=f"question={truncate_text(question)}",
        output_summary=f"selected action={action.action}",
        succeeded=True,
        iteration=iteration,
    )
    return {
        "next_action": action.action,
        "current_query": action.query or action.question or question,
        "iteration_count": iteration,
        "workflow_steps": [*state.get("workflow_steps", []), serialize_step(planner_step)],
    }


def _plan_route_action(
    *,
    question: str,
    observations: list[ReActObservation],
    previous_queries: set[str],
    prior_sources: list[AgentSourceReference] | None = None,
    prior_answer_summary: str = "",
    memory_context: AgentMemoryContext | None = None,
) -> ReActAction:
    planner_provider = _CURRENT_PLANNER_PROVIDER.get()
    if planner_provider is not None:
        try:
            with latency_timer("planner_latency_ms"):
                result = planner_provider.generate(
                    build_planner_messages(
                        question=question,
                        observations=observations,
                        prior_sources=prior_sources or [],
                        prior_answer_summary=prior_answer_summary,
                        memory_context=memory_context,
                    )
                )
            _record_planner_model(f"{result.provider}/{result.model_name}")
            return parse_planner_action(result.answer, question=question)
        except Exception as exc:  # noqa: BLE001 - planner fallback must be broad.
            logger.warning(
                "langgraph_planner_fallback",
                extra={"fallback_reason": type(exc).__name__},
            )
            _record_planner_model("deterministic", overwrite=True)
            return DeterministicReActPlanner().plan(
                question=question,
                observations=observations,
                previous_queries=previous_queries,
                prior_source_count=usable_prior_source_count(
                    prior_sources or [],
                    memory_context,
                ),
                expand_followup=should_plan_from_prior_evidence(
                    question,
                    memory_context,
                ),
                stale_anchor_count=memory_stale_anchor_count(memory_context),
            )
    _record_planner_model("deterministic")
    return DeterministicReActPlanner().plan(
        question=question,
        observations=observations,
        previous_queries=previous_queries,
        prior_source_count=usable_prior_source_count(prior_sources or [], memory_context),
        expand_followup=should_plan_from_prior_evidence(question, memory_context),
        stale_anchor_count=memory_stale_anchor_count(memory_context),
    )


def build_planner_messages(
    *,
    question: str,
    observations: list[ReActObservation],
    prior_sources: list[AgentSourceReference] | None = None,
    prior_answer_summary: str = "",
    memory_context: AgentMemoryContext | None = None,
) -> list[ChatMessage]:
    tool_lines = "\n".join(
        f"- {name}: {description}"
        for name, description in PLANNER_TOOL_DESCRIPTIONS.items()
        if name in READ_ONLY_REACT_ACTIONS
    )
    observation_summary = summarize_observations_for_planner(observations)
    prior_evidence_summary = summarize_prior_sources_for_planner(prior_sources or [])
    memory_summary = summarize_memory_context_for_planner(memory_context)
    prior_answer_summary = truncate_text(prior_answer_summary, 200) if prior_answer_summary else "(none)"
    system_prompt = (
        "You route one RAG agent step. Choose exactly one allowed action. "
        "Return only compact JSON with keys action, query, and reasoning_summary. "
        "Do not include markdown, hidden reasoning, credentials, or raw provider data."
    )
    user_prompt = (
        f"Allowed actions:\n{tool_lines}\n\n"
        f"Current question:\n{question}\n\n"
        f"Prior answer summary:\n{prior_answer_summary}\n\n"
        f"Prior evidence from the same conversation:\n{prior_evidence_summary}\n\n"
        f"Short-term memory trace:\n{memory_summary}\n\n"
        f"Recent observations:\n{observation_summary}\n\n"
        'Return JSON like {"action":"search_knowledge","query":"...","reasoning_summary":"..."}'
    )
    return [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]


def summarize_observations_for_planner(observations: list[ReActObservation]) -> str:
    if not observations:
        return "none"
    lines: list[str] = []
    for observation in observations[-3:]:
        lines.append(
            (
                f"- action={observation.action}; "
                f"succeeded={observation.succeeded}; "
                f"results={observation.search_result_count}; "
                f"summary={truncate_text(observation.observation_summary, limit=160)}"
            )
        )
    return "\n".join(lines)


def summarize_prior_sources_for_planner(sources: list[AgentSourceReference]) -> str:
    if not sources:
        return "(none)"
    lines: list[str] = []
    for index, source in enumerate(sources[:5], start=1):
        title = source.title or source.source_id
        snippet = truncate_text(source.content or source.table_content or "", limit=160)
        lines.append(
            f"[{index}] title={truncate_text(title, 80)}; "
            f"source_id={source.source_id}; snippet={snippet}"
        )
    return "\n".join(lines)


def summarize_memory_context_for_planner(memory_context: AgentMemoryContext | None) -> str:
    if memory_context is None:
        return "(none)"
    session = memory_context.session
    parts = [
        f"decision_hint={memory_context.decision_hint}",
        f"policy_route={memory_context.policy.planner_route}",
        f"intent={memory_context.intent.label}",
        f"prior_relevance={memory_context.prior_relevance.score:.3f}/{memory_context.prior_relevance.passed}",
        f"entities={';'.join(item.text for item in session.entities[:5]) or '(none)'}",
        f"retrieval_anchors={';'.join(item.text for item in session.retrieval_anchors[:8]) or '(none)'}",
        f"stale_anchors={';'.join(item.text for item in session.stale_anchors[:8]) or '(none)'}",
    ]
    return " | ".join(parts)


def should_plan_from_prior_evidence(
    question: str,
    memory_context: AgentMemoryContext | None,
) -> bool:
    if memory_context is not None:
        return (
            memory_context.intent.label == "expand_followup"
            and memory_context.policy.use_prior_evidence_for_answer
        )
    return is_expand_followup_question(question)


def usable_prior_source_count(
    prior_sources: list[AgentSourceReference],
    memory_context: AgentMemoryContext | None,
) -> int:
    if memory_context is not None and not memory_context.policy.use_prior_evidence_for_answer:
        return 0
    return len(prior_sources)


def memory_stale_anchor_count(memory_context: AgentMemoryContext | None) -> int:
    if memory_context is None:
        return 0
    return len(memory_context.session.stale_anchors)


def parse_planner_action(payload: str, *, question: str) -> ReActAction:
    decoded = decode_planner_json(payload)
    action_name = decoded.get("action") or decoded.get("next_action")
    if action_name in {"search_knowledge", "search_figures", "search_tables", "rewrite_query"}:
        decoded.setdefault("query", question)
    if action_name == "answer_with_citations":
        decoded.setdefault("question", question)
    if action_name == "refuse":
        decoded.setdefault(
            "refusal_reason",
            "The planner could not select a reliable evidence-backed action.",
        )
    decoded.setdefault("reasoning_summary", "Planner selected the next action.")
    return parse_react_action_json(decoded, default_query=question)


def decode_planner_json(payload: str) -> dict[str, Any]:
    stripped = payload.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.casefold().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("planner response did not contain a JSON object")
        decoded = json.loads(stripped[start : end + 1])
    if not isinstance(decoded, dict):
        raise ValueError("planner response must be a JSON object")
    return decoded


def _record_planner_model(value: str, *, overwrite: bool = False) -> None:
    trace = get_current_latency_trace()
    if trace is not None:
        if not overwrite and value == "deterministic" and trace.values.get("planner_model") != "deterministic":
            return
        trace.set_value("planner_model", value)


PLANNER_TOOL_DESCRIPTIONS: dict[str, str] = {
    "search_knowledge": "Search the text knowledge base for RFC concepts, causes, mechanisms, or general evidence.",
    "search_figures": "Search figure or image evidence when the user explicitly asks for pictures, diagrams, cracks, curves, or visual examples.",
    "search_tables": "Search table chunks when the user asks for tabulated parameters, mix ratios, rows, columns, or numeric table data.",
    "analyze_user_image": "Analyze a user-uploaded image. Only choose this when an image path is already attached.",
    "rewrite_query": "Rewrite the query after a failed search before retrying knowledge search.",
    "answer_with_citations": "Generate a cited answer after useful evidence has already been observed.",
    "refuse": "Refuse when tool errors or insufficient evidence make a reliable answer impossible.",
}


def search_knowledge_node(state: LangGraphAgentState) -> dict[str, Any]:
    memory_context = memory_context_for_state(state, _question(state))
    query = augment_query_with_agent_memory(_current_query(state), memory_context)
    previous_queries = set(state.get("previous_queries", []))
    if is_repeated_query(query, previous_queries):
        action = ReActAction(
            action="search_knowledge",
            query=query,
            reasoning_summary="Repeated query skipped.",
        )
        observation = ReActObservation(
            action="search_knowledge",
            query=query,
            observation_summary="repeated query skipped",
            succeeded=False,
            error="repeated query skipped",
        )
        return _append_observation(state, action, observation)

    previous_queries.add(normalize_react_query(query))
    action = ReActAction(
        action="search_knowledge",
        query=query,
        reasoning_summary="Search knowledge through AgentToolbox.",
    )
    iteration = int(state.get("iteration_count", 1))
    event_sink = _CURRENT_EVENT_SINK.get()

    def emit_progress(summary: str) -> None:
        if event_sink is not None:
            event_sink(
                ReActRuntimeEvent(
                    event="agent_step",
                    payload={
                        "iteration": iteration,
                        "action": "search_progress",
                        "step_summary": summary,
                    },
                )
            )

    _emit_tool_start(action, iteration)
    tool_result = _toolbox(state).hybrid_search_knowledge(
        query,
        top_k=int(state.get("top_k", 5)),
        progress_callback=emit_progress,
    )
    updates = _append_tool_result(state, action, tool_result)
    updates["previous_queries"] = sorted(previous_queries)
    return updates


def search_figures_node(state: LangGraphAgentState) -> dict[str, Any]:
    query = _current_query(state)
    action = ReActAction(
        action="search_figures",
        query=query,
        reasoning_summary="Search figure evidence through AgentToolbox.",
    )
    _emit_tool_start(action, int(state.get("iteration_count", 1)))
    tool_result = _toolbox(state).search_figures(
        query,
        top_k=min(int(state.get("top_k", 5)), 4),
    )
    return _append_tool_result(state, action, tool_result)


def search_tables_node(state: LangGraphAgentState) -> dict[str, Any]:
    query = _current_query(state)
    action = ReActAction(
        action="search_tables",
        query=query,
        reasoning_summary="Search table evidence through AgentToolbox.",
    )
    _emit_tool_start(action, int(state.get("iteration_count", 1)))
    tool_result = _toolbox(state).search_tables(
        query,
        top_k=int(state.get("top_k", 5)),
    )
    return _append_tool_result(state, action, tool_result)


def analyze_image_node(state: LangGraphAgentState) -> dict[str, Any]:
    image_path = state.get("image_path")
    action = ReActAction(
        action="analyze_user_image",
        image_path=image_path,
        question=_question(state),
        reasoning_summary="Analyze the user-uploaded image through AgentToolbox.",
    )
    _emit_tool_start(action, int(state.get("iteration_count", 1)))
    tool_result = _toolbox(state).analyze_user_image(
        image_path or "",
        _question(state),
        top_k=int(state.get("top_k", 5)),
    )
    updates = _append_tool_result(state, action, tool_result)
    updates["image_analysis"] = tool_result.image_analysis
    if tool_result.answer:
        updates["answer"] = tool_result.answer
    return updates


def rewrite_query_node(state: LangGraphAgentState) -> dict[str, Any]:
    query = _current_query(state)
    action = ReActAction(
        action="rewrite_query",
        query=query,
        reasoning_summary="Rewrite the query once before retrying search.",
    )
    observation = ReActObservation(
        action="rewrite_query",
        query=query,
        observation_summary=f"rewritten query={truncate_text(query)}",
        succeeded=True,
    )
    return _append_observation(state, action, observation)


def generate_answer_node(state: LangGraphAgentState) -> dict[str, Any]:
    question = _question(state)
    action = ReActAction(
        action="answer_with_citations",
        question=question,
        reasoning_summary="Generate a cited answer from existing LangGraph evidence.",
    )
    memory_context = memory_context_for_state(state, question)
    sources = deserialize_source_references(state.get("sources", []))
    prior_sources = deserialize_prior_source_references(
        list(memory_context.prior_evidence.sources) or state.get("prior_sources", [])
    )
    if not should_use_prior_evidence_for_answer(memory_context, question):
        prior_sources = []
    answer_sources = sources or prior_sources
    evidence_count = len(state.get("search_results", [])) or len(sources) or len(prior_sources)
    source_count = len(answer_sources)
    citation_count = len(state.get("citations", []))
    _emit_answer_progress(
        iteration=int(state.get("iteration_count", 1)),
        summary=f"正在基于 {evidence_count} 条证据组织回答",
    )
    _emit_answer_progress(
        iteration=int(state.get("iteration_count", 1)),
        summary=f"已找到 {source_count} 个相关来源",
    )
    _emit_answer_progress(
        iteration=int(state.get("iteration_count", 1)),
        summary=(
            f"正在检查 {citation_count} 个引用编号"
            if citation_count
            else "正在检查引用编号"
        ),
    )
    _emit_answer_progress(
        iteration=int(state.get("iteration_count", 1)),
        summary="正在生成最终中文回答",
    )
    _emit_tool_start(action, int(state.get("iteration_count", 1)))
    toolbox = _toolbox(state)
    responsibility_gate = evaluate_responsibility_gate(question)
    topic_gate_query = " ".join([question, *state.get("history", [])])
    if responsibility_gate.triggered:
        tool_result = AgentToolResult(
            tool_name="answer_with_citations",
            call=AgentToolCallRecord(
                tool_name="responsibility_gate",
                input_summary=truncate_text(question),
                output_summary="refused=True responsibility_gate",
                succeeded=True,
            ),
            answer=RESPONSIBILITY_REFUSAL_ANSWER,
            refused=True,
            refusal_reason=responsibility_gate.refusal_reason,
        )
    elif not has_topic_anchor(topic_gate_query):
        refusal_reason = "Question appears off-topic: no domain anchor was found."
        tool_result = AgentToolResult(
            tool_name="answer_with_citations",
            call=AgentToolCallRecord(
                tool_name="off_topic_gate",
                input_summary=truncate_text(question),
                output_summary="refused=True off_topic",
                succeeded=True,
            ),
            answer="当前问题缺少项目资料库的领域锚点，无法基于堆石混凝土资料可靠回答。",
            refused=True,
            refusal_reason=refusal_reason,
        )
    elif not answer_sources:
        tool_result = toolbox.answer_with_citations(
            question,
            top_k=int(state.get("top_k", 5)),
            retrieval_mode="hybrid",
            history=state.get("history", []),
        )
    else:
        with latency_timer("answer_latency_ms"):
            model_result = toolbox.chat_model_provider.generate(
                evidence_answer_messages(
                    question,
                    sources=answer_sources,
                    history=state.get("history", []),
                )
            )
        allowed_source_ids = list(range(1, len(answer_sources) + 1))
        citations = extract_citations(model_result.answer, allowed_source_ids)
        answer = model_result.answer
        if not citations:
            with latency_timer("answer_latency_ms"):
                repair_result = toolbox.chat_model_provider.generate(
                    citation_repair_messages(
                        question,
                        draft_answer=model_result.answer,
                        sources=answer_sources,
                        history=state.get("history", []),
                    )
                )
            repair_citations = extract_citations(repair_result.answer, allowed_source_ids)
            if repair_citations:
                answer = repair_result.answer
                citations = repair_citations
        refused = not citations
        refusal_reason = (
            "已有证据未能支撑带有效引用编号的回答。"
            if refused
            else None
        )
        tool_result = AgentToolResult(
            tool_name="answer_with_citations",
            call=AgentToolCallRecord(
                tool_name="answer_with_citations",
                input_summary=(
                    f"question={truncate_text(question)}; "
                    f"existing_sources={len(answer_sources)}"
                ),
                output_summary=(
                    f"refused={refused}; sources={len(answer_sources)}; "
                    f"citations={len(citations)}"
                ),
                succeeded=not refused,
                error=refusal_reason,
            ),
            answer=answer if not refused else refusal_answer(refusal_reason),
            sources=answer_sources,
            citations=citations,
            refused=refused,
            refusal_reason=refusal_reason,
        )
    updates = _append_tool_result(state, action, tool_result)
    updates["answer"] = tool_result.answer or ""
    updates["refused"] = tool_result.refused
    updates["refusal_reason"] = tool_result.refusal_reason
    return updates


def refuse_node(state: LangGraphAgentState) -> dict[str, Any]:
    reason = state.get("refusal_reason") or "Reliable evidence was not available."
    action = ReActAction(
        action="refuse",
        refusal_reason=reason,
        reasoning_summary="Refuse safely.",
    )
    step = ReActStepRecord(
        name="refuse",
        action="refuse",
        input_summary=action.safe_input_summary(),
        output_summary=reason,
        succeeded=True,
        iteration=int(state.get("iteration_count", 1)),
    )
    return {
        "answer": refusal_answer(reason),
        "refused": True,
        "refusal_reason": reason,
        "workflow_steps": [*state.get("workflow_steps", []), serialize_step(step)],
    }


def final_answer_node(state: LangGraphAgentState) -> dict[str, Any]:
    answer = state.get("answer") or refusal_answer(state.get("refusal_reason"))
    return {"answer": answer}


def _append_tool_result(
    state: LangGraphAgentState,
    action: ReActAction,
    tool_result: AgentToolResult,
) -> dict[str, Any]:
    observation = observation_from_tool_result(action=action, tool_result=tool_result)
    updates = _append_observation(state, action, observation)
    _emit_tool_result(action, observation, int(state.get("iteration_count", 1)))
    updates["tool_calls"] = [
        *state.get("tool_calls", []),
        serialize_tool_call(tool_result.call),
    ]
    updates["search_results"] = serialize_search_items(
        merge_search_results(
            deserialize_search_items(state.get("search_results", [])),
            tool_result.search_results,
        )
    )
    updates["sources"] = serialize_source_references(
        merge_sources(
            deserialize_source_references(state.get("sources", [])),
            tool_result.sources,
        )
    )
    updates["citations"] = unique_ints(
        [*state.get("citations", []), *tool_result.citations]
    )
    if tool_result.refused:
        updates["refused"] = True
        updates["refusal_reason"] = tool_result.refusal_reason
    return updates


def _append_observation(
    state: LangGraphAgentState,
    action: ReActAction,
    observation: ReActObservation,
) -> dict[str, Any]:
    iteration = int(state.get("iteration_count", 1))
    step = ReActStepRecord(
        name=action.action,
        action=action.action,
        input_summary=action.safe_input_summary(),
        output_summary=observation.observation_summary,
        succeeded=observation.succeeded,
        iteration=iteration,
        error=observation.error,
    )
    return {
        "observations": [*state.get("observations", []), serialize_observation(observation)],
        "workflow_steps": [*state.get("workflow_steps", []), serialize_step(step)],
    }


def _toolbox(state: LangGraphAgentState) -> AgentToolbox:
    toolbox = state.get("_toolbox")
    if toolbox is None:
        toolbox = _CURRENT_TOOLBOX.get()
    if toolbox is None:
        raise ValueError("LangGraph agent state is missing _toolbox")
    return toolbox


def _question(state: LangGraphAgentState) -> str:
    question = (state.get("normalized_question") or state.get("question") or "").strip()
    if not question:
        raise ValueError("LangGraph agent state is missing question")
    return question


def _current_query(state: LangGraphAgentState) -> str:
    return (state.get("current_query") or _question(state)).strip()


def next_action_from_state(state: LangGraphAgentState) -> LangGraphAgentRoute:
    return state.get("next_action", "refuse")


def serialize_observation(value: ReActObservation | dict[str, Any]) -> dict[str, Any]:
    return _to_plain_dict(value)


def deserialize_observation(value: ReActObservation | dict[str, Any]) -> ReActObservation:
    if isinstance(value, ReActObservation):
        return value
    return ReActObservation(**value)


def deserialize_observations(values: list[ReActObservation | dict[str, Any]]) -> list[ReActObservation]:
    return [deserialize_observation(value) for value in values]


def serialize_step(value: ReActStepRecord | dict[str, Any]) -> dict[str, Any]:
    return _to_plain_dict(value)


def deserialize_step(value: ReActStepRecord | dict[str, Any]) -> ReActStepRecord:
    if isinstance(value, ReActStepRecord):
        return value
    return ReActStepRecord(**value)


def deserialize_steps(values: list[ReActStepRecord | dict[str, Any]]) -> list[ReActStepRecord]:
    return [deserialize_step(value) for value in values]


def serialize_tool_call(value: AgentToolCallRecord | dict[str, Any]) -> dict[str, Any]:
    return _to_plain_dict(value)


def deserialize_tool_call(value: AgentToolCallRecord | dict[str, Any]) -> AgentToolCallRecord:
    if isinstance(value, AgentToolCallRecord):
        return value
    return AgentToolCallRecord(**value)


def deserialize_tool_calls(values: list[AgentToolCallRecord | dict[str, Any]]) -> list[AgentToolCallRecord]:
    return [deserialize_tool_call(value) for value in values]


def serialize_search_items(values: list[AgentSearchItem | dict[str, Any]]) -> list[dict[str, Any]]:
    return [_to_plain_dict(value) for value in values]


def deserialize_search_items(values: list[AgentSearchItem | dict[str, Any]]) -> list[AgentSearchItem]:
    return [
        value if isinstance(value, AgentSearchItem) else AgentSearchItem(**value)
        for value in values
    ]


def serialize_source_references(
    values: list[AgentSourceReference | dict[str, Any]],
) -> list[dict[str, Any]]:
    return [_to_plain_dict(value) for value in values]


def deserialize_source_references(
    values: list[AgentSourceReference | dict[str, Any]],
) -> list[AgentSourceReference]:
    return [
        value if isinstance(value, AgentSourceReference) else AgentSourceReference(**value)
        for value in values
    ]


def deserialize_prior_source_references(
    values: list[AgentSourceReference | dict[str, Any]],
) -> list[AgentSourceReference]:
    sources: list[AgentSourceReference] = []
    for index, value in enumerate(values, start=1):
        if isinstance(value, AgentSourceReference):
            sources.append(value)
            continue
        title = str(
            value.get("title")
            or value.get("document_title")
            or value.get("source_id")
            or f"Prior source {index}"
        )
        sources.append(
            AgentSourceReference(
                source_id=str(value.get("source_id") or f"prior:{index}"),
                title=title,
                source_type=str(value.get("source_type") or "prior_conversation"),
                document_id=_optional_int(value.get("document_id")),
                chunk_id=_optional_int(value.get("chunk_id")),
                chunk_index=_optional_int(value.get("chunk_index")),
                content=value.get("content"),
                chunk_type=str(value.get("chunk_type") or "text"),
                caption=value.get("caption"),
                page_number=_optional_int(value.get("page_number")),
                table_content=value.get("table_content"),
            )
        )
    return sources


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_plain_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"Cannot serialize {type(value)!r} into LangGraph state")


TABLE_QUERY_TERMS = (
    "table",
    "tabulated",
    "row",
    "column",
    "mix ratio",
    "parameter table",
    "表格",
    "表",
    "数据表",
    "配合比表",
    "参数表",
)


def query_requests_table(question: str) -> bool:
    normalized = question.casefold()
    return any(term in normalized for term in TABLE_QUERY_TERMS)


EXPAND_FOLLOWUP_TERMS = (
    "\u8be6\u7ec6",
    "\u5c55\u5f00",
    "\u8865\u5145",
    "\u7ee7\u7eed",
    "detail",
    "expand",
    "continue",
    "elaborate",
)


def is_expand_followup_question(question: str) -> bool:
    normalized = question.casefold().strip()
    return bool(normalized) and len(normalized) <= 80 and any(
        term in normalized for term in EXPAND_FOLLOWUP_TERMS
    )


def set_current_toolbox(toolbox: AgentToolbox) -> Token[AgentToolbox | None]:
    return _CURRENT_TOOLBOX.set(toolbox)


def reset_current_toolbox(token: Token[AgentToolbox | None]) -> None:
    _CURRENT_TOOLBOX.reset(token)


def set_current_event_sink(event_sink: ReActEventSink | None) -> Token[ReActEventSink | None]:
    return _CURRENT_EVENT_SINK.set(event_sink)


def reset_current_event_sink(token: Token[ReActEventSink | None]) -> None:
    _CURRENT_EVENT_SINK.reset(token)


def set_current_planner_provider(
    planner_provider: ChatModelProvider | None,
) -> Token[ChatModelProvider | None]:
    return _CURRENT_PLANNER_PROVIDER.set(planner_provider)


def reset_current_planner_provider(token: Token[ChatModelProvider | None]) -> None:
    _CURRENT_PLANNER_PROVIDER.reset(token)


def _emit(event: str, payload: dict[str, object]) -> None:
    event_sink = _CURRENT_EVENT_SINK.get()
    if event_sink is not None:
        event_sink(ReActRuntimeEvent(event=event, payload=payload))


def _emit_tool_start(action: ReActAction, iteration: int) -> None:
    _emit(
        "tool_call_start",
        {
            "iteration": iteration,
            "tool_name": action.action,
            "input_summary": action.safe_input_summary(),
        },
    )


def _emit_tool_result(
    action: ReActAction,
    observation: ReActObservation,
    iteration: int,
) -> None:
    _emit(
        "tool_call_result",
        {
            "iteration": iteration,
            "tool_name": action.action,
            "observation_summary": observation.observation_summary,
            "succeeded": observation.succeeded,
        },
    )


def _emit_answer_progress(*, iteration: int, summary: str) -> None:
    _emit(
        "agent_step",
        {
            "iteration": iteration,
            "action": "answer_progress",
            "step_summary": summary,
        },
    )


def _emit_search_progress(*, iteration: int, summary: str) -> None:
    _emit(
        "agent_step",
        {
            "iteration": iteration,
            "action": "search_progress",
            "step_summary": summary,
        },
    )
