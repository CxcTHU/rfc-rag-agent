from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from typing import Any


from app.services.agent.service import AgentQueryResult
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    AgentToolResult,
    truncate_text,
)
from app.services.agent.runtime import AgentRuntimeState
from app.services.agent.runtime_events import (
    RuntimeEventBus,
    ToolCallingRuntimeEvent,
)
from app.services.agent.final_answer_controller import FinalAnswerController
from app.services.agent.final_result_assembler import (
    build_final_generation_failure_result,
    build_tool_calling_result,
)
from app.services.agent.final_prompt import (
    TOOL_RESULT_MAX_SOURCES,
    TOOL_RESULT_SNIPPET_LIMIT,
    ToolCallingFinalAnswerStrategy,
    citation_repair_messages,
    evidence_answer_messages,
)
from app.services.agent.runtime_contracts import (
    FinalAnswerRequest,
    FinalAnswerOutcome,
    RuntimeStopReason,
)
from app.services.agent.tool_registry import TEXT_TOOL_NAMES
from app.core.config import get_settings
from app.services.brain.workflow import (
    extract_citations,
)
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelProvider,
    ChatToolCall,
    create_chat_model_provider,
)
from app.services.observability.latency_trace import (
    LatencyTrace,
)


TOOL_CALLING_DEFAULT_MAX_ITERATIONS = 3
TOOL_CALLING_HARD_MAX_ITERATIONS = 3
TOOL_CALLING_MAX_EXECUTED_TOOLS_PER_ITERATION = 1
TOOL_CALLING_NEAR_DUPLICATE_THRESHOLD = 0.65
TOOL_CALLING_PREFERRED_TOOL_ORDER = {
    "hybrid_search_knowledge": 0,
    "search_figures": 1,
    "search_tables": 2,
}
agent_logger = logging.getLogger("rfc_rag_agent.agent")


ToolCallingEventSink = Callable[[ToolCallingRuntimeEvent], None]
InternalToolCallingEventSink = ToolCallingEventSink | RuntimeEventBus


def create_runtime_identity_provider() -> ChatModelProvider | None:
    settings = get_settings()
    provider_name = (
        settings.runtime_identity_model_provider
        or settings.planner_chat_model_provider
    )
    model_name = (
        settings.runtime_identity_model_name
        or settings.planner_chat_model_name
    )
    if not provider_name.strip() or not model_name.strip():
        return None
    try:
        return create_chat_model_provider(
            provider_name=provider_name,
            model_name=model_name,
            api_key=(
                settings.runtime_identity_model_api_key
                or settings.planner_chat_model_api_key
            ),
            base_url=(
                settings.runtime_identity_model_base_url
                or settings.planner_chat_model_base_url
            ),
            temperature=settings.runtime_identity_model_temperature,
            timeout_seconds=settings.runtime_identity_model_timeout_seconds,
            max_attempts=1,
        )
    except ValueError:
        return None


class ToolCallingFinalAnswerFacade:
    """RunCoordinator-facing final answer adapter preserving service result shape."""

    def __init__(
        self,
        *,
        chat_model_provider: ChatModelProvider,
    ) -> None:
        self._chat_model_provider = chat_model_provider

    def generate(self, request: FinalAnswerRequest) -> FinalAnswerOutcome:
        return FinalAnswerController(
            self._chat_model_provider,
            answer_messages=evidence_answer_messages,
            repair_messages=citation_repair_messages,
            citation_extractor=extract_citations,
        ).generate(request)

    def refuse(self, request: FinalAnswerRequest) -> FinalAnswerOutcome:
        stop_detail = request.runtime_state.stop_reason
        if not stop_detail or stop_detail == "not_stopped":
            stop_detail = "insufficient_evidence"
            request.runtime_state.set_stop_reason(stop_detail)
        request.runtime_state.final_decision = "refuse"
        stop_reason = request.runtime_state.normalized_stop_reason or "insufficient_evidence"
        if stop_reason not in RuntimeStopReason.__args__:
            stop_reason = "insufficient_evidence"
        refusal_reason = runtime_refusal_message_for_request(request, stop_detail)
        workflow_steps = list(request.workflow_steps)
        workflow_steps.append(
            AgentToolCallRecord(
                tool_name="final_answer",
                input_summary="run coordinator refusal",
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
            llm_call_count=0,
            repeated_query_count=0,
            near_duplicate_query_count=0,
            skipped_tool_call_count=0,
            executed_tool_call_count=len(request.tool_calls),
            citation_repair_count=0,
            runtime_state=request.runtime_state,
            latency_trace=request.latency_trace.finalize(
                iteration_count=len(workflow_steps),
                tool_call_count=len(request.tool_calls),
            ),
        )
        return FinalAnswerController.outcome_from_result(
            result=result,
            citations=(),
            citation_repair_count=0,
            stop_reason=stop_reason,
        )


def runtime_refusal_message(stop_detail: str) -> str:
    """Return a bounded user-facing refusal reason without leaking raw internals."""

    if stop_detail == "deadline_exhausted":
        return (
            "Runtime deadline was exhausted before enough reliable evidence could "
            "be assembled."
        )
    if stop_detail == "reranking_failed":
        return (
            "Evidence reranking failed, so the agent refused to answer without "
            "reliable ranked sources."
        )
    if stop_detail == "required_evidence_missing":
        return "Required evidence was not found in the available project sources."
    if stop_detail == "completed_tool_replay_prevented":
        return (
            "Runtime checkpoint recovery prevented a duplicate completed tool "
            "execution, so the agent refused instead of replaying retrieval."
        )
    if stop_detail == "tool_budget_exhausted":
        return (
            "Runtime tool budget was exhausted before enough reliable evidence "
            "could be assembled."
        )
    if stop_detail == "tool_execution_failed":
        return (
            "Tool execution failed before the agent could assemble valid "
            "tool-backed citations."
        )
    if stop_detail in {"evidence_exhausted", "insufficient_evidence"}:
        return "Runtime evidence state refused final generation due to insufficient evidence."
    return "Runtime evidence state refused final generation."


def runtime_refusal_message_for_request(
    request: FinalAnswerRequest,
    stop_detail: str,
) -> str:
    """Return refusal text, preserving safe legacy tool-failure details when useful."""
    if stop_detail == "reranking_failed":
        for record in reversed((*request.workflow_steps, *request.tool_calls)):
            error = str(getattr(record, "error", "") or "").strip()
            if error and (
                "rerank" in error.lower()
                or "重排序" in error
                or "重排" in error
            ):
                return error
    if stop_detail == "required_evidence_missing":
        refusal_reason = str(
            request.latency_trace.values.get("runtime_tool_refusal_reason", "") or ""
        ).strip()
        if refusal_reason:
            return refusal_reason
    return runtime_refusal_message(stop_detail)


def generate_hyde_vector_query(
    *,
    canonical_task: str,
    provider: ChatModelProvider | None,
    latency_trace: LatencyTrace,
) -> str:
    task = " ".join((canonical_task or "").split())
    if not task:
        latency_trace.set_value("hyde_generated", False)
        latency_trace.set_value("hyde_used_for_vector", False)
        latency_trace.set_value("hyde_reason", "empty_task")
        return ""
    if provider is None:
        latency_trace.set_value("hyde_generated", False)
        latency_trace.set_value("hyde_used_for_vector", False)
        latency_trace.set_value("hyde_reason", "provider_unavailable")
        return ""
    if str(getattr(provider, "provider_name", "")).casefold() in {"", "deterministic", "fake", "local"}:
        latency_trace.set_value("hyde_generated", False)
        latency_trace.set_value("hyde_used_for_vector", False)
        latency_trace.set_value("hyde_reason", "provider_unavailable")
        return ""
    try:
        started = time.perf_counter()
        result = provider.generate(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "Generate a concise hypothetical evidence passage for retrieval only. "
                        "Do not include citations. Do not claim it is real evidence. "
                        "Use technical terms likely to appear in source documents. "
                        "Return plain text only, under 120 words."
                    ),
                ),
                ChatMessage(role="user", content=task),
            ]
        )
        hyde_duration_ms = (time.perf_counter() - started) * 1000.0
        latency_trace.add_duration("planner_latency_ms", hyde_duration_ms)
        latency_trace.add_duration("hyde_latency_ms", hyde_duration_ms)
    except Exception:
        latency_trace.set_value("hyde_generated", False)
        latency_trace.set_value("hyde_used_for_vector", False)
        latency_trace.set_value("hyde_reason", "provider_error")
        return ""
    passage = " ".join((result.answer or "").split())
    if not passage:
        latency_trace.set_value("hyde_generated", False)
        latency_trace.set_value("hyde_used_for_vector", False)
        latency_trace.set_value("hyde_reason", "empty")
        return ""
    latency_trace.set_value("hyde_generated", True)
    latency_trace.set_value("hyde_used_for_vector", True)
    latency_trace.set_value("hyde_reason", "generated")
    latency_trace.set_value("hyde_model", f"{result.provider}/{result.model_name}")
    return f"{task}\n\nHypothetical evidence for vector retrieval only:\n{passage[:1200]}"




def safe_tool_result_payload(
    tool_result: AgentToolResult,
    merged_sources: list[AgentSourceReference],
) -> dict[str, object]:
    source_index_by_id = {
        source.source_id: index for index, source in enumerate(merged_sources, start=1)
    }
    safe_sources: list[dict[str, object]] = []
    for source in tool_result.sources[:TOOL_RESULT_MAX_SOURCES]:
        citation_id = source_index_by_id.get(source.source_id)
        safe_sources.append(
            {
                "citation_id": citation_id,
                "source_id": source.source_id,
                "title": truncate_text(source.title, 120),
                "source_type": source.source_type,
                "chunk_id": source.chunk_id,
                "chunk_index": source.chunk_index,
                "chunk_type": source.chunk_type,
                "image_url": source.image_url,
                "caption": truncate_text(source.caption or "", 120) or None,
                "page_number": source.page_number,
                "score": round(float(source.score), 4) if source.score is not None else None,
                "snippet": truncate_text(source.content or "", TOOL_RESULT_SNIPPET_LIMIT),
            }
        )
    return {
        "tool_name": tool_result.tool_name,
        "succeeded": tool_result.call.succeeded,
        "refused": tool_result.refused,
        "error": tool_result.call.error,
        "summary": tool_result.call.output_summary,
        "sources": safe_sources,
    }


def is_reranking_failure(call: AgentToolCallRecord) -> bool:
    if call.succeeded:
        return False
    text = " ".join(
        part
        for part in [call.error, call.output_summary]
        if isinstance(part, str) and part
    )
    return "重排序失效" in text or "reranking failed" in text.casefold()


def skipped_tool_result_payload(
    *,
    reason: str,
    sources: list[AgentSourceReference],
) -> dict[str, object]:
    return {
        "succeeded": False,
        "refused": True,
        "error": reason,
        "instruction": (
            "Do not repeat equivalent search calls. If the listed sources are "
            "sufficient, produce the final answer with citations; otherwise refuse "
            "safely based on insufficient evidence."
        ),
        "sources": safe_sources_payload(sources),
    }


def safe_sources_payload(
    sources: list[AgentSourceReference],
) -> list[dict[str, object]]:
    safe_sources: list[dict[str, object]] = []
    for index, source in enumerate(sources[:TOOL_RESULT_MAX_SOURCES], start=1):
        safe_sources.append(
            {
                "citation_id": index,
                "source_id": source.source_id,
                "title": truncate_text(source.title, 120),
                "source_type": source.source_type,
                "chunk_id": source.chunk_id,
                "chunk_index": source.chunk_index,
                "chunk_type": source.chunk_type,
                "image_url": source.image_url,
                "caption": truncate_text(source.caption or "", 120) or None,
                "page_number": source.page_number,
                "score": round(float(source.score), 4) if source.score is not None else None,
                "snippet": truncate_text(source.content or "", TOOL_RESULT_SNIPPET_LIMIT),
            }
        )
    return safe_sources


def tool_message_from_payload(
    tool_call: ChatToolCall,
    payload: dict[str, object],
) -> ChatMessage:
    return ChatMessage(
        role="tool",
        content=json.dumps(payload, ensure_ascii=False),
        tool_call_id=tool_call.id,
    )


def tool_query_from_call(tool_call: ChatToolCall, default_query: str) -> str:
    query = tool_call.arguments.get("query")
    if isinstance(query, str) and query.strip():
        return query.strip()
    return default_query


def safe_tool_input_summary(tool_call: ChatToolCall) -> str:
    query = tool_call.arguments.get("query", "")
    return f"query={truncate_text(str(query))}"


def normalize_tool_query(query: str) -> str:
    return " ".join(tokenize_tool_query(query))


def tokenize_tool_query(query: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", query.casefold())
    normalized_tokens: list[str] = []
    for token in tokens:
        if token in {"rfc", "rockfilled"}:
            normalized_tokens.extend(["rock", "filled", "concrete"])
        elif token == "scc":
            normalized_tokens.extend(["self", "compacting", "concrete"])
        else:
            normalized_tokens.append(token)
    return normalized_tokens


def is_near_duplicate_tool_query(
    normalized_query: str,
    previous_queries: Sequence[str],
) -> bool:
    current_tokens = set(normalized_query.split())
    if not current_tokens:
        return False
    for previous_query in previous_queries:
        previous_tokens = set(previous_query.split())
        if not previous_tokens:
            continue
        overlap = len(current_tokens & previous_tokens)
        union = len(current_tokens | previous_tokens)
        if union and overlap / union >= TOOL_CALLING_NEAR_DUPLICATE_THRESHOLD:
            return True
    return False


def executable_tool_call_ids(
    tool_calls: Sequence[ChatToolCall],
    *,
    previous_tool_queries: Sequence[str],
    sources_available: bool,
    preferred_tool_name: str | None = None,
) -> set[str]:
    if sources_available:
        return set()

    candidates: list[ChatToolCall] = []
    for tool_call in tool_calls:
        if tool_call.name not in TEXT_TOOL_NAMES:
            candidates.append(tool_call)
            continue
        query = normalize_tool_query(tool_query_from_call(tool_call, default_query=""))
        if is_near_duplicate_tool_query(query, previous_tool_queries):
            continue
        candidates.append(tool_call)

    candidates.sort(
        key=lambda call: (
            0 if call.name == preferred_tool_name else 1,
            TOOL_CALLING_PREFERRED_TOOL_ORDER.get(call.name, 99),
        )
    )
    return {
        call.id
        for call in candidates[:TOOL_CALLING_MAX_EXECUTED_TOOLS_PER_ITERATION]
    }


def skip_reason_for_tool_call(*, sources_available: bool) -> str:
    if sources_available:
        return "existing evidence available; tool call skipped"
    return "per-iteration search tool budget reached"


def failed_tool_call_result(
    tool_name: str,
    input_summary: str,
    error: str,
) -> AgentToolResult:
    return AgentToolResult(
        tool_name=tool_name,
        call=AgentToolCallRecord(
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=error,
            succeeded=False,
            error=error,
        ),
        refused=True,
        refusal_reason=error,
    )


def result_from_final_generation_failure(
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
    return build_final_generation_failure_result(
        question=question,
        sources=sources,
        search_results=search_results,
        tool_calls=tool_calls,
        workflow_steps=workflow_steps,
        llm_call_count=llm_call_count,
        repeated_query_count=repeated_query_count,
        near_duplicate_query_count=near_duplicate_query_count,
        skipped_tool_call_count=skipped_tool_call_count,
        executed_tool_call_count=executed_tool_call_count,
        citation_repair_count=citation_repair_count,
        runtime_state=runtime_state,
        latency_trace=latency_trace,
        error=error,
    )


def result_from_tool_calling_loop(
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
    runtime_state: AgentRuntimeState | None = None,
    latency_trace: dict[str, object],
    image_analysis: dict[str, object] | None = None,
) -> AgentQueryResult:
    return build_tool_calling_result(
        question=question,
        answer=answer,
        tool_calls=tool_calls,
        sources=sources,
        search_results=search_results,
        citations=citations,
        refused=refused,
        refusal_reason=refusal_reason,
        workflow_steps=workflow_steps,
        llm_call_count=llm_call_count,
        repeated_query_count=repeated_query_count,
        near_duplicate_query_count=near_duplicate_query_count,
        skipped_tool_call_count=skipped_tool_call_count,
        executed_tool_call_count=executed_tool_call_count,
        citation_repair_count=citation_repair_count,
        runtime_state=runtime_state,
        latency_trace=latency_trace,
        image_analysis=image_analysis,
    )


def outcome_from_tool_calling_loop(
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
    runtime_state: AgentRuntimeState | None = None,
    latency_trace: dict[str, object],
    stop_reason: RuntimeStopReason,
    image_analysis: dict[str, object] | None = None,
) -> FinalAnswerOutcome:
    result = result_from_tool_calling_loop(
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
        repeated_query_count=repeated_query_count,
        near_duplicate_query_count=near_duplicate_query_count,
        skipped_tool_call_count=skipped_tool_call_count,
        executed_tool_call_count=executed_tool_call_count,
        citation_repair_count=citation_repair_count,
        runtime_state=runtime_state,
        latency_trace=latency_trace,
        image_analysis=image_analysis,
    )
    return FinalAnswerController.outcome_from_result(
        result=result,
        citations=citations,
        citation_repair_count=citation_repair_count,
        stop_reason=stop_reason,
    )


def apply_runtime_diagnostics(
    latency_trace: LatencyTrace,
    runtime_state: AgentRuntimeState,
) -> None:
    for key, value in runtime_state.diagnostics().items():
        latency_trace.set_value(key, value)


def semantic_cache_tool_for_identity(evidence_identity: Any) -> str:
    intent_key = str(getattr(evidence_identity, "intent_key", "") or "")
    if intent_key == "visual_evidence":
        return "search_figures"
    if intent_key == "table_evidence":
        return "search_tables"
    return "hybrid_search_knowledge"


def tool_call_record_to_dict(record: AgentToolCallRecord) -> dict[str, object]:
    return {
        "tool_name": record.tool_name,
        "input_summary": truncate_text(record.input_summary, 160),
        "output_summary": truncate_text(record.output_summary, 180),
        "succeeded": record.succeeded,
        "error": truncate_text(record.error or "", 180) or None,
        "step_id": record.step_id,
    }


def source_reference_to_dict(source: AgentSourceReference) -> dict[str, object]:
    return {
        "source_id": source.source_id,
        "title": truncate_text(source.title, 160),
        "source_type": source.source_type,
        "status": source.status,
        "trust_level": source.trust_level,
        "fulltext_permission": source.fulltext_permission,
        "document_id": source.document_id,
        "chunk_id": source.chunk_id,
        "chunk_index": source.chunk_index,
        "url": source.url,
        "doi": source.doi,
        "content": truncate_text(source.content or "", TOOL_RESULT_SNIPPET_LIMIT),
        "score": source.score,
        "chunk_type": source.chunk_type,
        "source_image_path": source.source_image_path,
        "image_url": source.image_url,
        "caption": truncate_text(source.caption or "", 120) or None,
        "page_number": source.page_number,
        "table_content": truncate_text(source.table_content or "", 200) or None,
    }


def source_reference_from_dict(values: dict[str, object]) -> AgentSourceReference:
    return AgentSourceReference(
        source_id=str(values.get("source_id") or ""),
        title=str(values.get("title") or ""),
        source_type=str(values.get("source_type") or "unknown"),
        status=optional_str(values.get("status")),
        trust_level=optional_str(values.get("trust_level")),
        fulltext_permission=optional_str(values.get("fulltext_permission")),
        document_id=optional_int(values.get("document_id")),
        chunk_id=optional_int(values.get("chunk_id")),
        chunk_index=optional_int(values.get("chunk_index")),
        url=optional_str(values.get("url")),
        doi=optional_str(values.get("doi")),
        content=optional_str(values.get("content")),
        score=optional_float(values.get("score")),
        chunk_type=str(values.get("chunk_type") or "text"),
        source_image_path=optional_str(values.get("source_image_path")),
        image_url=optional_str(values.get("image_url")),
        caption=optional_str(values.get("caption")),
        page_number=optional_int(values.get("page_number")),
        table_content=optional_str(values.get("table_content")),
    )


def result_from_cached_evidence(
    *,
    question: str,
    search_results: list[AgentSearchItem],
    sources: list[AgentSourceReference],
    tool_calls: list[AgentToolCallRecord],
    workflow_steps: list[AgentToolCallRecord],
    chat_model_provider: ChatModelProvider,
    history: Sequence[str] | None,
    final_answer_strategy: ToolCallingFinalAnswerStrategy,
    runtime_state: AgentRuntimeState,
    latency_trace: LatencyTrace,
) -> AgentQueryResult:
    return FinalAnswerController(
        chat_model_provider,
        answer_messages=evidence_answer_messages,
        repair_messages=citation_repair_messages,
        citation_extractor=extract_citations,
    ).from_cached_evidence(
        question=question,
        search_results=search_results,
        sources=sources,
        tool_calls=tool_calls,
        workflow_steps=workflow_steps,
        history=history,
        strategy=final_answer_strategy,
        runtime_state=runtime_state,
        latency_trace=latency_trace,
    ).result


def optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def optional_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
