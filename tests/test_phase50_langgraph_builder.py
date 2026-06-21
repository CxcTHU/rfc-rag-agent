from __future__ import annotations

from app.services.agent.graph_builder import (
    LangGraphAgentService,
    build_langgraph_agent_graph,
    route_after_planner,
)
from app.services.agent.graph_checkpointer import (
    create_graph_checkpointer,
    reset_graph_checkpointer_cache,
)
from app.services.agent.graph_nodes import (
    initialize_state,
    reset_current_toolbox,
    set_current_toolbox,
)
from app.core.config import Settings
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from tests.test_phase50_langgraph_nodes import FakeToolbox


def test_langgraph_agent_graph_compiles_with_expected_nodes() -> None:
    graph = build_langgraph_agent_graph()
    compiled = graph.compile()

    node_names = set(compiled.nodes.keys()) - {"__start__"}

    assert node_names == {
        "route",
        "search_knowledge",
        "search_figures",
        "search_tables",
        "analyze_user_image",
        "rewrite_query",
        "answer_with_citations",
        "refuse",
        "final_answer",
    }


def test_route_after_planner_uses_state_next_action() -> None:
    assert route_after_planner({"next_action": "search_tables"}) == "search_tables"


def test_langgraph_agent_graph_runs_search_then_answer_with_fake_toolbox() -> None:
    toolbox = FakeToolbox()
    initial_state = initialize_state(
        question="What affects filling capacity?",
        top_k=2,
        toolbox=toolbox,  # type: ignore[arg-type]
    )
    compiled = build_langgraph_agent_graph().compile()

    final_state = compiled.invoke(initial_state, config={"recursion_limit": 15})

    assert final_state["answer"] == "cited answer [1]"
    assert final_state["citations"] == [1]
    assert final_state["refused"] is False
    assert [call[0] for call in toolbox.calls] == [
        "hybrid_search_knowledge",
        "answer_with_citations",
    ]
    assert [step["name"] for step in final_state["workflow_steps"]] == [
        "llm_with_tools",
        "search_knowledge",
        "llm_with_tools",
        "answer_with_citations",
    ]


def test_langgraph_agent_graph_writes_memory_checkpoint_with_thread_id() -> None:
    reset_graph_checkpointer_cache()
    selection = create_graph_checkpointer(Settings(redis_url=""))
    toolbox = FakeToolbox()
    initial_state = initialize_state(
        question="What affects filling capacity?",
        top_k=2,
    )
    compiled = build_langgraph_agent_graph().compile(checkpointer=selection.checkpointer)
    token = set_current_toolbox(toolbox)  # type: ignore[arg-type]
    try:
        compiled.invoke(
            initial_state,
            config={
                "recursion_limit": 15,
                "configurable": {"thread_id": "phase50-memory-checkpoint"},
            },
        )
    finally:
        reset_current_toolbox(token)

    checkpoint_tuple = selection.checkpointer.get_tuple(
        {"configurable": {"thread_id": "phase50-memory-checkpoint"}}
    )

    assert checkpoint_tuple is not None
    assert selection.backend == "memory"


def test_langgraph_agent_service_preserves_agent_query_result_contract(monkeypatch) -> None:
    toolbox = FakeToolbox()

    class FakeSession:
        pass

    service = LangGraphAgentService(
        db=FakeSession(),  # type: ignore[arg-type]
        embedding_provider=DeterministicEmbeddingProvider(),
        chat_model_provider=DeterministicChatModelProvider(),
    )
    service.toolbox = toolbox  # type: ignore[assignment]

    result = service.query("What affects filling capacity?", top_k=2)

    assert result.mode == "langgraph_agent"
    assert result.answer == "cited answer [1]"
    assert result.citations == [1]
    assert result.refused is False
    assert result.iteration_count == 4
    assert result.workflow_steps[0].tool_name == "llm_with_tools"
    assert result.workflow_steps[1].tool_name == "search_knowledge"
    assert result.workflow_steps[2].tool_name == "llm_with_tools"
    assert result.workflow_steps[3].tool_name == "answer_with_citations"
    assert result.reasoning_summary == "langgraph_agent iterations=4; tool_calls=2"
