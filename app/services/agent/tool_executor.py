"""Safe execution boundary for the Runtime-owned retrieval tools."""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from collections.abc import Collection
from typing import Protocol

from pydantic import ValidationError

from app.services.agent.tool_contracts import (
    AnalyzeUserImageArguments,
    RetrievalArguments,
    ToolAdapter,
    ToolArguments,
    ToolExecutionContext,
)
from app.services.agent.runtime_contracts import ToolExecutionOutcome, ToolExecutionRequest
from app.services.agent.runtime_events import RuntimeEventBus, publish_tool_call_result
from app.services.agent.tool_models import AgentToolCallRecord, AgentToolResult
from app.services.agent.tool_registry import (
    ToolRegistry,
    UnsupportedToolError,
    tool_registry_from_adapters,
)
from app.services.agent.tools import truncate_text
from app.core.structured_logging import log_event
from app.services.generation.chat_model import ChatToolCall
from app.services.retrieval.runtime import retrieval_tool_for_action


agent_logger = logging.getLogger("rfc_rag_agent.agent")


class ToolboxAdapters(Protocol):
    _hybrid_adapter: ToolAdapter
    _figure_adapter: ToolAdapter
    _table_adapter: ToolAdapter
    _user_image_adapter: ToolAdapter


class GroundingRuntime(Protocol):
    def ground_tool_call(
        self,
        call: ChatToolCall,
        *,
        state: object,
        default_query: str,
    ) -> tuple[ChatToolCall, object]:
        ...


class RetrievalActionLike(Protocol):
    forbidden_tools: Collection[str]


class ToolboxMethodAdapter:
    def __init__(
        self,
        toolbox: object,
        *,
        tool_name: str,
        method_name: str,
        default_top_k: int,
    ) -> None:
        self._toolbox = toolbox
        self._tool_name = tool_name
        self._method_name = method_name
        self._default_top_k = default_top_k

    def execute(
        self,
        arguments: ToolArguments,
        context: ToolExecutionContext,
    ) -> AgentToolResult:
        method = getattr(self._toolbox, self._method_name)
        if isinstance(arguments, AnalyzeUserImageArguments):
            return method(
                arguments.image_path,
                arguments.question,
                top_k=self._default_top_k,
            )
        if isinstance(arguments, RetrievalArguments):
            return method(
                arguments.query,
                top_k=arguments.top_k or self._default_top_k,
            )
        raise TypeError(f"unsupported arguments for {self._tool_name}")


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus

    @classmethod
    def for_toolbox(
        cls,
        toolbox: ToolboxAdapters,
        *,
        event_bus: RuntimeEventBus | None = None,
    ) -> ToolExecutor:
        return cls(
            tool_registry_from_adapters(
                hybrid_search=ToolboxMethodAdapter(
                    toolbox,
                    tool_name="hybrid_search_knowledge",
                    method_name="hybrid_search_knowledge",
                    default_top_k=8,
                ),
                figure_search=ToolboxMethodAdapter(
                    toolbox,
                    tool_name="search_figures",
                    method_name="search_figures",
                    default_top_k=4,
                ),
                table_search=ToolboxMethodAdapter(
                    toolbox,
                    tool_name="search_tables",
                    method_name="search_tables",
                    default_top_k=8,
                ),
                user_image_analysis=ToolboxMethodAdapter(
                    toolbox,
                    tool_name="analyze_user_image",
                    method_name="analyze_user_image",
                    default_top_k=4,
                ),
            ),
            event_bus=event_bus,
        )

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
        try:
            spec = self._registry.require(request.call.name)
        except UnsupportedToolError:
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

        raw_arguments = raw_tool_arguments(request, default_top_k=spec.default_result_limit)
        try:
            arguments = self._registry.validate_arguments(spec.name, raw_arguments)
        except ValidationError as exc:
            return self._failed_outcome(
                request,
                "invalid_tool_arguments",
                f"Invalid arguments for {request.call.name}: {exc.errors()[0]['msg']}",
            )

        self._emit_start(request)
        result = spec.adapter.execute(
            arguments,
            ToolExecutionContext(
                run_id="",
                step_id=request.call.id,
                iteration=request.iteration,
                deadline_monotonic=request.deadline_monotonic,
                cancelled=False,
            ),
        )
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
        runtime: GroundingRuntime,
        runtime_state: object,
        retrieval_action: RetrievalActionLike,
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

    def _emit_start(self, request: ToolExecutionRequest) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(
            "retrieval",
            "tool_call_start",
            {
                "iteration": request.iteration,
                "step_id": request.call.id,
                "tool_name": request.call.name,
                "input_summary": safe_tool_input_summary(request),
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


def raw_tool_arguments(
    request: ToolExecutionRequest,
    *,
    default_top_k: int,
) -> dict[str, object]:
    raw = dict(request.call.arguments)
    if request.call.name == "analyze_user_image":
        raw.setdefault("question", request.default_query)
        if request.image_path is not None:
            raw.setdefault("image_path", request.image_path)
        return raw

    raw.setdefault("query", tool_query_from_call(request))
    raw.setdefault("top_k", default_top_k)
    return raw


def safe_tool_input_summary(request: ToolExecutionRequest) -> str:
    if request.call.name == "analyze_user_image":
        question = request.call.arguments.get("question")
        if not isinstance(question, str) or not question.strip():
            question = request.default_query
        return f"question={truncate_text(question)}; image_path=<user_upload>"
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
