from __future__ import annotations

from dataclasses import dataclass

from app.services.agent.tool_registry import (
    TEXT_TOOL_NAMES,
    ToolRegistry,
    default_tool_registry,
)
from app.services.generation.chat_model import ChatToolDefinition


@dataclass(frozen=True)
class ToolCallingRuntimeComposition:
    registry: ToolRegistry


def compose_tool_calling_runtime(
    registry: ToolRegistry | None = None,
) -> ToolCallingRuntimeComposition:
    return ToolCallingRuntimeComposition(registry=registry or default_tool_registry())


def tool_calling_tool_definitions(
    registry: ToolRegistry | None = None,
) -> list[ChatToolDefinition]:
    active_registry = registry or default_tool_registry()
    return list(active_registry.chat_tool_definitions(available_names=TEXT_TOOL_NAMES))
