from __future__ import annotations

from app.services.agent.final_answer_controller import FinalAnswerController
from app.services.agent.runtime import AgentRuntimeState, RuntimeContext
from app.services.agent.runtime_contracts import FinalAnswerRequest
from app.services.agent.tools import AgentSourceReference, AgentToolCallRecord
from app.services.generation.chat_model import ChatModelResult
from app.services.observability.latency_trace import LatencyTrace


class UncitedThenCitedProvider:
    provider_name = "phase65-final-test"
    model_name = "phase65-final-test-v1"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, _messages: object) -> ChatModelResult:
        self.calls += 1
        return ChatModelResult(
            answer="supported answer [1]" if self.calls == 2 else "uncited answer",
            provider=self.provider_name,
            model_name=self.model_name,
        )


class StreamingProvider:
    provider_name = "phase65-stream-test"
    model_name = "phase65-stream-test-v1"

    def stream_generate(self, _messages: object):
        yield "supported "
        yield "answer [1]"


class UncitedStreamingProvider:
    provider_name = "phase65-stream-test"
    model_name = "phase65-stream-test-v1"

    def stream_generate(self, _messages: object):
        yield "supported "
        yield "answer"


class DraftRepairProvider:
    provider_name = "phase65-repair-test"
    model_name = "phase65-repair-test-v1"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, _messages: object) -> ChatModelResult:
        self.calls += 1
        return ChatModelResult(
            answer="repaired answer [1]",
            provider=self.provider_name,
            model_name=self.model_name,
        )


class PromptShape:
    def __init__(self) -> None:
        self.seen = False

    def as_trace_values(self) -> dict[str, object]:
        return {"prompt_shape_seen": self.seen}


def test_controller_repairs_once_and_returns_valid_citations() -> None:
    provider = UncitedThenCitedProvider()
    trace = LatencyTrace()
    controller = FinalAnswerController(
        provider,
        answer_messages=lambda **_: ["answer"],
        repair_messages=lambda **_: ["repair"],
        citation_extractor=lambda answer, _: [1] if "[1]" in answer else [],
    )

    outcome = controller.generate_evidence(
        question="问题",
        sources=(AgentSourceReference(source_id="s1", title="source", source_type="local"),),
        history=(),
        strategy="structured_final_answer",
        trace=trace,
        prompt_budgets={},
    )

    assert outcome.answer == "supported answer [1]"
    assert outcome.citations == (1,)
    assert outcome.citation_repair_count == 1
    assert outcome.llm_call_count == 2
    assert provider.calls == 2


def test_controller_can_refuse_repair_for_checkpoint_compatibility() -> None:
    provider = UncitedThenCitedProvider()
    controller = FinalAnswerController(
        provider,
        answer_messages=lambda **_: ["answer"],
        repair_messages=lambda **_: ["repair"],
        citation_extractor=lambda answer, _: [1] if "[1]" in answer else [],
    )

    outcome = controller.generate_evidence(
        question="问题",
        sources=(AgentSourceReference(source_id="s1", title="source", source_type="local"),),
        history=(),
        strategy="structured_final_answer",
        trace=LatencyTrace(),
        prompt_budgets={},
        repair_on_missing_citations=False,
    )

    assert outcome.citations == ()
    assert outcome.citation_repair_count == 0
    assert outcome.llm_call_count == 1
    assert provider.calls == 1


def test_controller_marks_first_answer_token_for_streamed_evidence() -> None:
    emitted: list[str] = []
    trace = LatencyTrace()
    controller = FinalAnswerController(
        StreamingProvider(),
        answer_messages=lambda **_: ["answer"],
        repair_messages=lambda **_: ["repair"],
        citation_extractor=lambda answer, _: [1] if "[1]" in answer else [],
    )

    outcome = controller.stream_evidence(
        question="问题",
        sources=(AgentSourceReference(source_id="s1", title="source", source_type="local"),),
        history=(),
        strategy="structured_final_answer",
        trace=trace,
        prompt_budgets={},
        token_emitter=emitted.append,
    )

    assert outcome.answer == "supported answer [1]"
    assert outcome.citations == (1,)
    assert emitted == ["supported ", "answer [1]"]
    assert trace.values["time_to_first_answer_token_ms"] is not None


def test_controller_appends_single_safe_citation_to_uncited_stream() -> None:
    emitted: list[str] = []
    trace = LatencyTrace()
    controller = FinalAnswerController(
        UncitedStreamingProvider(),
        answer_messages=lambda **_: ["answer"],
        repair_messages=lambda **_: ["repair"],
        citation_extractor=lambda answer, _: [1] if "[1]" in answer else [],
    )

    outcome = controller.stream_evidence(
        question="问题",
        sources=(AgentSourceReference(source_id="s1", title="source", source_type="local"),),
        history=(),
        strategy="structured_final_answer",
        trace=trace,
        prompt_budgets={},
        token_emitter=emitted.append,
        append_citation_on_missing_citations=True,
    )

    assert outcome.answer == "supported answer\n\n证据引用：[1]"
    assert outcome.citations == (1,)
    assert emitted == ["supported ", "answer", "\n\n证据引用：[1]"]
    assert trace.values["streamed_token_count"] == 3


def test_controller_validates_existing_draft_and_repairs_once() -> None:
    provider = DraftRepairProvider()
    controller = FinalAnswerController(
        provider,
        answer_messages=lambda **_: ["answer"],
        repair_messages=lambda **_: ["repair"],
        citation_extractor=lambda answer, _: [1] if "[1]" in answer else [],
    )

    outcome = controller.validate_or_repair(
        question="问题",
        draft_answer="uncited draft",
        sources=(AgentSourceReference(source_id="s1", title="source", source_type="local"),),
        history=(),
        strategy="structured_final_answer",
        trace=LatencyTrace(),
        prompt_budgets={},
    )

    assert outcome.answer == "repaired answer [1]"
    assert outcome.citations == (1,)
    assert outcome.citation_repair_count == 1
    assert outcome.llm_call_count == 1
    assert provider.calls == 1


def test_controller_wraps_agent_result_in_standard_outcome() -> None:
    result = object()

    outcome = FinalAnswerController.outcome_from_result(
        result=result,
        citations=[1, 2],
        citation_repair_count=1,
        stop_reason="completed",
    )

    assert outcome.result is result
    assert outcome.citations == (1, 2)
    assert outcome.citation_repair_count == 1
    assert outcome.stop_reason == "completed"


def test_controller_generate_returns_standard_agent_outcome_with_repair() -> None:
    provider = UncitedThenCitedProvider()
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    request = _final_answer_request(runtime_state=runtime_state)
    controller = FinalAnswerController(
        provider,
        answer_messages=lambda **_: ["answer"],
        repair_messages=lambda **_: ["repair"],
        citation_extractor=lambda answer, _: [1] if "[1]" in answer else [],
    )

    outcome = controller.generate(request)

    assert outcome.stop_reason == "completed"
    assert outcome.citations == (1,)
    assert outcome.citation_repair_count == 1
    assert outcome.result.answer == "supported answer [1]"
    assert outcome.result.citations == [1]
    assert outcome.result.refused is False
    assert outcome.result.workflow_steps[-1].tool_name == "final_answer"
    assert outcome.result.latency_trace["runtime_final_decision"] == "answer"
    assert provider.calls == 2


def test_controller_generate_streams_tokens_and_safe_citation_suffix() -> None:
    emitted: list[str] = []
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    request = _final_answer_request(
        runtime_state=runtime_state,
        token_emitter=emitted.append,
    )
    controller = FinalAnswerController(
        UncitedStreamingProvider(),
        answer_messages=lambda **_: ["answer"],
        repair_messages=lambda **_: ["repair"],
        citation_extractor=lambda answer, _: [1] if "[1]" in answer else [],
    )

    outcome = controller.generate(request)

    assert outcome.stop_reason == "completed"
    assert outcome.citations == (1,)
    assert outcome.result.answer == "supported answer\n\n证据引用：[1]"
    assert emitted == ["supported ", "answer", "\n\n证据引用：[1]"]
    assert outcome.result.latency_trace["time_to_first_answer_token_ms"] is not None
    assert outcome.result.latency_trace["streamed_token_count"] == 3


def test_controller_from_cached_evidence_returns_standard_outcome() -> None:
    provider = UncitedThenCitedProvider()
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    controller = FinalAnswerController(
        provider,
        answer_messages=lambda **_: ["answer"],
        repair_messages=lambda **_: ["repair"],
        citation_extractor=lambda answer, _: [1] if "[1]" in answer else [],
    )

    outcome = controller.from_cached_evidence(
        question="问题",
        search_results=[],
        sources=[_source()],
        tool_calls=[_tool_call()],
        workflow_steps=[_tool_call()],
        history=(),
        strategy="structured_final_answer",
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
    )

    assert outcome.stop_reason == "completed"
    assert outcome.citations == (1,)
    assert outcome.result.answer == "supported answer [1]"
    assert outcome.result.latency_trace["runtime_stop_reason"] == "semantic_evidence_cache_hit"
    assert provider.calls == 2


def test_controller_from_checkpoint_refuses_missing_sources_without_model_call() -> None:
    provider = UncitedThenCitedProvider()
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    controller = FinalAnswerController(
        provider,
        answer_messages=lambda **_: ["answer"],
        repair_messages=lambda **_: ["repair"],
        citation_extractor=lambda answer, _: [1] if "[1]" in answer else [],
    )

    outcome = controller.from_checkpoint(
        question="问题",
        sources=[],
        workflow_steps=[_tool_call()],
        history=(),
        strategy="structured_final_answer",
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
    )

    assert outcome.stop_reason == "insufficient_evidence"
    assert outcome.result.refused
    assert "Runtime checkpoint did not contain reusable source evidence" in outcome.result.answer
    assert provider.calls == 0


def test_controller_stream_final_evidence_accepts_prompt_shape_and_emits_suffix() -> None:
    emitted: list[str] = []
    trace = LatencyTrace()
    prompt_shape = PromptShape()

    def answer_messages(**kwargs):
        kwargs["prompt_shape"].seen = True
        return ["answer"]

    controller = FinalAnswerController(
        UncitedStreamingProvider(),
        answer_messages=answer_messages,
        repair_messages=lambda **_: ["repair"],
        citation_extractor=lambda answer, _: [1] if "[1]" in answer else [],
    )

    outcome = controller.stream_final_evidence(
        question="问题",
        sources=[_source()],
        history=(),
        strategy="structured_final_answer",
        trace=trace,
        prompt_budgets={},
        token_emitter=emitted.append,
        prompt_shape=prompt_shape,
    )

    assert outcome.answer.endswith("证据引用：[1]")
    assert outcome.citations == (1,)
    assert emitted == ["supported ", "answer", "\n\n证据引用：[1]"]
    assert trace.values["prompt_shape_seen"] is True


def test_controller_validate_model_content_repairs_existing_draft() -> None:
    provider = DraftRepairProvider()
    controller = FinalAnswerController(
        provider,
        answer_messages=lambda **_: ["answer"],
        repair_messages=lambda **_: ["repair"],
        citation_extractor=lambda answer, _: [1] if "[1]" in answer else [],
    )

    outcome = controller.validate_model_content(
        question="问题",
        draft_answer="uncited draft",
        sources=[_source()],
        history=(),
        strategy="structured_final_answer",
        trace=LatencyTrace(),
        prompt_budgets={},
    )

    assert outcome.answer == "repaired answer [1]"
    assert outcome.citations == (1,)
    assert outcome.citation_repair_count == 1
    assert outcome.llm_call_count == 1
    assert provider.calls == 1


def _final_answer_request(
    *,
    runtime_state: AgentRuntimeState,
    token_emitter=None,
) -> FinalAnswerRequest:
    source = AgentSourceReference(
        source_id="s1",
        title="source",
        source_type="local",
        content="source evidence",
    )
    tool_call = AgentToolCallRecord(
        tool_name="hybrid_search_knowledge",
        input_summary="query=问题",
        output_summary="selected=1",
        succeeded=True,
        step_id="runtime-retrieval-1",
    )
    return FinalAnswerRequest(
        question="问题",
        history=(),
        strategy="structured_final_answer",
        search_results=(),
        sources=(source,),
        tool_calls=(tool_call,),
        workflow_steps=(tool_call,),
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
        prompt_budgets={},
        token_emitter=token_emitter,
    )


def _source() -> AgentSourceReference:
    return AgentSourceReference(
        source_id="s1",
        title="source",
        source_type="local",
        content="source evidence",
    )


def _tool_call() -> AgentToolCallRecord:
    return AgentToolCallRecord(
        tool_name="hybrid_search_knowledge",
        input_summary="query=问题",
        output_summary="selected=1",
        succeeded=True,
        step_id="runtime-retrieval-1",
    )
