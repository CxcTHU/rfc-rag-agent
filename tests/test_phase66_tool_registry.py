from __future__ import annotations

import pytest

from app.services.agent.tool_contracts import (
    AnalyzeUserImageArguments,
    RetrievalArguments,
    ToolArguments,
    ToolExecutionContext,
    ToolSpec,
)
from app.services.agent.tool_registry import (
    TEXT_TOOL_NAMES,
    ToolRegistry,
    default_tool_registry,
)
from app.services.agent.tool_calling_service import tool_calling_tool_definitions
from app.services.agent.tools import AgentToolResult


class FakeAdapter:
    def execute(
        self,
        arguments: ToolArguments,
        context: ToolExecutionContext,
    ) -> AgentToolResult:
        raise AssertionError("schema projection should not execute adapters")


@pytest.fixture
def fake_adapter() -> FakeAdapter:
    return FakeAdapter()


@pytest.fixture
def default_registry() -> ToolRegistry:
    return default_tool_registry(adapter=FakeAdapter())


def test_registry_rejects_duplicate_tool_names(fake_adapter: FakeAdapter) -> None:
    spec = ToolSpec(
        name="hybrid_search_knowledge",
        arguments_model=RetrievalArguments,
        adapter=fake_adapter,
        default_result_limit=8,
        timeout_seconds=20.0,
        required_permissions=frozenset({"read:knowledge"}),
        safe_event_label="knowledge_search",
        description="Search RFC knowledge.",
    )

    with pytest.raises(ValueError, match="duplicate tool"):
        ToolRegistry((spec, spec))


def test_default_registry_contains_each_production_tool_once(
    default_registry: ToolRegistry,
) -> None:
    assert default_registry.names == (
        "hybrid_search_knowledge",
        "search_figures",
        "search_tables",
        "analyze_user_image",
    )


def test_registry_projects_chat_tool_definitions(
    default_registry: ToolRegistry,
) -> None:
    definitions = default_registry.chat_tool_definitions(
        available_names=default_registry.names
    )

    assert [definition.function.name for definition in definitions] == list(
        default_registry.names
    )
    assert definitions[0].function.parameters["additionalProperties"] is False
    assert definitions[-1].function.parameters["required"] == [
        "image_path",
        "question",
    ]


def test_text_projection_excludes_image_tool(default_registry: ToolRegistry) -> None:
    definitions = default_registry.chat_tool_definitions(available_names=TEXT_TOOL_NAMES)

    assert [definition.function.name for definition in definitions] == [
        "hybrid_search_knowledge",
        "search_figures",
        "search_tables",
    ]


def test_service_helper_uses_registry_text_projection() -> None:
    definitions = tool_calling_tool_definitions()

    assert [definition.function.name for definition in definitions] == [
        "hybrid_search_knowledge",
        "search_figures",
        "search_tables",
    ]


def test_registry_validates_arguments(default_registry: ToolRegistry) -> None:
    arguments = default_registry.validate_arguments(
        "hybrid_search_knowledge",
        {"query": "  dam crack  "},
    )
    image_arguments = default_registry.validate_arguments(
        "analyze_user_image",
        {"image_path": " image.png ", "question": " what is shown "},
    )

    assert isinstance(arguments, RetrievalArguments)
    assert arguments.query == "dam crack"
    assert isinstance(image_arguments, AnalyzeUserImageArguments)
    assert image_arguments.image_path == "image.png"
