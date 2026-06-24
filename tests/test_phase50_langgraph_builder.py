from __future__ import annotations

from app.services.agent.graph_builder import (
    LangGraphAgentService,
    build_langgraph_agent_graph,
    compact_prior_evidence,
    route_after_planner,
    load_prior_evidence_from_checkpoint,
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
from app.services.agent.memory_context import MEMORY_TRACE_FIELDS
from app.core.config import Settings
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from tests.test_phase50_langgraph_nodes import FakeToolbox


def test_langgraph_agent_graph_compiles_with_expected_nodes() -> None:
    graph = build_langgraph_agent_graph()
    compiled = graph.compile()

    node_names = set(compiled.nodes.keys()) - {"__start__"}

    assert node_names == {
        "planner",
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

    assert final_state["answer"] == "cited answer from existing evidence [1]"
    assert final_state["citations"] == [1]
    assert final_state["refused"] is False
    assert [call[0] for call in toolbox.calls] == ["hybrid_search_knowledge"]
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


def test_compact_prior_evidence_limits_sources_and_answer_summary() -> None:
    prior = compact_prior_evidence(
        {
            "sources": [
                {
                    "source_id": f"chunk:{index}",
                    "title": f"Document {index}",
                    "source_type": "local_file",
                    "document_id": index,
                    "chunk_id": index,
                    "chunk_index": 0,
                    "content": "x" * 500,
                }
                for index in range(1, 8)
            ],
            "citations": [1, "2", "bad"],
            "answer": "answer " * 100,
        }
    )

    assert len(prior["prior_sources"]) == 5
    assert len(prior["prior_sources"][0]["content"]) == 300
    assert prior["prior_citations"] == [1, 2]
    assert len(prior["prior_answer_summary"]) <= 200


def test_load_prior_evidence_from_checkpoint_fails_open() -> None:
    class BrokenGraph:
        def get_state(self, config):
            raise RuntimeError("checkpoint unavailable")

    prior = load_prior_evidence_from_checkpoint(
        compiled_graph=BrokenGraph(),
        config={"configurable": {"thread_id": "broken"}},
    )

    assert prior == {}


def test_load_prior_evidence_from_checkpoint_returns_compacted_state() -> None:
    class Snapshot:
        values = {
            "sources": [
                {
                    "source_id": "chunk:1",
                    "title": "Prior document",
                    "source_type": "local_file",
                    "content": "prior evidence",
                }
            ],
            "citations": [1],
            "answer": "prior answer",
        }

    class FakeGraph:
        def get_state(self, config):
            return Snapshot()

    prior = load_prior_evidence_from_checkpoint(
        compiled_graph=FakeGraph(),
        config={"configurable": {"thread_id": "ok"}},
    )

    assert prior["prior_sources"][0]["source_id"] == "chunk:1"
    assert prior["prior_citations"] == [1]
    assert prior["prior_answer_summary"] == "prior answer"


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
    assert result.answer == "cited answer from existing evidence [1]"
    assert result.citations == [1]
    assert result.refused is False
    assert result.iteration_count == 4
    assert result.workflow_steps[0].tool_name == "llm_with_tools"
    assert result.workflow_steps[1].tool_name == "search_knowledge"
    assert result.workflow_steps[2].tool_name == "llm_with_tools"
    assert result.workflow_steps[3].tool_name == "answer_with_citations"
    assert result.reasoning_summary == "langgraph_agent iterations=4; tool_calls=2"
    assert result.latency_trace["memory_context_present"] is False
    assert result.latency_trace["memory_long_term_enabled"] is False
    for field in MEMORY_TRACE_FIELDS:
        assert field in result.latency_trace
    assert result.latency_trace["memory_citation_source"] is False


def test_langgraph_agent_service_records_memory_trace_for_history(monkeypatch) -> None:
    toolbox = FakeToolbox()

    class FakeSession:
        pass

    service = LangGraphAgentService(
        db=FakeSession(),  # type: ignore[arg-type]
        embedding_provider=DeterministicEmbeddingProvider(),
        chat_model_provider=DeterministicChatModelProvider(),
    )
    service.toolbox = toolbox  # type: ignore[assignment]

    result = service.query(
        "它的流动性为什么重要？",
        top_k=2,
        history=["用户：自密实混凝土在堆石混凝土中起什么作用？"],
    )

    assert result.latency_trace["memory_context_present"] is True
    assert result.latency_trace["memory_session_entity_count"] >= 1
    assert result.latency_trace["memory_session_anchor_count"] >= 1
    assert result.latency_trace["memory_prior_source_count"] == 0
    assert result.latency_trace["memory_long_term_enabled"] is False
    assert result.latency_trace["memory_decision_hint"] in {
        "session_memory_retrieval_hint",
        "no_memory",
    }
    for field in MEMORY_TRACE_FIELDS:
        assert field in result.latency_trace
    assert result.latency_trace["memory_used_for_planning"] in {True, False}
    assert result.latency_trace["memory_citation_source"] is False
