from __future__ import annotations

from app.services.agent.runtime_contracts import ToolExecutionRequest
from app.services.agent.runtime_events import RuntimeEventBus
from app.services.retrieval.runtime import RetrievalAction
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.tool_contracts import (
    AnalyzeUserImageArguments,
    RetrievalArguments,
    ToolArguments,
    ToolExecutionContext,
)
from app.services.agent.tools import AgentToolCallRecord, AgentToolResult
from app.services.generation.chat_model import ChatToolCall


class RecordingAdapter:
    def __init__(self, owner: "RecordingToolbox", tool_name: str) -> None:
        self.owner = owner
        self.tool_name = tool_name

    def execute(
        self,
        arguments: ToolArguments,
        context: ToolExecutionContext,
    ) -> AgentToolResult:
        if isinstance(arguments, RetrievalArguments):
            return self.owner._result(
                self.tool_name,
                arguments.query,
                arguments.top_k or 0,
            )
        if isinstance(arguments, AnalyzeUserImageArguments):
            return self.owner._result(
                self.tool_name,
                arguments.question,
                0,
            )
        raise TypeError("unsupported arguments")


class RecordingToolbox:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self._hybrid_adapter = RecordingAdapter(self, "hybrid_search_knowledge")
        self._figure_adapter = RecordingAdapter(self, "search_figures")
        self._table_adapter = RecordingAdapter(self, "search_tables")
        self._user_image_adapter = RecordingAdapter(self, "analyze_user_image")

    def search_figures(self, query: str, *, top_k: int) -> AgentToolResult:
        return self._result("search_figures", query, top_k)

    def search_tables(self, query: str, *, top_k: int) -> AgentToolResult:
        return self._result("search_tables", query, top_k)

    def hybrid_search_knowledge(self, query: str, *, top_k: int) -> AgentToolResult:
        return self._result("hybrid_search_knowledge", query, top_k)

    def _result(self, tool_name: str, query: str, top_k: int) -> AgentToolResult:
        self.calls.append((tool_name, query, top_k))
        return AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=f"query={query}",
                output_summary="selected=1",
                succeeded=True,
            ),
        )


def tool_call(name: str, *, call_id: str = "tool-1") -> ChatToolCall:
    return ChatToolCall(id=call_id, name=name, arguments={"query": "密实度参数"})


def test_executor_rejects_unknown_tool_without_calling_toolbox() -> None:
    toolbox = RecordingToolbox()

    outcome = ToolExecutor.for_toolbox(toolbox).execute(
        ToolExecutionRequest(call=tool_call("delete_source"), default_query="q")
    )

    assert outcome.result.call.succeeded is False
    assert outcome.error_category == "unsupported_tool"
    assert toolbox.calls == []


def test_executor_does_not_repeat_a_completed_tool_call_after_resume() -> None:
    toolbox = RecordingToolbox()

    outcome = ToolExecutor.for_toolbox(toolbox).execute(
        ToolExecutionRequest(
            call=tool_call("search_tables"),
            default_query="q",
            completed_tool_ids=frozenset({"tool-1"}),
        )
    )

    assert outcome.skipped_completed_tool is True
    assert outcome.error_category == "completed_tool"
    assert toolbox.calls == []


def test_executor_preserves_required_tool_result_and_event_order() -> None:
    toolbox = RecordingToolbox()
    received = []
    bus = RuntimeEventBus(run_id="run-1")
    bus.subscribe(received.append)

    outcome = ToolExecutor.for_toolbox(toolbox, event_bus=bus).execute(
        ToolExecutionRequest(call=tool_call("search_tables"), default_query="q", iteration=2)
    )

    assert outcome.result.tool_name == "search_tables"
    assert outcome.result.call.step_id == "tool-1"
    assert [event.name for event in received] == ["tool_call_start", "tool_call_result"]
    assert received[0].payload["iteration"] == 2
    assert received[1].payload["succeeded"] is True


class PassthroughRuntime:
    def ground_tool_call(self, call, *, state, default_query):
        return call, state


def test_executor_runs_short_loop_with_grounded_runtime_call() -> None:
    toolbox = RecordingToolbox()
    bus = RuntimeEventBus(run_id="run-1")
    received = []
    bus.subscribe(received.append)

    outcome = ToolExecutor.for_toolbox(toolbox, event_bus=bus).execute_short_loop(
        runtime=PassthroughRuntime(),
        runtime_state=object(),
        retrieval_action=RetrievalAction(required_tool="search_tables"),
        canonical_task="参数表",
        default_query="查询参数表",
    )

    assert outcome.result.call.step_id == "runtime-retrieval-1"
    assert toolbox.calls[0][0] == "search_tables"
    assert [event.name for event in received] == ["tool_call_start", "tool_call_result"]


def test_short_loop_propagates_iteration_and_completed_tool_guard() -> None:
    toolbox = RecordingToolbox()
    bus = RuntimeEventBus(run_id="run-1")
    received = []
    bus.subscribe(received.append)

    outcome = ToolExecutor.for_toolbox(toolbox, event_bus=bus).execute_short_loop(
        runtime=PassthroughRuntime(),
        runtime_state=object(),
        retrieval_action=RetrievalAction(required_tool="search_tables"),
        canonical_task="参数表",
        default_query="查询参数表",
        iteration=2,
        completed_tool_ids=frozenset({"runtime-retrieval-2"}),
    )

    assert outcome.skipped_completed_tool is True
    assert outcome.error_category == "completed_tool"
    assert outcome.result.call.step_id == "runtime-retrieval-2"
    assert toolbox.calls == []
    assert received[0].payload["iteration"] == 2
