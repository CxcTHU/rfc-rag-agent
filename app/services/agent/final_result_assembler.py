"""Safe final Agent result assembly for tool-calling runtime paths."""

from __future__ import annotations

import logging
from typing import Any

from app.core.structured_logging import log_event
from app.services.agent.runtime import AgentRuntimeState
from app.services.agent.service import AgentQueryResult
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    truncate_text,
)
from app.services.observability.latency_trace import LatencyTrace


agent_logger = logging.getLogger("rfc_rag_agent.agent")


def build_pre_tool_refusal_result(
    *,
    question: str,
    answer: str,
    refusal_reason: str | None,
    gate_name: str,
    output_summary: str,
    reasoning_summary: str,
    latency_trace: LatencyTrace,
) -> AgentQueryResult:
    return AgentQueryResult(
        question=question,
        answer=answer,
        tool_calls=[],
        refused=True,
        refusal_reason=refusal_reason,
        reasoning_summary=reasoning_summary,
        mode="tool_calling_agent",
        workflow_steps=[
            AgentToolCallRecord(
                tool_name=gate_name,
                input_summary=truncate_text(question),
                output_summary=output_summary,
                succeeded=True,
            )
        ],
        iteration_count=1,
        latency_trace=latency_trace.finalize(
            iteration_count=1,
            tool_call_count=0,
        ),
    )


def build_tool_calling_result(
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
    runtime_state: AgentRuntimeState | None = None,
    image_analysis: dict[str, object] | None = None,
) -> AgentQueryResult:
    safe_trace: dict[str, object] = dict(latency_trace)
    if runtime_state is not None:
        safe_trace.update(runtime_state.diagnostics())
    safe_trace["llm_call_count"] = llm_call_count
    safe_trace["repeated_query_count"] = repeated_query_count
    safe_trace["near_duplicate_query_count"] = near_duplicate_query_count
    safe_trace["skipped_tool_call_count"] = skipped_tool_call_count
    safe_trace["executed_tool_call_count"] = executed_tool_call_count
    safe_trace["citation_repair_count"] = citation_repair_count
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
        latency_ms=safe_trace.get("total_latency_ms"),
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
        reasoning_summary=tool_calling_reasoning_summary(
            llm_call_count=llm_call_count,
            tool_call_count=len(tool_calls),
            executed_tool_call_count=executed_tool_call_count,
            skipped_tool_call_count=skipped_tool_call_count,
            citation_repair_count=citation_repair_count,
            repeated_query_count=repeated_query_count,
        ),
        mode="tool_calling_agent",
        workflow_steps=workflow_steps,
        iteration_count=len(workflow_steps),
        latency_trace=safe_trace,
        image_analysis=image_analysis,
    )


def build_final_generation_failure_result(
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
    citations = list(range(1, min(len(sources), 3) + 1))
    answer = fallback_answer_from_sources(sources, citations)
    workflow_steps.append(
        AgentToolCallRecord(
            tool_name="final_answer",
            input_summary="evidence fallback",
            output_summary="final provider failed; returned cited evidence fallback",
            succeeded=True,
            step_id="final",
        )
    )
    latency_trace.set_value("final_generation_failed", True)
    latency_trace.set_value("final_generation_error_type", error.__class__.__name__)
    latency_trace.mark_answer_token()
    latency_trace.set_value(
        "streamed_token_count",
        max(int(latency_trace.values.get("streamed_token_count", 0) or 0), 1),
    )
    runtime_state.set_stop_reason("final_generation_failed")
    runtime_state.final_decision = "answer" if citations else "refuse"
    return build_tool_calling_result(
        question=question,
        answer=answer,
        tool_calls=tool_calls,
        workflow_steps=workflow_steps,
        search_results=search_results,
        sources=sources,
        citations=citations,
        refused=not bool(citations),
        refusal_reason=(
            None
            if citations
            else "Final answer generation failed before cited evidence fallback."
        ),
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


def build_cached_evidence_result(
    *,
    question: str,
    answer: str,
    search_results: list[AgentSearchItem],
    sources: list[AgentSourceReference],
    tool_calls: list[AgentToolCallRecord],
    workflow_steps: list[AgentToolCallRecord],
    citations: list[int],
    llm_call_count: int,
    citation_repair_count: int,
    runtime_state: AgentRuntimeState,
    latency_trace: LatencyTrace,
) -> AgentQueryResult:
    if citations:
        runtime_state.final_decision = "answer"
        runtime_state.set_stop_reason("semantic_evidence_cache_hit")
        refused = False
        refusal_reason = None
    else:
        runtime_state.final_decision = "refuse"
        runtime_state.set_stop_reason("cached_evidence_without_citations")
        refused = True
        refusal_reason = "Cached evidence answer did not include valid citations."
    return build_tool_calling_result(
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


def build_runtime_checkpoint_result(
    *,
    question: str,
    answer: str,
    sources: list[AgentSourceReference],
    workflow_steps: list[AgentToolCallRecord],
    citations: list[int],
    llm_call_count: int,
    citation_repair_count: int,
    runtime_state: AgentRuntimeState,
    latency_trace: LatencyTrace,
) -> AgentQueryResult:
    if not sources:
        runtime_state.set_stop_reason("resume_checkpoint_without_sources")
        runtime_state.final_decision = "refuse"
        return build_tool_calling_result(
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

    runtime_state.set_stop_reason("runtime_resume_completed")
    runtime_state.final_decision = "answer" if citations else "refuse"
    workflow_steps.append(
        AgentToolCallRecord(
            tool_name="final_answer",
            input_summary="runtime resume",
            output_summary=truncate_text(answer),
            succeeded=bool(citations),
            error=None if citations else "checkpoint answer missing citations",
        )
    )
    refused = not bool(citations)
    refusal_reason = (
        None if citations else "Runtime checkpoint evidence could not produce cited answer."
    )
    return build_tool_calling_result(
        question=question,
        answer=answer if citations else "Runtime checkpoint evidence could not produce cited answer.",
        tool_calls=[],
        workflow_steps=workflow_steps,
        search_results=[],
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
            tool_call_count=0,
        ),
    )


def fallback_answer_from_sources(
    sources: list[AgentSourceReference],
    citations: list[int],
) -> str:
    if not sources or not citations:
        return "Final answer generation failed before cited evidence could be produced."
    bullets: list[str] = []
    for citation in citations:
        source = sources[citation - 1]
        snippet = truncate_text(source.content or source.title, limit=220)
        bullets.append(f"- {snippet} [{citation}]")
    return (
        "Final answer generation failed after retrieval, so this is a cited "
        "evidence fallback:\n"
        + "\n".join(bullets)
    )


def tool_calling_reasoning_summary(
    *,
    llm_call_count: int,
    tool_call_count: int,
    executed_tool_call_count: int,
    skipped_tool_call_count: int,
    citation_repair_count: int,
    repeated_query_count: int,
) -> str:
    return (
        "tool_calling_agent "
        f"llm_calls={llm_call_count}; "
        f"tool_calls={tool_call_count}; "
        f"executed_tool_call_count={executed_tool_call_count}; "
        f"skipped_tool_call_count={skipped_tool_call_count}; "
        f"citation_repair_count={citation_repair_count}; "
        f"repeated_query_count={repeated_query_count}"
    )
