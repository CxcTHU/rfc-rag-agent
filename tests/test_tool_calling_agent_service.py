from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    AgentToolResult,
)
from app.services.agent.tool_calling_service import (
    ToolCallingAgentService,
    ToolCallingRuntimeEvent,
    citation_repair_messages,
    evidence_answer_messages,
    final_answer_strategy_instruction,
    tool_calling_tool_definitions,
    tool_calling_messages,
)
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelResult,
    ChatToolCall,
    ChatToolDefinition,
    DeterministicChatModelProvider,
    ToolCallingChatModelResult,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService


def make_session(tmp_path):
    database_path = tmp_path / "tool_calling_agent.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_tool_calling_documents(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Rock-filled concrete filling guide",
            source_type="local_file",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="tool-calling-agent-filling-hash",
            raw_path="data/raw/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Filling capacity depends on self-compacting concrete "
                    "flowability in rock-filled concrete voids."
                ),
                char_count=98,
                heading_path="Filling",
                start_char=0,
                end_char=98,
            )
        ],
    )


def seed_tool_calling_figure_documents(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Rock-filled concrete stress strain figure",
            source_type="local_file",
            source_path="stress-strain.pdf",
            file_name="stress-strain.pdf",
            file_extension=".pdf",
            content_hash="tool-calling-agent-stress-strain-hash",
            raw_path="data/raw/stress-strain.pdf",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Rock-filled concrete stress strain behavior is evaluated from axial loading tests.",
                char_count=83,
                heading_path="Stress strain",
                start_char=0,
                end_char=83,
            ),
            ChunkCreate(
                chunk_index=1,
                content=(
                    "Stress strain curve figure for rock-filled concrete specimens "
                    "under compression loading and failure morphology."
                ),
                char_count=108,
                heading_path="Figure",
                start_char=None,
                end_char=None,
                chunk_type="image_description",
                source_image_path="data/images/tool_calling_fixture/page3_img1.png",
                caption="图3-4 堆石混凝土应力应变曲线",
                page_number=3,
            ),
        ],
    )


def make_service(
    db: Session,
    chat_provider: DeterministicChatModelProvider | None = None,
) -> ToolCallingAgentService:
    provider = DeterministicEmbeddingProvider(dimension=32)
    VectorIndexService(db, provider).build_index()
    return ToolCallingAgentService(
        db=db,
        embedding_provider=provider,
        chat_model_provider=chat_provider or DeterministicChatModelProvider(),
        log_answers=False,
    )


class FailingEmbeddingProvider:
    provider_name = "failing-embedding"
    model_name = "failing-embedding-v1"
    dimension = 32

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("Embedding provider unavailable")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Embedding provider unavailable")


class CitationRepairChatProvider:
    provider_name = "citation-repair-test"
    model_name = "citation-repair-test-v1"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer="Filling capacity depends on SCC flowability [1].",
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def stream_generate(self, messages: list[ChatMessage]):
        yield self.generate(messages).answer

    def generate_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ChatToolDefinition],
    ) -> ToolCallingChatModelResult:
        if not any(message.role == "tool" for message in messages):
            return ToolCallingChatModelResult(
                content="",
                tool_calls=[
                    ChatToolCall(
                        id="call_1",
                        name="hybrid_search_knowledge",
                        arguments={"query": "filling capacity", "top_k": 2},
                    )
                ],
                provider=self.provider_name,
                model_name=self.model_name,
            )
        return ToolCallingChatModelResult(
            content="Filling capacity depends on SCC flowability.",
            tool_calls=[],
            provider=self.provider_name,
            model_name=self.model_name,
        )


def test_tool_calling_agent_searches_then_returns_cited_answer(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db).query(
            "What affects filling capacity in rock-filled concrete?",
            top_k=2,
            max_tool_calls=3,
        )

    assert not result.refused
    assert result.mode == "tool_calling_agent"
    assert result.citations == [1]
    assert result.sources
    assert [call.tool_name for call in result.tool_calls] == ["hybrid_search_knowledge"]
    assert result.latency_trace["llm_call_count"] == 2
    assert result.latency_trace["tool_call_count"] == 1
    assert "tool_calling_agent" in result.reasoning_summary


def test_tool_calling_agent_adds_figures_for_visual_queries(tmp_path, monkeypatch) -> None:
    TestingSessionLocal = make_session(tmp_path)

    figure_item = AgentSearchItem(
        document_id=2,
        document_title="Rock-filled concrete stress strain figure",
        source_type="local_file",
        source_path="stress-strain.pdf",
        file_name="stress-strain.pdf",
        chunk_id=20,
        chunk_index=1,
        content="Stress strain curve figure for rock-filled concrete specimens.",
        heading_path="Figure",
        score=0.82,
        chunk_type="image_description",
        source_image_path="data/images/tool_calling_fixture/page3_img1.png",
        image_url="/assets/images/tool_calling_fixture/page3_img1.png",
        caption="图3-4 堆石混凝土应力应变曲线",
        page_number=3,
    )
    figure_source = AgentSourceReference(
        source_id="chunk:20",
        title=figure_item.document_title,
        source_type=figure_item.source_type,
        document_id=figure_item.document_id,
        chunk_id=figure_item.chunk_id,
        chunk_index=figure_item.chunk_index,
        content=figure_item.content,
        score=figure_item.score,
        chunk_type=figure_item.chunk_type,
        source_image_path=figure_item.source_image_path,
        image_url=figure_item.image_url,
        caption=figure_item.caption,
        page_number=figure_item.page_number,
    )

    def fake_search_figures(self, query: str, top_k: int = 4) -> AgentToolResult:
        return AgentToolResult(
            tool_name="search_figures",
            call=AgentToolCallRecord(
                tool_name="search_figures",
                input_summary=f"query={query}; top_k={top_k}",
                output_summary="returned 1 figure results",
                succeeded=True,
            ),
            search_results=[figure_item],
            sources=[figure_source],
        )

    monkeypatch.setattr(
        "app.services.agent.tools.AgentToolbox.search_figures",
        fake_search_figures,
    )

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        chat_provider = DeterministicChatModelProvider(
            tool_call_rounds=(
                (
                    ChatToolCall(
                        id="call_1",
                        name="hybrid_search_knowledge",
                        arguments={
                            "query": "filling capacity in rock-filled concrete",
                            "top_k": 1,
                        },
                    ),
                ),
            )
        )
        result = make_service(db, chat_provider=chat_provider).query(
            "Show the rock-filled concrete stress strain curve figure.",
            top_k=1,
            max_tool_calls=3,
        )

    assert not result.refused
    assert "search_figures" in [call.tool_name for call in result.tool_calls]
    image_sources = [source for source in result.sources if source.image_url]
    assert image_sources
    assert image_sources[0].caption == "图3-4 堆石混凝土应力应变曲线"
    assert image_sources[0].page_number == 3
    assert image_sources[0].image_url == "/assets/images/tool_calling_fixture/page3_img1.png"


def test_tool_calling_agent_emits_safe_runtime_events(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    events: list[ToolCallingRuntimeEvent] = []

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db).query(
            "What affects filling capacity?",
            top_k=2,
            max_tool_calls=3,
            event_sink=events.append,
        )

    assert not result.refused
    event_names = [event.event for event in events]
    assert "agent_step" in event_names
    assert "tool_call_start" in event_names
    assert "tool_call_result" in event_names
    serialized_payloads = " ".join(str(event.payload) for event in events)
    assert "raw_response" not in serialized_payloads
    assert "Bearer" not in serialized_payloads
    assert "reasoning_content" not in serialized_payloads


def test_tool_calling_agent_supports_multi_round_tool_calls(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    chat_provider = DeterministicChatModelProvider(
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="call_1",
                    name="hybrid_search_knowledge",
                    arguments={"query": "filling capacity", "top_k": 2},
                ),
            ),
            (
                ChatToolCall(
                    id="call_2",
                    name="search_knowledge",
                    arguments={"query": "self-compacting concrete flowability", "top_k": 2},
                ),
            ),
        )
    )

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db, chat_provider=chat_provider).query(
            "Compare filling capacity and flowability.",
            top_k=2,
            max_tool_calls=3,
        )

    assert not result.refused
    assert [call.tool_name for call in result.tool_calls] == [
        "hybrid_search_knowledge",
        "search_knowledge",
    ]
    assert result.tool_calls[0].succeeded
    assert not result.tool_calls[1].succeeded
    assert result.tool_calls[1].error == "existing evidence available; tool call skipped"
    assert result.latency_trace["executed_tool_call_count"] == 1
    assert result.latency_trace["skipped_tool_call_count"] == 1
    assert result.latency_trace["llm_call_count"] == 3


def test_tool_calling_agent_executes_one_search_per_iteration(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    chat_provider = DeterministicChatModelProvider(
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="call_1",
                    name="search_knowledge",
                    arguments={"query": "filling capacity", "top_k": 2},
                ),
                ChatToolCall(
                    id="call_2",
                    name="hybrid_search_knowledge",
                    arguments={"query": "self-compacting concrete flowability", "top_k": 2},
                ),
            ),
        )
    )

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db, chat_provider=chat_provider).query(
            "Compare filling capacity and flowability.",
            top_k=2,
            max_tool_calls=3,
        )

    assert not result.refused
    assert [call.tool_name for call in result.tool_calls] == [
        "search_knowledge",
        "hybrid_search_knowledge",
    ]
    assert not result.tool_calls[0].succeeded
    assert result.tool_calls[0].error == "per-iteration search tool budget reached"
    assert result.tool_calls[1].succeeded
    assert result.latency_trace["executed_tool_call_count"] == 1
    assert result.latency_trace["skipped_tool_call_count"] == 1


def test_tool_calling_agent_blocks_repeated_queries(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    chat_provider = DeterministicChatModelProvider(
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="call_1",
                    name="hybrid_search_knowledge",
                    arguments={"query": "filling capacity", "top_k": 2},
                ),
            ),
            (
                ChatToolCall(
                    id="call_2",
                    name="hybrid_search_knowledge",
                    arguments={"query": "filling capacity", "top_k": 2},
                ),
            ),
        )
    )

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db, chat_provider=chat_provider).query(
            "What affects filling capacity?",
            top_k=2,
            max_tool_calls=3,
        )

    assert result.latency_trace["repeated_query_count"] == 1
    assert result.latency_trace["near_duplicate_query_count"] == 1
    assert result.latency_trace["executed_tool_call_count"] == 1
    assert result.latency_trace["skipped_tool_call_count"] == 1
    assert result.tool_calls[1].error == "near-duplicate query skipped"


def test_tool_calling_agent_blocks_near_duplicate_queries(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    chat_provider = DeterministicChatModelProvider(
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="call_1",
                    name="hybrid_search_knowledge",
                    arguments={"query": "rock-filled concrete filling capacity", "top_k": 2},
                ),
            ),
            (
                ChatToolCall(
                    id="call_2",
                    name="hybrid_search_knowledge",
                    arguments={"query": "RFC filling capacity", "top_k": 2},
                ),
            ),
        )
    )

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db, chat_provider=chat_provider).query(
            "What affects RFC filling capacity?",
            top_k=2,
            max_tool_calls=3,
        )

    assert not result.refused
    assert result.latency_trace["near_duplicate_query_count"] == 1
    assert result.tool_calls[1].error == "near-duplicate query skipped"


def test_tool_calling_agent_repairs_missing_final_citations(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db, chat_provider=CitationRepairChatProvider()).query(
            "What affects filling capacity?",
            top_k=2,
            max_tool_calls=3,
        )

    assert not result.refused
    assert result.citations == [1]
    assert result.latency_trace["citation_repair_count"] == 1


def test_tool_calling_agent_converges_when_tool_errors(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = ToolCallingAgentService(
            db=db,
            embedding_provider=FailingEmbeddingProvider(),
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        ).query(
            "What affects filling capacity?",
            top_k=2,
            max_tool_calls=2,
        )

    assert result.refused
    assert result.tool_calls[0].tool_name == "hybrid_search_knowledge"
    assert result.tool_calls[0].error == "Embedding provider unavailable"
    assert "valid tool-backed citations" in (result.refusal_reason or "")


def test_tool_calling_agent_rejects_invalid_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        service = make_service(db)

        try:
            service.query("   ")
        except ValueError as exc:
            assert "question" in str(exc)
        else:
            raise AssertionError("blank question should fail")

        try:
            service.query("question", max_tool_calls=0)
        except ValueError as exc:
            assert "max_tool_calls" in str(exc)
        else:
            raise AssertionError("invalid max_tool_calls should fail")


def test_tool_calling_agent_refuses_off_topic_before_tool_loop(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = make_service(db).query("Give me a tomato soup recipe")

    assert result.refused
    assert result.tool_calls == []
    assert result.workflow_steps[0].tool_name == "off_topic_gate"
    assert "off-topic" in (result.refusal_reason or "")


def test_tool_calling_agent_respects_responsibility_gate(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = make_service(db).query("请判定这个配合比是否符合规范要求")

    assert result.refused
    assert result.tool_calls == []
    assert result.workflow_steps[0].tool_name == "responsibility_gate"


def test_tool_calling_structured_final_answer_prompt_is_default() -> None:
    messages = tool_calling_messages("What affects RFC filling capacity?")

    assert "structured_final_answer" in messages[0].content
    assert "citation-first compact structure" in messages[0].content
    assert "direct answer in one or two cited sentences" in messages[0].content
    assert "every requested aspect" in messages[0].content
    assert "4 to 6 bullets" in messages[0].content
    assert "quality control" in messages[0].content
    assert "Each factual sentence and each factual bullet" in messages[0].content
    assert "Do not omit a supported point" in messages[0].content
    assert "cite each side separately" in messages[0].content
    assert "evidence gap" in messages[0].content
    assert "concrete retrieved source title" in messages[0].content
    assert "generic 'source [1]'" in messages[0].content
    assert "Do not reveal internal outline" in messages[0].content


def test_tool_calling_tools_include_search_figures() -> None:
    tool_names = [tool.function.name for tool in tool_calling_tool_definitions()]

    assert tool_names == [
        "hybrid_search_knowledge",
        "search_knowledge",
        "search_figures",
        "search_tables",
    ]


def test_tool_calling_baseline_prompt_remains_available() -> None:
    messages = tool_calling_messages(
        "What affects RFC filling capacity?",
        final_answer_strategy="baseline",
    )

    assert "Final answer strategy: baseline" in messages[0].content
    assert "structured_final_answer" not in messages[0].content


def test_tool_calling_evidence_and_repair_prompts_use_structured_strategy() -> None:
    evidence_messages = evidence_answer_messages(
        "What affects RFC filling capacity?",
        sources=[],
        final_answer_strategy="structured_final_answer",
    )
    repair_messages = citation_repair_messages(
        "What affects RFC filling capacity?",
        draft_answer="Filling depends on flowability.",
        sources=[],
        final_answer_strategy="structured_final_answer",
    )

    assert "structured_final_answer" in evidence_messages[0].content
    assert "evidence gap" in evidence_messages[0].content
    assert "Do not add new facts" in repair_messages[0].content
    assert "not answer expansion" in repair_messages[0].content


def test_tool_calling_final_answer_strategy_validation(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        try:
            ToolCallingAgentService(
                db=db,
                embedding_provider=DeterministicEmbeddingProvider(dimension=32),
                chat_model_provider=DeterministicChatModelProvider(),
                final_answer_strategy="unsupported",  # type: ignore[arg-type]
            )
        except ValueError as exc:
            assert "final answer strategy" in str(exc)
        else:
            raise AssertionError("unsupported final answer strategy should fail")

    try:
        final_answer_strategy_instruction("unsupported")  # type: ignore[arg-type]
    except ValueError as exc:
        assert "final answer strategy" in str(exc)
    else:
        raise AssertionError("unsupported final answer strategy should fail")
