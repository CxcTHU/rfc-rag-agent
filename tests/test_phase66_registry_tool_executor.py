import ast
from dataclasses import dataclass
from pathlib import Path

from app.services.agent.runtime_contracts import ToolExecutionRequest
from app.services.agent.tool_contracts import (
    AnalyzeUserImageArguments,
    RetrievalArguments,
    ToolArguments,
    ToolExecutionContext,
)
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.tool_models import AgentToolCallRecord, AgentToolResult
from app.services.agent.tool_registry import tool_registry_from_adapters
from app.services.generation.chat_model import ChatToolCall


@dataclass
class RecordedCall:
    arguments: ToolArguments
    context: ToolExecutionContext


class RecordingAdapter:
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        self.calls: list[RecordedCall] = []

    def execute(
        self,
        arguments: ToolArguments,
        context: ToolExecutionContext,
    ) -> AgentToolResult:
        self.calls.append(RecordedCall(arguments=arguments, context=context))
        return AgentToolResult(
            tool_name=self.tool_name,
            call=AgentToolCallRecord(
                tool_name=self.tool_name,
                input_summary="recorded",
                output_summary="selected=1",
                succeeded=True,
            ),
        )


def make_registry(recording_adapter: RecordingAdapter):
    return tool_registry_from_adapters(
        hybrid_search=RecordingAdapter("hybrid_search_knowledge"),
        figure_search=RecordingAdapter("search_figures"),
        table_search=recording_adapter,
        user_image_analysis=RecordingAdapter("analyze_user_image"),
    )


def make_request(
    name: str,
    arguments: dict[str, object],
    *,
    image_path: str | None = None,
) -> ToolExecutionRequest:
    return ToolExecutionRequest(
        call=ChatToolCall(id="tool-1", name=name, arguments=arguments),
        default_query="default question",
        image_path=image_path,
    )


def test_executor_dispatches_through_registered_adapter() -> None:
    recording_adapter = RecordingAdapter("search_tables")
    registry = make_registry(recording_adapter)

    outcome = ToolExecutor(registry).execute(
        make_request("search_tables", {"query": "codes"})
    )

    assert recording_adapter.calls[0].arguments == RetrievalArguments(query="codes", top_k=8)
    assert outcome.result.tool_name == "search_tables"


def test_executor_applies_spec_default_limit() -> None:
    figure_adapter = RecordingAdapter("search_figures")
    registry = tool_registry_from_adapters(
        hybrid_search=RecordingAdapter("hybrid_search_knowledge"),
        figure_search=figure_adapter,
        table_search=RecordingAdapter("search_tables"),
        user_image_analysis=RecordingAdapter("analyze_user_image"),
    )

    ToolExecutor(registry).execute(make_request("search_figures", {"query": "figure 3"}))

    assert figure_adapter.calls[0].arguments == RetrievalArguments(query="figure 3", top_k=4)


def test_executor_builds_image_arguments_from_request_context() -> None:
    image_adapter = RecordingAdapter("analyze_user_image")
    registry = tool_registry_from_adapters(
        hybrid_search=RecordingAdapter("hybrid_search_knowledge"),
        figure_search=RecordingAdapter("search_figures"),
        table_search=RecordingAdapter("search_tables"),
        user_image_analysis=image_adapter,
    )

    ToolExecutor(registry).execute(
        make_request(
            "analyze_user_image",
            {"question": "describe"},
            image_path="data/user_uploads/sample.png",
        )
    )

    assert image_adapter.calls[0].arguments == AnalyzeUserImageArguments(
        image_path="data/user_uploads/sample.png",
        question="describe",
    )


def test_tool_executor_has_no_name_branch_dispatch() -> None:
    source = Path("app/services/agent/tool_executor.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "ALLOWED_TOOL_NAMES" not in source
    assert not any(
        isinstance(node, ast.FunctionDef) and node.name == "_dispatch"
        for node in ast.walk(tree)
    )
