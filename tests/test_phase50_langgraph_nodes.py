from __future__ import annotations

from app.services.agent.graph_nodes import (
    generate_answer_node,
    initialize_state,
    refuse_node,
    reset_current_event_sink,
    rewrite_query_node,
    route_query_node,
    search_figures_node,
    search_knowledge_node,
    search_tables_node,
    set_current_event_sink,
)
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    AgentToolResult,
)


class FakeToolbox:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def hybrid_search_knowledge(self, query: str, top_k: int = 5, progress_callback=None) -> AgentToolResult:
        self.calls.append(("hybrid_search_knowledge", query, top_k))
        if progress_callback is not None:
            progress_callback("正在生成或读取问题向量")
        return tool_result(
            "hybrid_search_knowledge",
            query=query,
            output_summary="returned 1 hybrid results",
            search_results=[search_item(chunk_id=1)],
            sources=[source_reference(chunk_id=1)],
        )

    def search_figures(self, query: str, top_k: int = 4) -> AgentToolResult:
        self.calls.append(("search_figures", query, top_k))
        return tool_result(
            "search_figures",
            query=query,
            output_summary="returned 1 figure results",
            search_results=[search_item(chunk_id=2, chunk_type="image_description")],
            sources=[source_reference(chunk_id=2, chunk_type="image_description")],
        )

    def search_tables(self, query: str, top_k: int = 5) -> AgentToolResult:
        self.calls.append(("search_tables", query, top_k))
        return tool_result(
            "search_tables",
            query=query,
            output_summary="returned 1 table results",
            search_results=[search_item(chunk_id=3, chunk_type="table")],
            sources=[source_reference(chunk_id=3, chunk_type="table")],
        )

    def analyze_user_image(self, image_path: str, question: str, top_k: int = 5) -> AgentToolResult:
        self.calls.append(("analyze_user_image", image_path, top_k))
        return tool_result(
            "analyze_user_image",
            query=question,
            output_summary="image described",
            answer="image answer",
            image_analysis={"domain_relevance": "in_scope"},
        )

    def answer_with_citations(
        self,
        question: str,
        top_k: int = 5,
        retrieval_mode: str = "hybrid",
        history=None,
    ) -> AgentToolResult:
        self.calls.append(("answer_with_citations", question, top_k))
        return tool_result(
            "answer_with_citations",
            query=question,
            output_summary="refused=False; sources=1; citations=1",
            answer="cited answer [1]",
            sources=[source_reference(chunk_id=1)],
            citations=[1],
        )


def tool_result(
    tool_name: str,
    *,
    query: str,
    output_summary: str,
    answer: str | None = None,
    search_results: list[AgentSearchItem] | None = None,
    sources: list[AgentSourceReference] | None = None,
    citations: list[int] | None = None,
    image_analysis: dict[str, object] | None = None,
) -> AgentToolResult:
    return AgentToolResult(
        tool_name=tool_name,
        call=AgentToolCallRecord(
            tool_name=tool_name,
            input_summary=f"query={query}",
            output_summary=output_summary,
            succeeded=True,
        ),
        answer=answer,
        search_results=search_results or [],
        sources=sources or [],
        citations=citations or [],
        image_analysis=image_analysis,
    )


def search_item(*, chunk_id: int, chunk_type: str = "text") -> AgentSearchItem:
    return AgentSearchItem(
        document_id=1,
        document_title="Fixture",
        source_type="local_file",
        source_path="fixture.md",
        file_name="fixture.md",
        chunk_id=chunk_id,
        chunk_index=0,
        content="fixture content",
        heading_path=None,
        score=1.0,
        chunk_type=chunk_type,
    )


def source_reference(*, chunk_id: int, chunk_type: str = "text") -> AgentSourceReference:
    return AgentSourceReference(
        source_id=f"chunk:{chunk_id}",
        title="Fixture",
        source_type="local_file",
        document_id=1,
        chunk_id=chunk_id,
        chunk_index=0,
        chunk_type=chunk_type,
    )


def test_initialize_state_sets_safe_defaults() -> None:
    state = initialize_state(question="  filling capacity  ", top_k=3, max_iterations=10)

    assert state["question"] == "filling capacity"
    assert state["top_k"] == 3
    assert state["max_iterations"] == 3
    assert state["observations"] == []
    assert state["previous_queries"] == []


def test_route_query_node_selects_search_before_answering() -> None:
    state = initialize_state(question="What affects filling capacity?")

    updates = route_query_node(state)

    assert updates["next_action"] == "search_knowledge"
    assert updates["current_query"] == "What affects filling capacity?"
    assert updates["iteration_count"] == 1
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"


def test_route_query_node_selects_image_analysis_when_image_is_attached() -> None:
    state = initialize_state(question="analyze this", image_path="data/user_uploads/a.png")

    updates = route_query_node(state)

    assert updates["next_action"] == "analyze_user_image"
    assert updates["iteration_count"] == 1
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"


def test_route_query_node_selects_table_search_for_table_questions() -> None:
    state = initialize_state(question="请返回配合比表中的参数")

    updates = route_query_node(state)

    assert updates["next_action"] == "search_tables"
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"


def test_route_query_node_answers_after_table_evidence() -> None:
    state = initialize_state(question="请返回配合比表中的参数")
    state["observations"] = [
        search_tables_node(
            {
                **state,
                "_toolbox": FakeToolbox(),
                "current_query": "请返回配合比表中的参数",
                "iteration_count": 1,
            }
        )["observations"][0]
    ]

    updates = route_query_node(state)

    assert updates["next_action"] == "answer_with_citations"
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"


def test_route_query_node_answers_with_retrieved_evidence_at_iteration_limit() -> None:
    state = initialize_state(question="堆石混凝土的性能", max_iterations=1)
    state["iteration_count"] = 1
    state["observations"] = [
        search_knowledge_node(
            {
                **state,
                "_toolbox": FakeToolbox(),
                "current_query": "堆石混凝土的性能",
            }
        )["observations"][0]
    ]

    updates = route_query_node(state)

    assert updates["next_action"] == "answer_with_citations"
    assert "refusal_reason" not in updates
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"


def test_search_knowledge_node_reuses_agent_toolbox_and_records_observation() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(question="filling capacity", top_k=2, toolbox=toolbox)
    state.update(route_query_node(state))

    updates = search_knowledge_node(state)

    assert toolbox.calls == [("hybrid_search_knowledge", "filling capacity", 2)]
    assert len(updates["observations"]) == 1
    assert updates["observations"][0]["action"] == "search_knowledge"
    assert len(updates["workflow_steps"]) == 2
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"
    assert len(updates["search_results"]) == 1
    assert len(updates["sources"]) == 1


def test_search_knowledge_node_emits_safe_search_progress() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(question="filling capacity", top_k=2, toolbox=toolbox)
    state.update(route_query_node(state))
    events = []
    token = set_current_event_sink(events.append)
    try:
        search_knowledge_node(state)
    finally:
        reset_current_event_sink(token)

    progress = [
        event.payload["step_summary"]
        for event in events
        if event.event == "agent_step" and event.payload.get("action") == "search_progress"
    ]
    assert progress == ["正在生成或读取问题向量"]


def test_visual_and_table_nodes_reuse_agent_toolbox() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(question="show figure", top_k=5, toolbox=toolbox)
    state["current_query"] = "show figure"

    figure_updates = search_figures_node(state)
    table_updates = search_tables_node(state)

    assert toolbox.calls == [
        ("search_figures", "show figure", 4),
        ("search_tables", "show figure", 5),
    ]
    assert figure_updates["search_results"][0]["chunk_type"] == "image_description"
    assert table_updates["search_results"][0]["chunk_type"] == "table"


def test_generate_answer_node_uses_answer_with_citations_contract() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(question="answer me", top_k=3, toolbox=toolbox)

    updates = generate_answer_node(state)

    assert toolbox.calls == [("answer_with_citations", "answer me", 3)]
    assert updates["answer"] == "cited answer [1]"
    assert updates["citations"] == [1]
    assert updates["refused"] is False


def test_generate_answer_node_emits_safe_answer_progress() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(question="answer me", top_k=3, toolbox=toolbox)
    state["search_results"] = [search_item(chunk_id=1), search_item(chunk_id=2)]
    state["sources"] = [source_reference(chunk_id=1), source_reference(chunk_id=2)]
    events = []
    token = set_current_event_sink(events.append)
    try:
        generate_answer_node(state)
    finally:
        reset_current_event_sink(token)

    progress = [
        event.payload["step_summary"]
        for event in events
        if event.event == "agent_step" and event.payload.get("action") == "answer_progress"
    ]
    assert progress == [
        "正在基于 2 条证据组织回答",
        "已找到 2 个相关来源",
        "正在检查引用编号",
        "正在生成最终中文回答",
    ]


def test_rewrite_and_refuse_nodes_record_workflow_steps() -> None:
    state = initialize_state(question="unknown")
    state["current_query"] = "unknown rock-filled concrete"
    state["iteration_count"] = 2

    rewrite_updates = rewrite_query_node(state)
    state.update(rewrite_updates)
    state["refusal_reason"] = "No reliable evidence."
    refuse_updates = refuse_node(state)

    assert rewrite_updates["observations"][0]["action"] == "rewrite_query"
    assert refuse_updates["refused"] is True
    assert "No reliable evidence." in refuse_updates["answer"]
    assert len(refuse_updates["workflow_steps"]) == 2
