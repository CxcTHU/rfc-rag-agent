from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.agent import AgentQueryRequest
from app.services.agent.tool_registry import default_tool_registry
from app.services.agent.tools import AgentToolbox


ROOT = Path(__file__).resolve().parents[1]

RETIRED_RUNTIME_PATHS = (
    "app/services/agent/react_actions.py",
    "app/services/agent/react_service.py",
    "app/services/agent/adaptive_retrieval.py",
    "app/services/agent/routing.py",
    "app/services/agent/graph_builder.py",
    "app/services/agent/graph_checkpointer.py",
    "app/services/agent/graph_nodes.py",
    "app/services/agent/graph_state.py",
    "app/services/agent/memory_context.py",
)

PRODUCTION_TOOLS = (
    "hybrid_search_knowledge",
    "search_tables",
    "search_figures",
    "analyze_user_image",
)


def test_retired_agent_runtimes_are_absent() -> None:
    remaining = [path for path in RETIRED_RUNTIME_PATHS if (ROOT / path).exists()]
    assert remaining == []
    assert not list((ROOT / "app/services/agentic").glob("*.py"))


@pytest.mark.parametrize("retired_mode", ["react_agent", "langgraph_agent", "agentic"])
def test_agent_query_rejects_retired_mode_fields(retired_mode: str) -> None:
    with pytest.raises(ValidationError):
        AgentQueryRequest(question="What affects filling capacity?", mode=retired_mode)


def test_langgraph_dependencies_are_absent() -> None:
    project_config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"langgraph>=' not in project_config
    assert '"langgraph-checkpoint-redis>=' not in project_config


def test_production_registry_and_toolbox_keep_exactly_four_tools() -> None:
    assert len(default_tool_registry().names) == len(PRODUCTION_TOOLS)
    assert set(default_tool_registry().names) == set(PRODUCTION_TOOLS)
    for tool_name in PRODUCTION_TOOLS:
        assert callable(getattr(AgentToolbox, tool_name))
