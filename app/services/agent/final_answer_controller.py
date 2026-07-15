"""Citation-first final-answer generation policy."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.services.agent.runtime_contracts import (
    FinalAnswerRequest,
    FinalAnswerOutcome,
    RuntimeStopReason,
    ToolCallingFinalAnswerStrategy,
)
from app.services.agent.final_result_assembler import (
    build_cached_evidence_result,
    build_final_generation_failure_result,
    build_runtime_checkpoint_result,
    build_tool_calling_result,
)
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    truncate_text,
)
from app.services.observability.latency_trace import LatencyTrace


@dataclass(frozen=True)
class EvidenceAnswerGeneration:
    answer: str
    citations: tuple[int, ...]
    citation_repair_count: int
    llm_call_count: int


@dataclass
class _FinalPromptTraceShape:
    character_count: int = 0
    cjk_character_count: int = 0
    source_count: int = 0
    history_character_count: int = 0
    estimated_input_tokens: int = 0
    budget_applied: bool = False

    def as_trace_values(self) -> dict[str, object]:
        return {
            "final_prompt_character_count": self.character_count,
            "final_prompt_cjk_character_count": self.cjk_character_count,
            "final_prompt_source_count": self.source_count,
            "final_prompt_history_character_count": self.history_character_count,
            "final_prompt_estimated_input_tokens": self.estimated_input_tokens,
            "final_prompt_budget_applied": self.budget_applied,
        }


def record_final_generation_call_counts(trace: LatencyTrace, llm_call_count: int) -> None:
    count = max(0, int(llm_call_count))
    if count <= 0:
        return
    trace.set_value(
        "final_generation_call_count",
        int(trace.values.get("final_generation_call_count", 0) or 0) + count,
    )
    trace.set_value(
        "total_model_call_count",
        int(trace.values.get("total_model_call_count", 0) or 0) + count,
    )


class FinalAnswerController:
    """Generates a source-backed answer and performs at most one repair pass."""

    def __init__(
        self,
        provider: Any,
        *,
        answer_messages: Callable[..., object],
        repair_messages: Callable[..., object],
        citation_extractor: Callable[[str, Sequence[int]], Sequence[int]],
    ) -> None:
        self._provider = provider
        self._answer_messages = answer_messages
        self._repair_messages = repair_messages
        self._citation_extractor = citation_extractor

    @staticmethod
    def outcome_from_result(
        *,
        result: Any,
        citations: Sequence[int],
        citation_repair_count: int,
        stop_reason: RuntimeStopReason,
    ) -> FinalAnswerOutcome:
        return FinalAnswerOutcome(
            result=result,
            citations=tuple(int(value) for value in citations),
            citation_repair_count=max(0, int(citation_repair_count)),
            stop_reason=stop_reason,
        )

    def generate(self, request: FinalAnswerRequest) -> FinalAnswerOutcome:
        """Generate and assemble the standard tool-calling final answer result."""
        workflow_steps = list(request.workflow_steps)
        try:
            if hasattr(self._provider, "stream_generate"):
                prompt_shape = (
                    _FinalPromptTraceShape()
                    if request.prompt_budgets
                    else None
                )
                generated = self.stream_final_evidence(
                    question=request.question,
                    sources=list(request.sources),
                    history=request.history,
                    strategy=request.strategy,
                    trace=request.latency_trace,
                    prompt_budgets=dict(request.prompt_budgets),
                    token_emitter=request.token_emitter,
                    prompt_shape=prompt_shape,
                )
            else:
                generated = self.generate_evidence(
                    question=request.question,
                    sources=list(request.sources),
                    history=request.history,
                    strategy=request.strategy,
                    trace=request.latency_trace,
                    prompt_budgets=dict(request.prompt_budgets),
                )
        except Exception as exc:
            result = build_final_generation_failure_result(
                question=request.question,
                sources=list(request.sources),
                search_results=list(request.search_results),
                tool_calls=list(request.tool_calls),
                workflow_steps=workflow_steps,
                llm_call_count=0,
                repeated_query_count=0,
                near_duplicate_query_count=0,
                skipped_tool_call_count=0,
                executed_tool_call_count=len(request.tool_calls),
                citation_repair_count=0,
                runtime_state=request.runtime_state,
                latency_trace=request.latency_trace,
                error=exc,
            )
            return self.outcome_from_result(
                result=result,
                citations=result.citations,
                citation_repair_count=0,
                stop_reason="completed" if result.citations else "internal_error",
            )

        citations = list(generated.citations)
        record_final_generation_call_counts(request.latency_trace, generated.llm_call_count)
        if citations:
            request.runtime_state.set_stop_reason("completed")
            request.runtime_state.final_decision = "answer"
            workflow_steps.append(
                AgentToolCallRecord(
                    tool_name="final_answer",
                    input_summary="run coordinator",
                    output_summary=truncate_text(generated.answer),
                    succeeded=True,
                    step_id="final",
                )
            )
            result = build_tool_calling_result(
                question=request.question,
                answer=generated.answer,
                tool_calls=list(request.tool_calls),
                workflow_steps=workflow_steps,
                search_results=list(request.search_results),
                sources=list(request.sources),
                citations=citations,
                refused=False,
                refusal_reason=None,
                llm_call_count=generated.llm_call_count,
                repeated_query_count=0,
                near_duplicate_query_count=0,
                skipped_tool_call_count=0,
                executed_tool_call_count=len(request.tool_calls),
                citation_repair_count=generated.citation_repair_count,
                runtime_state=request.runtime_state,
                latency_trace=request.latency_trace.finalize(
                    iteration_count=len(workflow_steps),
                    tool_call_count=len(request.tool_calls),
                ),
            )
            return self.outcome_from_result(
                result=result,
                citations=citations,
                citation_repair_count=generated.citation_repair_count,
                stop_reason="completed",
            )

        refusal_reason = "Final answer generation did not include valid citations."
        request.runtime_state.set_stop_reason("insufficient_evidence")
        request.runtime_state.final_decision = "refuse"
        workflow_steps.append(
            AgentToolCallRecord(
                tool_name="final_answer",
                input_summary="run coordinator",
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
            llm_call_count=generated.llm_call_count,
            repeated_query_count=0,
            near_duplicate_query_count=0,
            skipped_tool_call_count=0,
            executed_tool_call_count=len(request.tool_calls),
            citation_repair_count=generated.citation_repair_count,
            runtime_state=request.runtime_state,
            latency_trace=request.latency_trace.finalize(
                iteration_count=len(workflow_steps),
                tool_call_count=len(request.tool_calls),
            ),
        )
        return self.outcome_from_result(
            result=result,
            citations=(),
            citation_repair_count=generated.citation_repair_count,
            stop_reason="insufficient_evidence",
        )

    def from_cached_evidence(
        self,
        *,
        question: str,
        search_results: Sequence[AgentSearchItem],
        sources: Sequence[AgentSourceReference],
        tool_calls: Sequence[AgentToolCallRecord],
        workflow_steps: Sequence[AgentToolCallRecord],
        history: Sequence[str] | None,
        strategy: ToolCallingFinalAnswerStrategy,
        runtime_state: Any,
        latency_trace: LatencyTrace,
        prompt_budgets: dict[str, int] | None = None,
    ) -> FinalAnswerOutcome:
        generated = self.generate_evidence(
            question=question,
            sources=sources,
            history=history,
            strategy=strategy,
            trace=latency_trace,
            prompt_budgets=prompt_budgets or {},
        )
        result = build_cached_evidence_result(
            question=question,
            answer=generated.answer,
            search_results=list(search_results),
            sources=list(sources),
            tool_calls=list(tool_calls),
            workflow_steps=list(workflow_steps),
            citations=list(generated.citations),
            llm_call_count=generated.llm_call_count,
            citation_repair_count=generated.citation_repair_count,
            runtime_state=runtime_state,
            latency_trace=latency_trace,
        )
        return self.outcome_from_result(
            result=result,
            citations=result.citations,
            citation_repair_count=generated.citation_repair_count,
            stop_reason="completed" if result.citations else "insufficient_evidence",
        )

    def from_checkpoint(
        self,
        *,
        question: str,
        sources: Sequence[AgentSourceReference],
        workflow_steps: Sequence[AgentToolCallRecord],
        history: Sequence[str] | None,
        strategy: ToolCallingFinalAnswerStrategy,
        runtime_state: Any,
        latency_trace: LatencyTrace,
        prompt_budgets: dict[str, int] | None = None,
    ) -> FinalAnswerOutcome:
        if not sources:
            result = build_runtime_checkpoint_result(
                question=question,
                workflow_steps=list(workflow_steps),
                sources=[],
                citations=[],
                answer="",
                llm_call_count=0,
                citation_repair_count=0,
                runtime_state=runtime_state,
                latency_trace=latency_trace,
            )
            return self.outcome_from_result(
                result=result,
                citations=(),
                citation_repair_count=0,
                stop_reason="insufficient_evidence",
            )

        generated = self.generate_evidence(
            question=question,
            sources=sources,
            history=history,
            strategy=strategy,
            trace=latency_trace,
            prompt_budgets=prompt_budgets or {},
            repair_on_missing_citations=False,
        )
        result = build_runtime_checkpoint_result(
            question=question,
            answer=generated.answer,
            workflow_steps=list(workflow_steps),
            sources=list(sources),
            citations=list(generated.citations),
            llm_call_count=generated.llm_call_count,
            citation_repair_count=generated.citation_repair_count,
            runtime_state=runtime_state,
            latency_trace=latency_trace,
        )
        return self.outcome_from_result(
            result=result,
            citations=result.citations,
            citation_repair_count=generated.citation_repair_count,
            stop_reason="completed" if result.citations else "insufficient_evidence",
        )

    def stream_final_evidence(
        self,
        *,
        question: str,
        sources: Sequence[AgentSourceReference],
        history: Sequence[str] | None,
        strategy: ToolCallingFinalAnswerStrategy,
        trace: LatencyTrace,
        prompt_budgets: dict[str, int],
        token_emitter: Callable[[str], None] | None = None,
        prompt_shape: Any | None = None,
        emit_answer_tokens: bool = True,
    ) -> EvidenceAnswerGeneration:
        generated = self.stream_evidence(
            question=question,
            sources=sources,
            history=history,
            strategy=strategy,
            trace=trace,
            prompt_budgets=prompt_budgets,
            token_emitter=token_emitter if emit_answer_tokens else None,
            citation_suffix_emitter=token_emitter,
            prompt_shape=prompt_shape,
            append_citation_on_missing_citations=True,
        )
        if prompt_shape is not None and hasattr(prompt_shape, "as_trace_values"):
            for field_name, value in prompt_shape.as_trace_values().items():
                trace.set_value(str(field_name), value)
        return generated

    def generate_final_evidence(
        self,
        *,
        question: str,
        sources: Sequence[AgentSourceReference],
        history: Sequence[str] | None,
        strategy: ToolCallingFinalAnswerStrategy,
        trace: LatencyTrace,
        prompt_budgets: dict[str, int],
    ) -> EvidenceAnswerGeneration:
        return self.generate_evidence(
            question=question,
            sources=sources,
            history=history,
            strategy=strategy,
            trace=trace,
            prompt_budgets=prompt_budgets,
        )

    def validate_model_content(
        self,
        *,
        question: str,
        draft_answer: str,
        sources: Sequence[AgentSourceReference],
        history: Sequence[str] | None,
        strategy: ToolCallingFinalAnswerStrategy,
        trace: LatencyTrace,
        prompt_budgets: dict[str, int],
    ) -> EvidenceAnswerGeneration:
        return self.validate_or_repair(
            question=question,
            draft_answer=draft_answer,
            sources=sources,
            history=history,
            strategy=strategy,
            trace=trace,
            prompt_budgets=prompt_budgets,
        )

    def generate_evidence(
        self,
        *,
        question: str,
        sources: Sequence[AgentSourceReference],
        history: Sequence[str] | None,
        strategy: ToolCallingFinalAnswerStrategy,
        trace: LatencyTrace,
        prompt_budgets: dict[str, int],
        repair_on_missing_citations: bool = True,
    ) -> EvidenceAnswerGeneration:
        allowed_source_ids = tuple(range(1, len(sources) + 1))
        started = time.perf_counter()
        initial = self._provider.generate(
            self._answer_messages(
                question=question,
                sources=list(sources),
                history=history,
                final_answer_strategy=strategy,
                **prompt_budgets,
            )
        )
        trace.add_duration("answer_latency_ms", (time.perf_counter() - started) * 1000.0)
        answer = str(initial.answer)
        citations = tuple(self._citation_extractor(answer, allowed_source_ids))
        if citations or not repair_on_missing_citations:
            return EvidenceAnswerGeneration(
                answer=answer,
                citations=citations,
                citation_repair_count=0,
                llm_call_count=1,
            )

        repair_started = time.perf_counter()
        repaired = self._provider.generate(
            self._repair_messages(
                question=question,
                draft_answer=answer,
                sources=list(sources),
                history=history,
                final_answer_strategy=strategy,
                **prompt_budgets,
            )
        )
        repair_elapsed_ms = (time.perf_counter() - repair_started) * 1000.0
        trace.add_duration("answer_latency_ms", repair_elapsed_ms)
        trace.add_duration("citation_repair_latency_ms", repair_elapsed_ms)
        repaired_answer = str(repaired.answer)
        repaired_citations = tuple(
            self._citation_extractor(repaired_answer, allowed_source_ids)
        )
        return EvidenceAnswerGeneration(
            answer=repaired_answer if repaired_citations else answer,
            citations=repaired_citations or citations,
            citation_repair_count=1,
            llm_call_count=2,
        )

    def stream_evidence(
        self,
        *,
        question: str,
        sources: Sequence[AgentSourceReference],
        history: Sequence[str] | None,
        strategy: ToolCallingFinalAnswerStrategy,
        trace: LatencyTrace,
        prompt_budgets: dict[str, int],
        token_emitter: Callable[[str], None] | None = None,
        citation_suffix_emitter: Callable[[str], None] | None = None,
        prompt_shape: Any | None = None,
        append_citation_on_missing_citations: bool = False,
    ) -> EvidenceAnswerGeneration:
        if not hasattr(self._provider, "stream_generate"):
            raise RuntimeError("final answer provider does not support streaming")
        started = time.perf_counter()
        parts: list[str] = []
        message_args: dict[str, object] = {
            "question": question,
            "sources": list(sources),
            "history": history,
            "final_answer_strategy": strategy,
            **prompt_budgets,
        }
        if prompt_shape is not None:
            message_args["prompt_shape"] = prompt_shape
        messages = self._answer_messages(**message_args)
        for token in self._provider.stream_generate(messages):
            token_text = str(token)
            if not token_text:
                continue
            if trace.values.get("final_model_ttft_ms") is None:
                trace.set_value(
                    "final_model_ttft_ms",
                    round((time.perf_counter() - started) * 1000.0, 3),
                )
            trace.mark_answer_token()
            if token_emitter is not None:
                token_emitter(token_text)
            parts.append(token_text)
            trace.set_value(
                "streamed_token_count",
                int(trace.values["streamed_token_count"]) + 1,
            )
        trace.add_duration(
            "final_generation_latency_ms",
            (time.perf_counter() - started) * 1000.0,
        )
        answer = "".join(parts)
        citations = tuple(
            self._citation_extractor(answer, tuple(range(1, len(sources) + 1)))
        )
        if (
            append_citation_on_missing_citations
            and answer.strip()
            and sources
            and not citations
        ):
            citation_suffix = "\n\n证据引用：[1]"
            suffix_emitter = citation_suffix_emitter or token_emitter
            if suffix_emitter is not None:
                suffix_emitter(citation_suffix)
            answer += citation_suffix
            trace.mark_answer_token()
            trace.set_value(
                "streamed_token_count",
                int(trace.values["streamed_token_count"]) + 1,
            )
            citations = tuple(
                self._citation_extractor(answer, tuple(range(1, len(sources) + 1)))
            )
        return EvidenceAnswerGeneration(
            answer=answer,
            citations=citations,
            citation_repair_count=0,
            llm_call_count=1,
        )

    def validate_or_repair(
        self,
        *,
        question: str,
        draft_answer: str,
        sources: Sequence[AgentSourceReference],
        history: Sequence[str] | None,
        strategy: ToolCallingFinalAnswerStrategy,
        trace: LatencyTrace,
        prompt_budgets: dict[str, int],
        repair_on_missing_citations: bool = True,
    ) -> EvidenceAnswerGeneration:
        """Validate an already-produced final draft and repair it at most once."""
        allowed_source_ids = tuple(range(1, len(sources) + 1))
        validation_started = time.perf_counter()
        citations = tuple(self._citation_extractor(draft_answer, allowed_source_ids))
        trace.add_duration(
            "citation_validation_latency_ms",
            (time.perf_counter() - validation_started) * 1000.0,
        )
        if citations or not repair_on_missing_citations:
            return EvidenceAnswerGeneration(
                answer=draft_answer,
                citations=citations,
                citation_repair_count=0,
                llm_call_count=0,
            )

        repair_started = time.perf_counter()
        repaired = self._provider.generate(
            self._repair_messages(
                question=question,
                draft_answer=draft_answer,
                sources=list(sources),
                history=history,
                final_answer_strategy=strategy,
                **prompt_budgets,
            )
        )
        repair_elapsed_ms = (time.perf_counter() - repair_started) * 1000.0
        trace.add_duration("answer_latency_ms", repair_elapsed_ms)
        trace.add_duration("citation_repair_latency_ms", repair_elapsed_ms)
        repaired_answer = str(repaired.answer)
        repaired_citations = tuple(
            self._citation_extractor(repaired_answer, allowed_source_ids)
        )
        return EvidenceAnswerGeneration(
            answer=repaired_answer if repaired_citations else draft_answer,
            citations=repaired_citations or citations,
            citation_repair_count=1,
            llm_call_count=1,
        )
