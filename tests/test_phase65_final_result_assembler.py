from __future__ import annotations

from app.services.agent.final_result_assembler import (
    build_cached_evidence_result,
    build_final_generation_failure_result,
    build_pre_tool_refusal_result,
    build_runtime_checkpoint_result,
    build_tool_calling_result,
)
from app.services.agent.runtime import AgentRuntimeState, RuntimeContext
from app.services.agent.tools import AgentSourceReference, AgentToolCallRecord
from app.services.observability.latency_trace import LatencyTrace


def test_final_result_assembler_adds_safe_runtime_and_count_metadata() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    runtime_state.set_stop_reason("completed")
    tool_call = AgentToolCallRecord(
        tool_name="hybrid_search_knowledge",
        input_summary="query=问题",
        output_summary="selected=1",
        succeeded=True,
        step_id="tool-1",
    )

    result = build_tool_calling_result(
        question="问题",
        answer="答案 [1]",
        tool_calls=[tool_call],
        workflow_steps=[tool_call],
        search_results=[],
        sources=[],
        citations=[1],
        refused=False,
        refusal_reason=None,
        llm_call_count=2,
        repeated_query_count=1,
        near_duplicate_query_count=1,
        skipped_tool_call_count=0,
        executed_tool_call_count=1,
        citation_repair_count=1,
        runtime_state=runtime_state,
        latency_trace={"total_latency_ms": 12.0},
    )

    assert result.answer == "答案 [1]"
    assert result.reasoning_summary == (
        "tool_calling_agent llm_calls=2; tool_calls=1; "
        "executed_tool_call_count=1; skipped_tool_call_count=0; "
        "citation_repair_count=1; repeated_query_count=1"
    )
    assert result.latency_trace["runtime_stop_reason"] == "completed"
    assert result.latency_trace["llm_call_count"] == 2
    assert result.latency_trace["executed_tool_call_count"] == 1


def test_pre_tool_refusal_result_preserves_gate_step_and_trace_shape() -> None:
    result = build_pre_tool_refusal_result(
        question="离题问题",
        answer="无法回答",
        refusal_reason="off-topic",
        gate_name="off_topic_gate",
        output_summary="refused=True off_topic",
        reasoning_summary="tool_calling_agent refused before tool loop via off_topic_gate.",
        latency_trace=LatencyTrace(),
    )

    assert result.refused
    assert result.workflow_steps[0].tool_name == "off_topic_gate"
    assert result.workflow_steps[0].input_summary == "离题问题"
    assert result.iteration_count == 1
    assert result.latency_trace["iteration_count"] == 1
    assert result.latency_trace["tool_call_count"] == 0


def test_final_generation_failure_uses_cited_evidence_fallback() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    source = AgentSourceReference(
        source_id="s1",
        title="来源标题",
        source_type="local",
        content="可引用的证据片段",
    )

    result = build_final_generation_failure_result(
        question="问题",
        sources=[source],
        search_results=[],
        tool_calls=[],
        workflow_steps=[],
        llm_call_count=1,
        repeated_query_count=0,
        near_duplicate_query_count=0,
        skipped_tool_call_count=0,
        executed_tool_call_count=1,
        citation_repair_count=0,
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
        error=TimeoutError("provider timed out"),
    )

    assert not result.refused
    assert result.citations == [1]
    assert "可引用的证据片段 [1]" in result.answer
    assert result.workflow_steps[-1].tool_name == "final_answer"
    assert result.latency_trace["final_generation_failed"] is True
    assert result.latency_trace["final_generation_error_type"] == "TimeoutError"
    assert result.latency_trace["runtime_stop_reason"] == "final_generation_failed"


def test_cached_evidence_result_marks_answer_when_citations_are_valid() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    tool_call = AgentToolCallRecord(
        tool_name="hybrid_search_knowledge",
        input_summary="cache_identity=abc",
        output_summary="cache hit",
        succeeded=True,
        step_id="tool-1",
    )

    result = build_cached_evidence_result(
        question="问题",
        answer="缓存证据回答 [1]",
        search_results=[],
        sources=[],
        tool_calls=[tool_call],
        workflow_steps=[tool_call],
        citations=[1],
        llm_call_count=1,
        citation_repair_count=0,
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
    )

    assert not result.refused
    assert result.refusal_reason is None
    assert result.citations == [1]
    assert result.latency_trace["runtime_stop_reason"] == "semantic_evidence_cache_hit"
    assert result.latency_trace["runtime_final_decision"] == "answer"
    assert result.latency_trace["executed_tool_call_count"] == 0


def test_cached_evidence_result_refuses_when_citations_are_missing() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))

    result = build_cached_evidence_result(
        question="问题",
        answer="缓存证据回答但没有引用",
        search_results=[],
        sources=[],
        tool_calls=[],
        workflow_steps=[],
        citations=[],
        llm_call_count=1,
        citation_repair_count=1,
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
    )

    assert result.refused
    assert result.refusal_reason == "Cached evidence answer did not include valid citations."
    assert result.latency_trace["runtime_stop_reason"] == "cached_evidence_without_citations"
    assert result.latency_trace["runtime_final_decision"] == "refuse"
    assert result.latency_trace["citation_repair_count"] == 1


def test_runtime_checkpoint_result_marks_completed_resume_with_citations() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    source = AgentSourceReference(
        source_id="s1",
        title="来源标题",
        source_type="local",
        content="恢复证据",
    )
    resume_step = AgentToolCallRecord(
        tool_name="runtime_resume",
        input_summary="checkpoint",
        output_summary="resumed from completed evidence node",
        succeeded=True,
    )

    result = build_runtime_checkpoint_result(
        question="问题",
        answer="恢复后的引用回答 [1]",
        sources=[source],
        workflow_steps=[resume_step],
        citations=[1],
        llm_call_count=1,
        citation_repair_count=0,
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
    )

    assert not result.refused
    assert result.citations == [1]
    assert result.workflow_steps[-1].tool_name == "final_answer"
    assert result.latency_trace["runtime_stop_reason"] == "runtime_resume_completed"
    assert result.latency_trace["runtime_final_decision"] == "answer"


def test_runtime_checkpoint_result_refuses_when_sources_are_missing() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    resume_step = AgentToolCallRecord(
        tool_name="runtime_resume",
        input_summary="checkpoint",
        output_summary="resumed from completed evidence node",
        succeeded=True,
    )

    result = build_runtime_checkpoint_result(
        question="问题",
        answer="",
        sources=[],
        workflow_steps=[resume_step],
        citations=[],
        llm_call_count=0,
        citation_repair_count=0,
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
    )

    assert result.refused
    assert result.answer == "Runtime checkpoint did not contain reusable source evidence."
    assert result.refusal_reason == "Runtime checkpoint did not contain reusable source evidence."
    assert result.latency_trace["runtime_stop_reason"] == "resume_checkpoint_without_sources"
    assert result.latency_trace["runtime_final_decision"] == "refuse"
