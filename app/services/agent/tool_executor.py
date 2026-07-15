"""Safe execution boundary for the Runtime-owned retrieval tools."""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import Any, Protocol

from app.services.agent.runtime_contracts import ToolExecutionOutcome, ToolExecutionRequest
from app.services.agent.runtime_events import RuntimeEventBus, publish_tool_call_result
from app.services.agent.tools import AgentToolCallRecord, AgentToolResult, truncate_text
from app.core.structured_logging import log_event
from app.services.generation.chat_model import ChatToolCall
from app.services.retrieval.runtime import retrieval_runtime_result_limit
from app.services.retrieval.runtime import retrieval_tool_for_action


ALLOWED_TOOL_NAMES = frozenset(
    {"hybrid_search_knowledge", "search_figures", "search_tables"}
)
agent_logger = logging.getLogger("rfc_rag_agent.agent")


class RetrievalToolbox(Protocol):
    def hybrid_search_knowledge(self, query: str, *, top_k: int) -> AgentToolResult: ...

    def search_figures(self, query: str, *, top_k: int) -> AgentToolResult: ...

    def search_tables(self, query: str, *, top_k: int) -> AgentToolResult: ...


class ToolExecutor:
    def __init__(
        self,
        toolbox: RetrievalToolbox,
        *,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self._toolbox = toolbox
        self._event_bus = event_bus

    def execute(self, request: ToolExecutionRequest) -> ToolExecutionOutcome:
        started = time.perf_counter()
        if (
            request.deadline_monotonic is not None
            and started >= request.deadline_monotonic
        ):
            return self._failed_outcome(request, "deadline_exhausted", "runtime deadline exhausted")
        if request.call.id and request.call.id in request.completed_tool_ids:
            return self._failed_outcome(
                request,
                "completed_tool",
                "tool call already completed in the resumed runtime",
                skipped_completed_tool=True,
            )
        if request.call.name not in ALLOWED_TOOL_NAMES:
            return self._failed_outcome(
                request,
                "unsupported_tool",
                f"Tool {request.call.name} is not allowed.",
            )
        if request.call.name in request.forbidden_tools:
            return self._failed_outcome(
                request,
                "forbidden_tool",
                f"Tool {request.call.name} is forbidden by explicit user intent.",
            )

        query = tool_query_from_call(request)
        self._emit_start(request, query)
        result = self._dispatch(request.call.name, query)
        result = replace(result, call=replace(result.call, step_id=request.call.id))
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._emit_result(request, result)
        return ToolExecutionOutcome(
            result=result,
            elapsed_ms=elapsed_ms,
            error_category=None
            if result.call.succeeded
            else tool_error_category(result),
        )

    def execute_short_loop(
        self,
        *,
        runtime: Any,
        runtime_state: Any,
        retrieval_action: Any,
        canonical_task: str,
        default_query: str,
        iteration: int = 1,
        completed_tool_ids: frozenset[str] = frozenset(),
        deadline_monotonic: float | None = None,
    ) -> ToolExecutionOutcome:
        """Execute the Runtime-owned retrieval action without model tool planning."""
        synthetic_call = ChatToolCall(
            id=f"runtime-retrieval-{iteration}",
            name=retrieval_tool_for_action(retrieval_action),
            arguments={"query": canonical_task},
        )
        grounded_call, _ = runtime.ground_tool_call(
            synthetic_call,
            state=runtime_state,
            default_query=default_query,
        )
        return self.execute(
            ToolExecutionRequest(
                call=grounded_call,
                default_query=default_query,
                forbidden_tools=tuple(retrieval_action.forbidden_tools),
                iteration=iteration,
                completed_tool_ids=completed_tool_ids,
                deadline_monotonic=deadline_monotonic,
            )
        )

    def _dispatch(self, tool_name: str, query: str) -> AgentToolResult:
        requested_top_k = retrieval_runtime_result_limit(tool_name)
        if tool_name == "search_figures":
            return self._toolbox.search_figures(query, top_k=requested_top_k)
        if tool_name == "search_tables":
            return self._toolbox.search_tables(query, top_k=requested_top_k)
        return self._toolbox.hybrid_search_knowledge(query, top_k=requested_top_k)

    def _failed_outcome(
        self,
        request: ToolExecutionRequest,
        error_category: str,
        error: str,
        *,
        skipped_completed_tool: bool = False,
    ) -> ToolExecutionOutcome:
        result = AgentToolResult(
            tool_name=request.call.name,
            call=AgentToolCallRecord(
                tool_name=request.call.name,
                input_summary=safe_tool_input_summary(request),
                output_summary=error,
                succeeded=False,
                error=error,
                step_id=request.call.id,
            ),
            refused=True,
            refusal_reason=error,
        )
        self._emit_result(request, result)
        return ToolExecutionOutcome(
            result=result,
            elapsed_ms=0.0,
            error_category=error_category,
            skipped_completed_tool=skipped_completed_tool,
        )

    def _emit_start(self, request: ToolExecutionRequest, query: str) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(
            "retrieval",
            "tool_call_start",
            {
                "iteration": request.iteration,
                "step_id": request.call.id,
                "tool_name": request.call.name,
                "input_summary": f"query={truncate_text(query)}",
            },
        )

    def _emit_result(self, request: ToolExecutionRequest, result: AgentToolResult) -> None:
        log_event(
            agent_logger,
            "tool_call_executed",
            mode="tool_calling_agent",
            tool_name=result.tool_name,
            iteration=request.iteration,
            succeeded=result.call.succeeded,
            selected_count=len(result.search_results),
        )
        if self._event_bus is None:
            return
        publish_tool_call_result(
            self._event_bus,
            iteration=request.iteration,
            record=result.call,
            selected_count=len(result.search_results),
        )


def tool_query_from_call(request: ToolExecutionRequest) -> str:
    query = request.call.arguments.get("query")
    if isinstance(query, str) and query.strip():
        return query.strip()
    return request.default_query


def safe_tool_input_summary(request: ToolExecutionRequest) -> str:
    return f"query={truncate_text(tool_query_from_call(request))}"


def tool_error_category(result: AgentToolResult) -> str:
    """Classify safe high-level tool failures for runtime evidence policy."""
    error_text = " ".join(
        str(value or "")
        for value in (
            getattr(result.call, "error", None),
            getattr(result.call, "output_summary", None),
            getattr(result, "refusal_reason", None),
        )
    ).lower()
    if "rerank" in error_text or "重排序" in error_text or "重排" in error_text:
        return "reranking_failed"
    return "tool_execution_failed"
