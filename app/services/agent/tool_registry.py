"""Single production tool catalogue for the Tool Calling runtime."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from types import MappingProxyType
from typing import cast

from pydantic import BaseModel

from app.services.agent.tool_contracts import (
    AnalyzeUserImageArguments,
    ProductionToolName,
    RetrievalArguments,
    ToolAdapter,
    ToolSpec,
)
from app.services.agent.tool_models import AgentToolResult
from app.services.generation.chat_model import ChatToolDefinition, ChatToolFunction


TEXT_TOOL_NAMES: tuple[ProductionToolName, ...] = (
    "hybrid_search_knowledge",
    "search_figures",
    "search_tables",
)


class UnsupportedToolError(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"unsupported tool: {name}")
        self.name = name


class UnboundToolAdapter:
    """Placeholder used while Task 3 wires schemas before adapter migration."""

    def execute(
        self,
        arguments: BaseModel,
        context: object,
    ) -> AgentToolResult:
        raise RuntimeError("tool adapter is not bound")


class ToolRegistry:
    def __init__(self, specs: Sequence[ToolSpec]) -> None:
        ordered = tuple(specs)
        by_name: dict[ProductionToolName, ToolSpec] = {}
        for spec in ordered:
            if spec.name in by_name:
                raise ValueError(f"duplicate tool registration: {spec.name}")
            by_name[spec.name] = spec
        self._specs = ordered
        self._by_name = MappingProxyType(by_name)

    @property
    def names(self) -> tuple[ProductionToolName, ...]:
        return tuple(spec.name for spec in self._specs)

    def require(self, name: str) -> ToolSpec:
        try:
            return self._by_name[cast(ProductionToolName, name)]
        except KeyError as error:
            raise UnsupportedToolError(name) from error

    def validate_arguments(self, name: str, raw: Mapping[str, object]) -> BaseModel:
        return self.require(name).arguments_model.model_validate(dict(raw))

    def chat_tool_definitions(
        self,
        available_names: Collection[str] | None = None,
    ) -> tuple[ChatToolDefinition, ...]:
        requested = set(self.names if available_names is None else available_names)
        for name in requested:
            self.require(name)
        return tuple(
            ChatToolDefinition(
                function=ChatToolFunction(
                    name=spec.name,
                    description=spec.description,
                    parameters=chat_tool_parameters_for_spec(spec),
                )
            )
            for spec in self._specs
            if spec.name in requested
        )


def tool_registry_from_adapters(
    *,
    hybrid_search: ToolAdapter,
    figure_search: ToolAdapter,
    table_search: ToolAdapter,
    user_image_analysis: ToolAdapter,
) -> ToolRegistry:
    return ToolRegistry(
        (
            ToolSpec(
                name="hybrid_search_knowledge",
                arguments_model=RetrievalArguments,
                adapter=hybrid_search,
                default_result_limit=8,
                timeout_seconds=20.0,
                required_permissions=frozenset({"read:knowledge"}),
                safe_event_label="knowledge_search",
                description=(
                    "Read-only hybrid keyword/vector search over the local "
                    "rock-filled concrete knowledge base."
                ),
            ),
            ToolSpec(
                name="search_figures",
                arguments_model=RetrievalArguments,
                adapter=figure_search,
                default_result_limit=4,
                timeout_seconds=20.0,
                required_permissions=frozenset({"read:figures"}),
                safe_event_label="figure_search",
                description=(
                    "Read-only figure search over image-description chunks. Use "
                    "when the user asks for or would clearly benefit from "
                    "visual evidence such as figures, photos, diagrams, curves, "
                    "charts, microscopy, or failure morphology."
                ),
            ),
            ToolSpec(
                name="search_tables",
                arguments_model=RetrievalArguments,
                adapter=table_search,
                default_result_limit=8,
                timeout_seconds=20.0,
                required_permissions=frozenset({"read:tables"}),
                safe_event_label="table_search",
                description=(
                    "Read-only search over extracted table chunks. Use for "
                    "tabulated data, mix-ratio rows, parameter tables, and "
                    "table-based comparisons."
                ),
            ),
            ToolSpec(
                name="analyze_user_image",
                arguments_model=AnalyzeUserImageArguments,
                adapter=user_image_analysis,
                default_result_limit=4,
                timeout_seconds=30.0,
                required_permissions=frozenset({"read:user_image"}),
                safe_event_label="user_image_analysis",
                description=(
                    "Analyze one uploaded user image and return bounded visual "
                    "observations for the runtime to combine with retrieval."
                ),
            ),
        )
    )


def default_tool_registry(
    adapter: ToolAdapter | None = None,
) -> ToolRegistry:
    bound_adapter = adapter or UnboundToolAdapter()
    return tool_registry_from_adapters(
        hybrid_search=bound_adapter,
        figure_search=bound_adapter,
        table_search=bound_adapter,
        user_image_analysis=bound_adapter,
    )


def chat_tool_parameters_for_spec(spec: ToolSpec) -> dict[str, object]:
    schema = dict(spec.arguments_model.model_json_schema())
    if spec.name in TEXT_TOOL_NAMES:
        properties = dict(schema.get("properties", {}))
        query_schema = properties.get("query")
        schema["properties"] = {"query": query_schema}
        schema["required"] = ["query"]
    return schema
