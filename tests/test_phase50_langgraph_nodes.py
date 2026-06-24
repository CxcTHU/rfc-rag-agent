from __future__ import annotations

from app.services.agent.graph_nodes import (
    generate_answer_node,
    initialize_state,
    planner_node,
    refuse_node,
    reset_current_event_sink,
    rewrite_query_node,
    search_figures_node,
    search_graph_knowledge_node,
    search_knowledge_node,
    search_tables_node,
    set_current_event_sink,
)
from app.services.agent.memory_context import build_agent_memory_context
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    AgentToolResult,
)
from app.services.generation.chat_model import ChatMessage, ChatModelResult
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)


class RecordingChatProvider:
    provider_name = "test"
    model_name = "recording-chat"

    def __init__(self, answers: list[str] | None = None) -> None:
        self.answers = answers or ["cited answer from existing evidence [1]"]
        self.messages: list[list[ChatMessage]] = []

    def generate(self, messages) -> ChatModelResult:
        self.messages.append(list(messages))
        answer = self.answers[min(len(self.messages) - 1, len(self.answers) - 1)]
        return ChatModelResult(
            answer=answer,
            provider=self.provider_name,
            model_name=self.model_name,
        )


class FakeToolbox:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self.chat_model_provider = RecordingChatProvider()

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

    def search_graph_knowledge(self, query: str, top_k: int = 5) -> AgentToolResult:
        self.calls.append(("search_graph_knowledge", query, top_k))
        return tool_result(
            "search_graph_knowledge",
            query=query,
            output_summary="returned 1 graph-enhanced results; graph_available=True",
            search_results=[search_item(chunk_id=4)],
            sources=[source_reference(chunk_id=4)],
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
        content="fixture source evidence",
    )


def test_initialize_state_sets_safe_defaults() -> None:
    state = initialize_state(question="  filling capacity  ", top_k=3, max_iterations=10)

    assert state["question"] == "filling capacity"
    assert state["top_k"] == 3
    assert state["max_iterations"] == 3
    assert state["observations"] == []
    assert state["previous_queries"] == []


def test_planner_node_selects_search_before_answering() -> None:
    state = initialize_state(question="What affects filling capacity?")

    updates = planner_node(state)

    assert updates["next_action"] == "search_knowledge"
    assert updates["retrieval_strategy"] == "hybrid_knowledge_search"
    assert updates["current_query"] == "What affects filling capacity?"
    assert updates["iteration_count"] == 1
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"


def test_planner_node_answers_expand_followup_from_prior_sources() -> None:
    state = initialize_state(
        question="请详细回答",
        history=["用户：堆石混凝土填充性能受到哪些方面的影响？"],
    )
    state["prior_sources"] = [
        source_reference(chunk_id=1).__dict__,
        source_reference(chunk_id=2).__dict__,
        source_reference(chunk_id=3).__dict__,
    ]
    state["prior_citations"] = [1, 2, 3]
    state["prior_answer_summary"] = "上一轮回答说明填充性能受颗粒阻塞、流体阻塞和施工参数影响。"
    state["memory_context"] = build_agent_memory_context(
        question="请详细回答",
        history=state["history"],
        prior_evidence={
            "prior_sources": state["prior_sources"],
            "prior_citations": state["prior_citations"],
            "prior_answer_summary": state["prior_answer_summary"],
        },
    ).to_state_dict()

    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        updates = planner_node(state)
    finally:
        reset_current_latency_trace(token)

    assert updates["next_action"] == "answer_with_citations"
    assert updates["retrieval_strategy"] == "answer_from_prior_evidence"
    assert trace.values["retrieval_strategy"] == "answer_from_prior_evidence"
    assert updates["current_query"] == "请详细回答"
    assert updates["workflow_steps"][0]["output_summary"] == "selected action=answer_with_citations"


def test_planner_node_searches_new_direction_despite_prior_sources() -> None:
    state = initialize_state(question="堆石混凝土温控措施有哪些？")
    state["prior_sources"] = [
        source_reference(chunk_id=1).__dict__,
        source_reference(chunk_id=2).__dict__,
        source_reference(chunk_id=3).__dict__,
    ]

    updates = planner_node(state)

    assert updates["next_action"] == "search_knowledge"
    assert updates["current_query"] == "堆石混凝土温控措施有哪些？"


def test_planner_node_refreshes_search_when_session_anchor_is_stale() -> None:
    state = initialize_state(
        question="更正一下，我想问 Peridynamics 用于裂纹分析的证据",
        history=["user:Peridynamics is a construction quality control method?"],
    )
    state["prior_sources"] = [
        source_reference(chunk_id=1).__dict__,
        source_reference(chunk_id=2).__dict__,
        source_reference(chunk_id=3).__dict__,
    ]
    state["memory_context"] = build_agent_memory_context(
        question=state["question"],
        history=state["history"],
        prior_evidence={"prior_sources": state["prior_sources"]},
    ).to_state_dict()

    updates = planner_node(state)

    assert updates["next_action"] == "search_knowledge"


def test_planner_node_keeps_original_behavior_without_prior_sources() -> None:
    state = initialize_state(question="请详细回答")

    updates = planner_node(state)

    assert updates["next_action"] == "search_knowledge"


def test_planner_node_selects_image_analysis_when_image_is_attached() -> None:
    state = initialize_state(question="analyze this", image_path="data/user_uploads/a.png")

    updates = planner_node(state)

    assert updates["next_action"] == "analyze_user_image"
    assert updates["iteration_count"] == 1
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"


def test_planner_node_selects_table_search_for_table_questions() -> None:
    state = initialize_state(question="请返回配合比表中的参数")
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        updates = planner_node(state)
    finally:
        reset_current_latency_trace(token)

    assert updates["next_action"] == "search_tables"
    assert updates["retrieval_strategy"] == "table_search"
    assert trace.values["retrieval_strategy"] == "table_search"
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"


def test_planner_node_answers_after_table_evidence() -> None:
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

    updates = planner_node(state)

    assert updates["next_action"] == "answer_with_citations"
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"


def test_planner_node_answers_with_retrieved_evidence_at_iteration_limit() -> None:
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

    updates = planner_node(state)

    assert updates["next_action"] == "answer_with_citations"
    assert "refusal_reason" not in updates
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"


def test_search_knowledge_node_reuses_agent_toolbox_and_records_observation() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(question="filling capacity", top_k=2, toolbox=toolbox)
    state.update(planner_node(state))

    updates = search_knowledge_node(state)

    assert toolbox.calls == [("hybrid_search_knowledge", "filling capacity", 2)]
    assert len(updates["observations"]) == 1
    assert updates["observations"][0]["action"] == "search_knowledge"
    assert len(updates["workflow_steps"]) == 2
    assert updates["workflow_steps"][0]["name"] == "llm_with_tools"
    assert len(updates["search_results"]) == 1
    assert len(updates["sources"]) == 1


def test_search_graph_knowledge_node_reuses_agent_toolbox_and_records_observation() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(question="standard reference chain", top_k=2, toolbox=toolbox)
    state["current_query"] = "standard reference chain"
    state["iteration_count"] = 1

    updates = search_graph_knowledge_node(state)

    assert toolbox.calls == [("search_graph_knowledge", "standard reference chain", 2)]
    assert updates["observations"][0]["action"] == "search_graph_knowledge"
    assert updates["workflow_steps"][0]["name"] == "search_graph_knowledge"
    assert len(updates["search_results"]) == 1
    assert len(updates["sources"]) == 1


def test_search_knowledge_node_augments_contextual_query_with_memory_hint() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(
        question="它的流动性为什么重要？",
        history=["用户：自密实混凝土在堆石混凝土中起什么作用？"],
        top_k=2,
        toolbox=toolbox,
    )
    state["current_query"] = "它的流动性为什么重要？"
    state["memory_context"] = build_agent_memory_context(
        question=state["question"],
        history=state["history"],
        prior_evidence={},
    ).to_state_dict()

    search_knowledge_node(state)

    assert "会话检索记忆" in toolbox.calls[0][1]
    assert "不作为引用来源" in toolbox.calls[0][1]


def test_search_knowledge_node_emits_safe_search_progress() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(question="filling capacity", top_k=2, toolbox=toolbox)
    state.update(planner_node(state))
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


def test_generate_answer_node_uses_existing_sources_without_retrieval() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(question="What affects RFC filling capacity?", top_k=3, toolbox=toolbox)
    state["search_results"] = [search_item(chunk_id=1)]
    state["sources"] = [source_reference(chunk_id=1)]

    updates = generate_answer_node(state)

    assert toolbox.calls == []
    assert len(toolbox.chat_model_provider.messages) == 1
    assert updates["answer"] == "cited answer from existing evidence [1]"
    assert updates["citations"] == [1]
    assert updates["refused"] is False


def test_generate_answer_node_falls_back_when_sources_are_missing() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(question="What affects RFC filling capacity?", top_k=3, toolbox=toolbox)

    updates = generate_answer_node(state)

    assert toolbox.calls == [("answer_with_citations", "What affects RFC filling capacity?", 3)]
    assert updates["answer"] == "cited answer [1]"
    assert updates["citations"] == [1]
    assert updates["refused"] is False


def test_generate_answer_node_uses_prior_sources_when_current_sources_are_missing() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(
        question="请详细回答",
        top_k=3,
        toolbox=toolbox,
        history=["堆石混凝土填充性能受到哪些方面的影响？"],
    )
    state["prior_sources"] = [
        source_reference(chunk_id=1).__dict__,
        source_reference(chunk_id=2).__dict__,
        source_reference(chunk_id=3).__dict__,
    ]
    state["prior_citations"] = [1, 2, 3]
    state["memory_context"] = build_agent_memory_context(
        question=state["question"],
        history=state["history"],
        prior_evidence={
            "prior_sources": state["prior_sources"],
            "prior_citations": state["prior_citations"],
        },
    ).to_state_dict()

    updates = generate_answer_node(state)

    assert toolbox.calls == []
    assert len(toolbox.chat_model_provider.messages) == 1
    assert updates["answer"] == "cited answer from existing evidence [1]"
    assert updates["citations"] == [1]
    assert len(updates["sources"]) == 3
    assert updates["refused"] is False


def test_generate_answer_node_rebuilds_policy_for_legacy_prior_sources() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(
        question="please expand",
        top_k=3,
        toolbox=toolbox,
        history=["user: What affects rock-filled concrete filling capacity?"],
    )
    state["prior_sources"] = [
        source_reference(chunk_id=1).__dict__,
        source_reference(chunk_id=2).__dict__,
        source_reference(chunk_id=3).__dict__,
    ]
    state["prior_citations"] = [1, 2, 3]

    updates = generate_answer_node(state)

    assert toolbox.calls == []
    assert len(toolbox.chat_model_provider.messages) == 1
    assert len(updates["sources"]) == 3


def test_generate_answer_node_accepts_legacy_prior_sources_when_relevance_passes() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(
        question="please expand",
        top_k=3,
        toolbox=toolbox,
        history=["user: What affects rock-filled concrete filling capacity?"],
    )
    state["prior_sources"] = [
        source_reference(chunk_id=1).__dict__,
        source_reference(chunk_id=2).__dict__,
    ]
    state["prior_citations"] = [1, 2]

    updates = generate_answer_node(state)

    assert toolbox.calls == []
    assert updates["answer"] == "cited answer from existing evidence [1]"


def test_generate_answer_node_does_not_use_prior_sources_when_stale() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(
        question="更正一下，我想问 Peridynamics 用于裂纹分析的证据",
        top_k=3,
        toolbox=toolbox,
        history=["user:Peridynamics is a construction quality control method?"],
    )
    state["prior_sources"] = [
        source_reference(chunk_id=1).__dict__,
        source_reference(chunk_id=2).__dict__,
        source_reference(chunk_id=3).__dict__,
    ]
    state["memory_context"] = build_agent_memory_context(
        question=state["question"],
        history=state["history"],
        prior_evidence={"prior_sources": state["prior_sources"]},
    ).to_state_dict()

    updates = generate_answer_node(state)

    assert toolbox.calls == [("answer_with_citations", state["question"], 3)]
    assert updates["answer"] == "cited answer [1]"


def test_generate_answer_node_refuses_off_topic_before_llm_generation() -> None:
    toolbox = FakeToolbox()
    state = initialize_state(question="How do I cook pasta?", top_k=3, toolbox=toolbox)
    state["search_results"] = [search_item(chunk_id=1)]
    state["sources"] = [source_reference(chunk_id=1)]

    updates = generate_answer_node(state)

    assert toolbox.calls == []
    assert toolbox.chat_model_provider.messages == []
    assert updates["refused"] is True
    assert updates["refusal_reason"] == "Question appears off-topic: no domain anchor was found."


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
