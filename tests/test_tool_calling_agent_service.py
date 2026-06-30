from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    AgentToolResult,
    AgentToolbox,
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
from app.services.agent.runtime import AgentRuntime, assemble_runtime_context
from app.core.config import get_settings
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelResult,
    ChatToolCall,
    ChatToolDefinition,
    DeterministicChatModelProvider,
    ToolCallingChatModelResult,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.vector_index import VectorIndexService


def make_session(tmp_path):
    database_path = tmp_path / "tool_calling_agent.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value.encode("utf-8")


def enable_tool_cache(monkeypatch, fake_redis: FakeRedis) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://phase58i-test")
    monkeypatch.setenv("LAYERED_CACHE_NAMESPACE", "phase58i-test")
    monkeypatch.setenv("TOOL_RESULT_CACHE_ENABLED", "true")
    monkeypatch.setenv("RETRIEVAL_CANDIDATE_CACHE_ENABLED", "false")
    monkeypatch.setenv("RERANK_ORDER_CACHE_ENABLED", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.cache.layered_cache.get_redis_client",
        lambda settings=None: fake_redis,
    )


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
    runtime_identity_provider=None,
) -> ToolCallingAgentService:
    provider = DeterministicEmbeddingProvider(dimension=32)
    VectorIndexService(db, provider).build_index()
    return ToolCallingAgentService(
        db=db,
        embedding_provider=provider,
        chat_model_provider=chat_provider or DeterministicChatModelProvider(),
        runtime_identity_provider=runtime_identity_provider,
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


class VisualFollowupChatProvider:
    provider_name = "visual-followup-test"
    model_name = "visual-followup-test-v1"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer="The requested visual evidence is available [1].",
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
                        id="call_figure",
                        name="search_figures",
                        arguments={"query": "我需要图片支撑", "top_k": 4},
                    )
                ],
                provider=self.provider_name,
                model_name=self.model_name,
            )
        return ToolCallingChatModelResult(
            content="The requested visual evidence is available [1].",
            tool_calls=[],
            provider=self.provider_name,
            model_name=self.model_name,
        )


class RuntimeIdentityProvider:
    provider_name = "runtime-identity-test"
    model_name = "runtime-identity-test-v1"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer=(
                '{"entity_key":"rock-filled concrete",'
                '"intent_key":"crack_phenomena",'
                '"canonical_query":"堆石混凝土 rock-filled concrete 裂缝 缝隙 裂纹 开裂",'
                '"confidence":0.9,'
                '"safe_for_cache_reuse":true}'
            ),
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def stream_generate(self, messages: list[ChatMessage]):
        yield self.generate(messages).answer

    def generate_with_tools(self, messages, tools):  # pragma: no cover - not used.
        raise AssertionError("runtime identity provider should not select tools")


class IdentityAndHydeProvider(RuntimeIdentityProvider):
    model_name = "identity-hyde-test-v1"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        latest = messages[-1].content if messages else ""
        if "required_json_schema" in latest:
            return super().generate(messages)
        return ChatModelResult(
            answer=(
                "Rock-filled concrete crack phenomena may involve defects, "
                "interfaces, aggregate voids, and damage characterization."
            ),
            provider=self.provider_name,
            model_name=self.model_name,
        )


class CachedEvidenceAnswerProvider(DeterministicChatModelProvider):
    provider_name = "cached-answer-test"
    model_name = "cached-answer-test-v1"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer="Fresh answer generated from cached evidence [1].",
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def generate_with_tools(self, messages, tools):  # pragma: no cover - should be skipped.
        raise AssertionError("semantic evidence cache hit should skip tool selection")


def test_agent_runtime_contextualizes_visual_followup() -> None:
    context = assemble_runtime_context(
        "我需要图片支撑",
        history=("大坝的裂缝成因有哪些？请给我详细列出来",),
    )

    assert context.followup_type == "visual_evidence_request"
    assert context.contextualized
    assert context.inherited_topic == "大坝的裂缝成因有哪些？请给我详细列出来"
    assert "大坝" in context.standalone_task
    assert "图片" in context.standalone_task


def test_agent_runtime_does_not_inherit_for_standalone_new_topic() -> None:
    context = assemble_runtime_context(
        "堆石混凝土的自密实性能如何评价？",
        history=("大坝的裂缝成因有哪些？请给我详细列出来",),
    )

    assert context.followup_type == "standalone"
    assert not context.contextualized
    assert context.inherited_topic == ""
    assert context.standalone_task == "堆石混凝土的自密实性能如何评价？"


def test_agent_runtime_grounds_tool_arguments_by_tool() -> None:
    runtime = AgentRuntime()
    state = runtime.assemble(
        "给我表格",
        history=("堆石混凝土配合比设计参数有哪些？",),
    )
    grounded_call, grounding = runtime.ground_tool_call(
        ChatToolCall(
            id="call_table",
            name="search_tables",
            arguments={"query": "给我表格", "top_k": 3},
        ),
        state=state,
        default_query="给我表格",
    )

    assert grounding.rewrite_applied
    assert grounding.reason == "grounded_table_followup"
    assert "配合比" in grounded_call.arguments["query"]
    assert "表格" in grounded_call.arguments["query"]


def test_tool_calling_agent_uses_llm_runtime_identity_for_open_synonyms(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(
            db,
            runtime_identity_provider=RuntimeIdentityProvider(),
        ).query(
            "堆石混凝土的裂纹问题",
            top_k=2,
            max_tool_calls=2,
        )

    trace = result.latency_trace
    assert trace["evidence_cache_identity_source"] == "llm"
    assert trace["evidence_cache_identity_model_name"] == "runtime-identity-test-v1"
    assert trace["evidence_entity_key"] == "rock-filled concrete"
    assert trace["evidence_intent_key"] == "crack_phenomena"
    assert trace["evidence_cache_reuse_allowed"] is True
    assert trace["runtime_contextualization_source"] == "llm"


def test_tool_calling_agent_semantic_evidence_cache_hit_skips_tool_selection(
    monkeypatch,
    tmp_path,
) -> None:
    fake_redis = FakeRedis()
    enable_tool_cache(monkeypatch, fake_redis)
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        provider = DeterministicEmbeddingProvider(dimension=32)
        VectorIndexService(db, provider).build_index()
        toolbox = AgentToolbox(
            db,
            embedding_provider=provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        trace = LatencyTrace()
        trace.set_value("evidence_cache_reuse_allowed", True)
        trace.set_value("evidence_entity_key", "rock-filled concrete")
        trace.set_value("evidence_intent_key", "crack_phenomena")
        trace.set_value("evidence_canonical_query", "堆石混凝土 rock-filled concrete 裂缝 缝隙 裂纹 开裂")
        token = set_current_latency_trace(trace)
        try:
            first = toolbox.hybrid_search_knowledge("filling capacity rock-filled concrete", top_k=1)
        finally:
            reset_current_latency_trace(token)
        events = []
        second = make_service(
            db,
            chat_provider=CachedEvidenceAnswerProvider(),
            runtime_identity_provider=RuntimeIdentityProvider(),
        ).query(
            "堆石混凝土缝隙问题",
            top_k=1,
            max_tool_calls=2,
            event_sink=events.append,
        )

    assert first.sources
    assert second.answer == "Fresh answer generated from cached evidence [1]."
    assert second.latency_trace["semantic_cache_hit"] is True
    assert second.latency_trace["tool_result_cache_hit"] is True
    assert second.latency_trace["hyde_generated"] is False
    assert second.latency_trace["executed_tool_call_count"] == 0
    assert [event.event for event in events] == ["tool_call_result"]
    assert events[0].payload["tool_name"] == "hybrid_search_knowledge"
    assert "cache hit" in events[0].payload["observation_summary"]


def test_tool_calling_agent_generates_hyde_only_on_semantic_cache_miss(
    monkeypatch,
    tmp_path,
) -> None:
    fake_redis = FakeRedis()
    enable_tool_cache(monkeypatch, fake_redis)
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(
            db,
            runtime_identity_provider=IdentityAndHydeProvider(),
        ).query(
            "堆石混凝土裂纹问题",
            top_k=2,
            max_tool_calls=2,
        )

    assert result.sources
    assert result.latency_trace["semantic_cache_hit"] is False
    assert result.latency_trace["hyde_generated"] is True
    assert result.latency_trace["hyde_used_for_vector"] is True
    assert result.latency_trace["hyde_model"] == "runtime-identity-test/identity-hyde-test-v1"
    assert all("Hypothetical evidence" not in (source.content or "") for source in result.sources)


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


def test_tool_calling_agent_stops_when_reranking_fails(tmp_path, monkeypatch) -> None:
    TestingSessionLocal = make_session(tmp_path)

    def fail_hybrid_search(self, query: str, top_k: int = 5, progress_callback=None) -> AgentToolResult:
        message = "重排序失效：主 reranker 失败，GLM fallback reranker 也失败。"
        return AgentToolResult(
            tool_name="hybrid_search_knowledge",
            call=AgentToolCallRecord(
                tool_name="hybrid_search_knowledge",
                input_summary=f"query={query}; top_k={top_k}",
                output_summary=message,
                succeeded=False,
                error=message,
            ),
            refused=True,
            refusal_reason=message,
        )

    monkeypatch.setattr(
        "app.services.agent.tools.AgentToolbox.hybrid_search_knowledge",
        fail_hybrid_search,
    )

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db).query(
            "What affects filling capacity in rock-filled concrete?",
            top_k=2,
            max_tool_calls=3,
        )

    assert result.refused
    assert "重排序失效" in result.answer
    assert result.refusal_reason == result.answer
    assert len(result.tool_calls) == 1
    assert not result.tool_calls[0].succeeded
    assert result.latency_trace["runtime_stop_reason"] == "reranking_failed"
    assert result.latency_trace["runtime_final_decision"] == "refuse"


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


def test_tool_calling_runtime_grounds_visual_followup_tool_query(
    tmp_path,
    monkeypatch,
) -> None:
    TestingSessionLocal = make_session(tmp_path)
    executed_queries: list[str] = []

    figure_item = AgentSearchItem(
        document_id=2,
        document_title="Dam crack cause figure",
        source_type="local_file",
        source_path="dam-crack.pdf",
        file_name="dam-crack.pdf",
        chunk_id=30,
        chunk_index=1,
        content="Dam crack morphology figure related to crack causes.",
        heading_path="Figure",
        score=0.88,
        chunk_type="image_description",
        source_image_path="data/images/tool_calling_fixture/page4_img1.png",
        image_url="/assets/images/tool_calling_fixture/page4_img1.png",
        caption="大坝裂缝形态图",
        page_number=4,
    )
    figure_source = AgentSourceReference(
        source_id="chunk:30",
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
        executed_queries.append(query)
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
        result = make_service(db, chat_provider=VisualFollowupChatProvider()).query(
            "我需要图片支撑",
            history=("大坝的裂缝成因有哪些？请给我详细列出来",),
            top_k=4,
            max_tool_calls=3,
        )

    assert not result.refused
    assert executed_queries
    assert executed_queries[0] != "我需要图片支撑"
    assert "大坝" in executed_queries[0]
    assert "裂缝" in executed_queries[0]
    assert "图片" in executed_queries[0]
    assert result.latency_trace["runtime_followup_type"] == "visual_evidence_request"
    assert result.latency_trace["runtime_tool_arg_rewrite_count"] == 1
    assert result.latency_trace["runtime_evidence_counts"]["figure"] == 1


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
    assert "citation-first balanced source-backed structure" in messages[0].content
    assert "direct answer in one or two cited sentences" in messages[0].content
    assert "every requested aspect" in messages[0].content
    assert "4 to 6 bullets" in messages[0].content
    assert "advantages, causes, classifications, measures" in messages[0].content
    assert "do not stop at bare labels" in messages[0].content
    assert "Only use title-only bullets" in messages[0].content
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
