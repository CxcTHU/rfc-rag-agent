from types import SimpleNamespace

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.agent.service import AgentQueryResult
from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    AgentToolResult,
    AgentToolbox,
)
from app.services.agent.evidence_identity import (
    build_evidence_query_identity,
    refine_evidence_query_identity_with_llm,
)
from app.services.agent.tool_calling_service import (
    ToolCallingAgentService,
    ToolCallingCoordinatorGateAdapter,
    ToolCallingFinalAnswerFacade,
    ToolCallingRuntimeEvent,
    build_tool_calling_combined_pre_tool_gate_decision,
    build_tool_calling_pre_tool_gate_decision,
    build_tool_calling_resume_gate_decision,
    build_tool_calling_semantic_cache_gate_decision,
    citation_repair_messages,
    evidence_answer_messages,
    executable_tool_call_ids,
    final_answer_strategy_instruction,
    tool_calling_tool_definitions,
    tool_calling_messages,
)
from app.services.agent.run_coordinator import RunCoordinator
from app.services.agent.runtime_contracts import CoordinatorRequest, FinalAnswerRequest, RunBudget
from app.services.agent.runtime_events import RuntimeEventBus
from app.services.agent.runtime import (
    AgentRuntime,
    AgentRuntimeState,
    RuntimeContext,
    assemble_runtime_context,
)
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
from app.services.retrieval.runtime import (
    build_retrieval_plan,
    reset_current_retrieval_plan,
    retrieval_runtime_result_limit,
    set_current_retrieval_plan,
)
from app.services.observability.latency_trace import (
    LatencyTrace,
    bind_agent_conversation_cache_scope,
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
    monkeypatch.setenv("SEMANTIC_EVIDENCE_CACHE_ENABLED", "true")
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
    final_answer_strategy="structured_final_answer",
) -> ToolCallingAgentService:
    provider = DeterministicEmbeddingProvider(dimension=32)
    VectorIndexService(db, provider).build_index()
    return ToolCallingAgentService(
        db=db,
        embedding_provider=provider,
        chat_model_provider=chat_provider or DeterministicChatModelProvider(),
        runtime_identity_provider=runtime_identity_provider,
        final_answer_strategy=final_answer_strategy,
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


class FailingFinalStreamChatProvider(CitationRepairChatProvider):
    provider_name = "failing-final-stream-test"
    model_name = "failing-final-stream-test-v1"

    def stream_generate(self, messages: list[ChatMessage]):
        raise RuntimeError("final answer stream failed")
        yield ""  # pragma: no cover - keeps this as a generator for Protocol users.


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


class RelationshipRuntimeIdentityProvider(RuntimeIdentityProvider):
    model_name = "runtime-relationship-intent-v1"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer=(
                '{"entity_key":"rock-filled concrete",'
                '"intent_key":"causal_relationship",'
                '"canonical_query":"rock-filled concrete filling capacity causes",'
                '"confidence":0.95,'
                '"safe_for_cache_reuse":true,'
                '"relationship_intent":0.96,'
                '"relationship_type":"causal",'
                '"graph_search_mode":"local",'
                '"relationship_explicitness":"explicit",'
                '"required_evidence_types":["text","relationship"]}'
            ),
            provider=self.provider_name,
            model_name=self.model_name,
        )


class UncitedStreamingChatProvider(CitationRepairChatProvider):
    emitted_tokens: list[str]

    def __init__(self) -> None:
        self.emitted_tokens = []

    def stream_generate(self, messages: list[ChatMessage]):
        yield "Filling capacity depends on SCC flowability."

    def emit_stream_token(self, token: str) -> None:
        self.emitted_tokens.append(token)


class ForbiddenRuntimeIdentityProvider(RuntimeIdentityProvider):
    model_name = "runtime-identity-must-not-run"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        raise AssertionError("safe deterministic identity must keep the fast path")


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


class StrategyCapturingFinalAnswerProvider(DeterministicChatModelProvider):
    provider_name = "deterministic"
    model_name = "strategy-capturing-final-answer-v1"

    def __init__(self) -> None:
        super().__init__()
        self.final_messages: list[ChatMessage] = []

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        self.final_messages = messages
        return ChatModelResult(
            answer="Filling capacity depends on SCC flowability [1].",
            provider=self.provider_name,
            model_name=self.model_name,
        )


class WrappedFinalAnswerProvider(DeterministicChatModelProvider):
    provider_name = "deterministic"
    model_name = "wrapped-final-answer-v1"

    def __init__(self) -> None:
        super().__init__()
        self.called = False

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        self.called = True
        return ChatModelResult(
            answer="Wrapped final answer [1].",
            provider=self.provider_name,
            model_name=self.model_name,
        )


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
            max_tool_calls=2,
        )

    trace = result.latency_trace
    assert trace["evidence_cache_identity_source"] == "llm"
    assert trace["evidence_cache_identity_model_name"] == "runtime-identity-test-v1"
    assert trace["evidence_entity_key"] == "rock-filled concrete"
    assert trace["evidence_intent_key"] == "crack_phenomena"
    assert trace["evidence_cache_reuse_allowed"] is True
    assert trace["runtime_contextualization_source"] == "llm"


def test_phase63_tool_calling_binds_identity_intent_to_retrieval_runtime(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        service = make_service(
            db,
            chat_provider=CitationRepairChatProvider(),
            runtime_identity_provider=RelationshipRuntimeIdentityProvider(),
        )
        settings = get_settings()
        original = settings.retrieval_runtime_enabled
        settings.retrieval_runtime_enabled = True
        try:
            result = service.query(
                "What causes rock-filled concrete filling capacity?",
                max_tool_calls=2,
            )
        finally:
            settings.retrieval_runtime_enabled = original

    assert result.latency_trace["retrieval_plan_schema"] == "phase63-gap-closure-v1"
    assert result.latency_trace["retrieval_graph_requirement"] == "required"
    assert result.latency_trace["retrieval_graph_max_hops"] == 2
    assert result.latency_trace["retrieval_plan_digest"] != "legacy"


def test_phase63_safe_deterministic_identity_skips_llm_classifier(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        service = make_service(
            db,
            chat_provider=CitationRepairChatProvider(),
            runtime_identity_provider=ForbiddenRuntimeIdentityProvider(),
        )
        settings = get_settings()
        original = settings.retrieval_runtime_enabled
        settings.retrieval_runtime_enabled = True
        try:
            result = service.query(
                "堆石混凝土的优势有哪些？",
                max_tool_calls=2,
            )
        finally:
            settings.retrieval_runtime_enabled = original

    assert result.latency_trace["evidence_cache_identity_source"] == "deterministic"
    assert result.latency_trace["evidence_cache_reuse_allowed"] is True


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
        bind_agent_conversation_cache_scope(trace, 101)
        trace.set_value("evidence_cache_reuse_allowed", True)
        trace.set_value("evidence_entity_key", "rock-filled concrete")
        trace.set_value("evidence_intent_key", "crack_phenomena")
        trace.set_value("evidence_canonical_query", "堆石混凝土 rock-filled concrete 裂缝 缝隙 裂纹 开裂")
        token = set_current_latency_trace(trace)
        identity = refine_evidence_query_identity_with_llm(
            "堆石混凝土缝隙问题",
            base_identity=build_evidence_query_identity("堆石混凝土缝隙问题"),
            provider=RuntimeIdentityProvider(),
        )
        retrieval_token = set_current_retrieval_plan(
            build_retrieval_plan(
                identity.retrieval_intent,
                identity.canonical_query,
                get_settings(),
            )
        )
        try:
            first = toolbox.hybrid_search_knowledge(
                "filling capacity rock-filled concrete",
                top_k=retrieval_runtime_result_limit("hybrid_search_knowledge"),
            )
        finally:
            reset_current_retrieval_plan(retrieval_token)
            reset_current_latency_trace(token)
        events = []
        second = make_service(
            db,
            chat_provider=CachedEvidenceAnswerProvider(),
            runtime_identity_provider=RuntimeIdentityProvider(),
        ).query(
            "堆石混凝土缝隙问题",
            max_tool_calls=2,
            conversation_id=101,
            event_sink=events.append,
        )

    assert first.sources
    assert second.answer == "Fresh answer generated from cached evidence [1]."
    assert second.latency_trace["semantic_cache_hit"] is True
    assert second.latency_trace["tool_result_cache_hit"] is True
    assert second.latency_trace["hyde_generated"] is False
    assert second.latency_trace["executed_tool_call_count"] == 0
    tool_result_events = [event for event in events if event.event == "tool_call_result"]
    assert len(tool_result_events) == 1
    assert tool_result_events[0].payload["tool_name"] == "hybrid_search_knowledge"
    assert "cache hit" in tool_result_events[0].payload["observation_summary"]


def test_tool_calling_agent_semantic_evidence_cache_is_scoped_to_conversation(
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
        bind_agent_conversation_cache_scope(trace, 201)
        trace.set_value("evidence_cache_reuse_allowed", True)
        trace.set_value("evidence_entity_key", "rock-filled concrete")
        trace.set_value("evidence_intent_key", "crack_phenomena")
        trace.set_value("evidence_canonical_query", "堆石混凝土 rock-filled concrete 裂缝 缝隙 裂纹 开裂")
        token = set_current_latency_trace(trace)
        try:
            first = toolbox.hybrid_search_knowledge(
                "filling capacity rock-filled concrete",
                top_k=get_settings().reranking_dynamic_max_results,
            )
        finally:
            reset_current_latency_trace(token)

        second = make_service(
            db,
            runtime_identity_provider=RuntimeIdentityProvider(),
        ).query(
            "rock-filled concrete crack question",
            max_tool_calls=2,
            conversation_id=202,
        )

    assert first.sources
    assert second.latency_trace["semantic_cache_hit"] is False
    assert second.latency_trace["tool_result_cache_hit"] is False
    assert second.latency_trace["agent_cache_scope"] == "conversation:202"


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
            max_tool_calls=2,
        )

    assert result.sources
    assert result.latency_trace["semantic_cache_hit"] is False
    assert result.latency_trace["hyde_generated"] is True
    assert result.latency_trace["hyde_used_for_vector"] is True
    assert result.latency_trace["hyde_model"] == "runtime-identity-test/identity-hyde-test-v1"
    assert all("Hypothetical evidence" not in (source.content or "") for source in result.sources)


def test_tool_calling_agent_searches_then_returns_cited_answer(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "false")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)

    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(db).query(
                "What affects filling capacity in rock-filled concrete?",
                max_tool_calls=3,
            )
    finally:
        get_settings.cache_clear()

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
            max_tool_calls=3,
        )

    assert not result.refused
    assert "search_figures" in [call.tool_name for call in result.tool_calls]
    image_sources = [source for source in result.sources if source.image_url]
    assert image_sources
    assert image_sources[0].caption == "图3-4 堆石混凝土应力应变曲线"
    assert image_sources[0].page_number == 3
    assert image_sources[0].image_url == "/assets/images/tool_calling_fixture/page3_img1.png"


def test_tool_calling_runtime_preflights_explicit_table_request(tmp_path, monkeypatch) -> None:
    TestingSessionLocal = make_session(tmp_path)
    calls: list[str] = []
    events: list[ToolCallingRuntimeEvent] = []
    table_item = AgentSearchItem(
        document_id=1,
        document_title="Rock-filled concrete mix table",
        source_type="local_file",
        source_path="mix.md",
        file_name="mix.md",
        chunk_id=30,
        chunk_index=0,
        content="Table: SCC mix ratio for rock-filled concrete.",
        heading_path="Mix ratio",
        score=0.9,
        chunk_type="table",
    )
    table_source = AgentSourceReference(
        source_id="chunk:30",
        title=table_item.document_title,
        source_type=table_item.source_type,
        document_id=table_item.document_id,
        chunk_id=table_item.chunk_id,
        chunk_index=table_item.chunk_index,
        content=table_item.content,
        score=table_item.score,
        chunk_type="table",
    )

    def fake_search_tables(self, query: str, top_k: int = 4) -> AgentToolResult:
        calls.append(query)
        return AgentToolResult(
            tool_name="search_tables",
            call=AgentToolCallRecord(
                tool_name="search_tables",
                input_summary=f"query={query}; top_k={top_k}",
                output_summary="returned 1 table results",
                succeeded=True,
            ),
            search_results=[table_item],
            sources=[table_source],
        )

    monkeypatch.setattr(
        "app.services.agent.tools.AgentToolbox.search_tables",
        fake_search_tables,
    )
    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db).query(
            "请列出堆石混凝土配合比表格",
            max_tool_calls=3,
            event_sink=events.append,
        )

    assert calls
    assert result.tool_calls[0].tool_name == "search_tables"
    assert result.sources[0].chunk_type == "table"
    assert result.latency_trace["retrieval_required_tool"] == "search_tables"
    preflight_event = next(
        event
        for event in events
        if event.event == "tool_call_result"
        and event.payload["step_id"] == "runtime-search_tables"
    )
    assert preflight_event.payload["selected_count"] == 1
    assert result.latency_trace["retrieval_selected_count"] == 1


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
            max_tool_calls=3,
        )

    assert not result.refused
    assert executed_queries
    assert executed_queries[0] != "我需要图片支撑"
    assert "大坝" in executed_queries[0]
    assert "裂缝" in executed_queries[0]
    assert "图片" in executed_queries[0]
    assert result.latency_trace["runtime_followup_type"] == "visual_evidence_request"
    assert result.latency_trace["runtime_tool_arg_rewrite_count"] == 0
    assert result.latency_trace["runtime_evidence_counts"]["figure"] == 1


def test_tool_calling_final_stream_failure_returns_safe_cold_receipt(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TOOL_RESULT_CACHE_ENABLED", "false")
    monkeypatch.setenv("SEMANTIC_EVIDENCE_CACHE_ENABLED", "false")
    monkeypatch.setenv("RETRIEVAL_CANDIDATE_CACHE_ENABLED", "false")
    monkeypatch.setenv("RERANK_ORDER_CACHE_ENABLED", "false")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)

    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(db, chat_provider=FailingFinalStreamChatProvider()).query(
                "What affects filling capacity in rock-filled concrete?",
                evaluation_run_namespace="phase65-final-stream-failure-test",
            )
    finally:
        get_settings.cache_clear()

    assert result.refused is False
    assert result.tool_calls
    assert result.tool_calls[0].succeeded is True
    assert result.citations == [1]
    assert result.latency_trace["runtime_stop_reason"] == "final_generation_failed"
    assert result.latency_trace["final_generation_failed"] is True
    assert {
        "retrieval_cache_hit": result.latency_trace["retrieval_cache_hit"],
        "rerank_cache_primary_hit": result.latency_trace["rerank_cache_primary_hit"],
        "tool_result_cache_hit": result.latency_trace["tool_result_cache_hit"],
    } == {
        "retrieval_cache_hit": False,
        "rerank_cache_primary_hit": False,
        "tool_result_cache_hit": False,
    }
    receipt = result.latency_trace["evaluation_cold_cache_receipt"]
    assert receipt["schema_version"] == "phase65-cold-cache-receipt-v1"
    assert receipt["cache_miss_confirmed"] is True


def test_tool_calling_visual_followup_empty_figures_stops_with_clear_reason(
    tmp_path,
    monkeypatch,
) -> None:
    TestingSessionLocal = make_session(tmp_path)
    executed_queries: list[str] = []

    def fake_search_figures(self, query: str, top_k: int = 4) -> AgentToolResult:
        executed_queries.append(query)
        return AgentToolResult(
            tool_name="search_figures",
            call=AgentToolCallRecord(
                tool_name="search_figures",
                input_summary=f"query={query}; top_k={top_k}",
                output_summary=(
                    "returned 0 figure results; threshold=0.35; "
                    "vector_backend=pgvector_hnsw; skipped_specific_mismatch=3"
                ),
                succeeded=True,
            ),
            search_results=[],
            sources=[],
            refused=True,
            refusal_reason="No relevant figure results were found.",
        )

    monkeypatch.setattr(
        "app.services.agent.tools.AgentToolbox.search_figures",
        fake_search_figures,
    )

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db, chat_provider=VisualFollowupChatProvider()).query(
            "\u6211\u9700\u8981\u56fe\u7247\u652f\u6491",
            history=(
                "\u5927\u575d\u7684\u88c2\u7f1d\u6210\u56e0\u6709\u54ea\u4e9b\uff1f"
                "\u8bf7\u7ed9\u6211\u8be6\u7ec6\u5217\u51fa\u6765",
            ),
            max_tool_calls=3,
        )

    assert result.refused
    assert result.refusal_reason == "No relevant figure results were found."
    assert result.answer == "No relevant figure results were found."
    assert len(executed_queries) == 1
    assert result.tool_calls[0].tool_name == "search_figures"
    assert result.latency_trace["runtime_stop_reason"] in {
        "required_asset_evidence_not_found",
        "required_evidence_missing",
    }


def test_tool_calling_agent_emits_safe_runtime_events(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    events: list[ToolCallingRuntimeEvent] = []

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db).query(
            "What affects filling capacity?",
            max_tool_calls=3,
            event_sink=events.append,
        )

    assert not result.refused
    event_names = [event.event for event in events]
    assert "agent_step" in event_names
    assert "tool_call_start" in event_names
    assert "tool_call_result" in event_names
    start_event = next(event for event in events if event.event == "tool_call_start")
    result_event = next(event for event in events if event.event == "tool_call_result")
    assert start_event.payload["step_id"] == result_event.payload["step_id"]
    assert result.workflow_steps[0].step_id == start_event.payload["step_id"]
    assert result_event.payload["selected_count"] == result.latency_trace["retrieval_selected_count"]
    serialized_payloads = " ".join(str(event.payload) for event in events)
    assert "raw_response" not in serialized_payloads
    assert "Bearer" not in serialized_payloads
    assert "reasoning_content" not in serialized_payloads


def test_tool_calling_agent_streams_after_first_successful_evidence_round(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "false")
    get_settings.cache_clear()
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

    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(db, chat_provider=chat_provider).query(
                "Compare filling capacity and flowability.",
                max_tool_calls=3,
            )
    finally:
        get_settings.cache_clear()

    assert not result.refused
    assert [call.tool_name for call in result.tool_calls] == ["hybrid_search_knowledge"]
    assert result.tool_calls[0].succeeded
    assert result.latency_trace["executed_tool_call_count"] == 1
    assert result.latency_trace["skipped_tool_call_count"] == 0
    assert result.latency_trace["llm_call_count"] == 2
    assert result.latency_trace["streamed_token_count"] > 0


def test_tool_calling_agent_executes_one_search_per_iteration(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "false")
    get_settings.cache_clear()
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

    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(db, chat_provider=chat_provider).query(
                "Compare filling capacity and flowability.",
                max_tool_calls=3,
            )
    finally:
        get_settings.cache_clear()

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


def test_explicit_figure_intent_prioritizes_figure_tool_within_budget() -> None:
    tool_calls = (
        ChatToolCall(
            id="hybrid",
            name="hybrid_search_knowledge",
            arguments={"query": "堆石混凝土破坏形态", "top_k": 8},
        ),
        ChatToolCall(
            id="figures",
            name="search_figures",
            arguments={"query": "堆石混凝土破坏形态图片", "top_k": 8},
        ),
    )

    executable = executable_tool_call_ids(
        tool_calls,
        previous_tool_queries=(),
        sources_available=False,
        preferred_tool_name="search_figures",
    )

    assert executable == {"figures"}


def test_tool_calling_agent_does_not_request_duplicate_after_evidence_converges(tmp_path) -> None:
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
            max_tool_calls=3,
        )

    assert result.latency_trace["repeated_query_count"] == 0
    assert result.latency_trace["near_duplicate_query_count"] == 0
    assert result.latency_trace["executed_tool_call_count"] == 1
    assert result.latency_trace["skipped_tool_call_count"] == 0
    assert len(result.tool_calls) == 1


def test_tool_calling_agent_does_not_request_near_duplicate_after_evidence_converges(tmp_path) -> None:
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
            max_tool_calls=3,
        )

    assert not result.refused
    assert result.latency_trace["near_duplicate_query_count"] == 0
    assert len(result.tool_calls) == 1
    assert result.latency_trace["streamed_token_count"] > 0


def test_tool_calling_agent_streams_cited_final_answer_without_repair(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_tool_calling_documents(db)
        result = make_service(db, chat_provider=CitationRepairChatProvider()).query(
            "What affects filling capacity?",
            max_tool_calls=3,
        )

    assert not result.refused
    assert result.citations == [1]
    assert result.latency_trace["citation_repair_count"] == 0
    assert result.latency_trace["streamed_token_count"] > 0


def test_tool_calling_agent_streams_safe_citation_suffix_for_uncited_answer(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "false")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)
    chat_provider = UncitedStreamingChatProvider()

    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(db, chat_provider=chat_provider).query(
                "What affects filling capacity?",
                max_tool_calls=3,
            )
    finally:
        get_settings.cache_clear()

    assert not result.refused
    assert result.citations == [1]
    assert result.answer.endswith("证据引用：[1]")
    assert chat_provider.emitted_tokens == ["\n\n证据引用：[1]"]
    assert result.latency_trace["citation_repair_count"] == 0


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


def test_pre_tool_gate_decision_refuses_off_topic_without_resume() -> None:
    runtime_state = AgentRuntimeState(
        context=RuntimeContext(current_query="Give me a tomato soup recipe")
    )

    decision = build_tool_calling_pre_tool_gate_decision(
        question="Give me a tomato soup recipe",
        runtime_state=runtime_state,
        resume_should_resume=False,
        latency_trace=LatencyTrace(),
    )

    assert decision.action == "return"
    assert decision.final_decision == "refuse"
    assert decision.sanitized_detail == "off_topic"
    assert decision.result is not None
    assert decision.result.workflow_steps[0].tool_name == "off_topic_gate"


def test_pre_tool_gate_decision_allows_off_topic_resume() -> None:
    runtime_state = AgentRuntimeState(
        context=RuntimeContext(current_query="Give me a tomato soup recipe")
    )

    decision = build_tool_calling_pre_tool_gate_decision(
        question="Give me a tomato soup recipe",
        runtime_state=runtime_state,
        resume_should_resume=True,
        latency_trace=LatencyTrace(),
    )

    assert decision.action == "continue"
    assert decision.result is None


def test_resume_gate_decision_continues_without_resumable_run() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))

    decision = build_tool_calling_resume_gate_decision(
        question="问题",
        resume_decision=SimpleNamespace(should_resume=False, run=None),
        chat_model_provider=DeterministicChatModelProvider(),
        history=None,
        final_answer_strategy="structured_final_answer",
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
    )

    assert decision.action == "continue"
    assert decision.result is None


def test_resume_gate_decision_returns_checkpoint_result_without_sources() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    run = SimpleNamespace(state_json='{"sources":[],"workflow_steps":[]}')

    decision = build_tool_calling_resume_gate_decision(
        question="问题",
        resume_decision=SimpleNamespace(should_resume=True, run=run),
        chat_model_provider=DeterministicChatModelProvider(),
        history=None,
        final_answer_strategy="structured_final_answer",
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
    )

    assert decision.action == "return"
    assert decision.final_decision == "refuse"
    assert decision.stop_reason == "checkpoint_unavailable"
    assert decision.sanitized_detail == "resume_checkpoint_without_sources"
    assert decision.result is not None
    assert decision.result.refused
    assert decision.result.workflow_steps[0].tool_name == "runtime_resume"


def test_semantic_cache_gate_continues_when_disabled() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    toolbox = SimpleNamespace(
        lookup_semantic_evidence_cache=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("disabled semantic cache gate must not query cache")
        )
    )

    decision = build_tool_calling_semantic_cache_gate_decision(
        question="问题",
        settings=SimpleNamespace(semantic_evidence_cache_enabled=False),
        evidence_identity=SimpleNamespace(safe_for_cache_reuse=True),
        toolbox=toolbox,
        chat_model_provider=CachedEvidenceAnswerProvider(),
        history=None,
        final_answer_strategy="structured_final_answer",
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
        runtime_event_bus=RuntimeEventBus(run_id="test"),
        workflow_steps=[],
        tool_calls=[],
    )

    assert decision.action == "continue"
    assert decision.result is None


def test_semantic_cache_gate_returns_cached_evidence_result_and_event() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    trace = LatencyTrace()
    events = []
    bus = RuntimeEventBus(run_id="test", trace=trace)
    bus.subscribe(events.append)
    call = AgentToolCallRecord(
        tool_name="hybrid_search_knowledge",
        input_summary="query=cache",
        output_summary="cache hit selected=1",
        succeeded=True,
        step_id="cache-1",
    )
    item = AgentSearchItem(
        document_id=1,
        document_title="来源标题",
        source_type="local",
        source_path=None,
        file_name="source.md",
        chunk_id=10,
        chunk_index=0,
        content="缓存证据",
        heading_path=None,
        score=0.9,
    )
    source = AgentSourceReference(
        source_id="s1",
        title="来源标题",
        source_type="local",
        content="缓存证据",
    )
    cached = AgentToolResult(
        tool_name="hybrid_search_knowledge",
        call=call,
        search_results=[item],
        sources=[source],
    )
    toolbox = SimpleNamespace(
        lookup_semantic_evidence_cache=lambda *_args, **_kwargs: cached
    )
    workflow_steps: list[AgentToolCallRecord] = []
    tool_calls: list[AgentToolCallRecord] = []

    decision = build_tool_calling_semantic_cache_gate_decision(
        question="问题",
        settings=SimpleNamespace(
            semantic_evidence_cache_enabled=True,
            reranking_dynamic_max_results=8,
            reranking_dynamic_min_results=4,
            reranking_recall_k=8,
        ),
        evidence_identity=SimpleNamespace(
            safe_for_cache_reuse=True,
            intent_key="",
            canonical_query="cache query",
        ),
        toolbox=toolbox,
        chat_model_provider=CachedEvidenceAnswerProvider(),
        history=None,
        final_answer_strategy="structured_final_answer",
        runtime_state=runtime_state,
        latency_trace=trace,
        runtime_event_bus=bus,
        workflow_steps=workflow_steps,
        tool_calls=tool_calls,
    )

    assert decision.action == "return"
    assert decision.final_decision == "answer"
    assert decision.sanitized_detail == "semantic_evidence_cache_hit"
    assert decision.result is not None
    assert decision.result.answer == "Fresh answer generated from cached evidence [1]."
    assert decision.result.latency_trace["semantic_cache_hit"] is True
    assert workflow_steps == [call]
    assert tool_calls == [call]
    assert events[0].name == "tool_call_result"
    assert events[0].payload["selected_count"] == 1


def test_combined_pre_tool_gate_short_circuits_before_resume_or_cache() -> None:
    runtime_state = AgentRuntimeState(
        context=RuntimeContext(current_query="Give me a tomato soup recipe")
    )
    toolbox = SimpleNamespace(
        lookup_semantic_evidence_cache=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("pre-tool refusal must short-circuit semantic cache")
        )
    )

    decision = build_tool_calling_combined_pre_tool_gate_decision(
        question="Give me a tomato soup recipe",
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
        run_pre_tool_gate=True,
        resume_should_resume=False,
        run_resume_gate=True,
        resume_decision=SimpleNamespace(should_resume=False, run=None),
        chat_model_provider=CachedEvidenceAnswerProvider(),
        run_semantic_cache_gate=True,
        settings=SimpleNamespace(semantic_evidence_cache_enabled=True),
        evidence_identity=SimpleNamespace(safe_for_cache_reuse=True),
        toolbox=toolbox,
        runtime_event_bus=RuntimeEventBus(run_id="test"),
        workflow_steps=[],
        tool_calls=[],
    )

    assert decision.action == "return"
    assert decision.sanitized_detail == "off_topic"


def test_combined_post_preflight_gate_prefers_resume_before_semantic_cache() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    run = SimpleNamespace(state_json='{"sources":[],"workflow_steps":[]}')
    toolbox = SimpleNamespace(
        lookup_semantic_evidence_cache=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("resume gate must short-circuit semantic cache")
        )
    )

    decision = build_tool_calling_combined_pre_tool_gate_decision(
        question="问题",
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
        run_pre_tool_gate=False,
        resume_should_resume=True,
        run_resume_gate=True,
        resume_decision=SimpleNamespace(should_resume=True, run=run),
        chat_model_provider=CachedEvidenceAnswerProvider(),
        run_semantic_cache_gate=True,
        settings=SimpleNamespace(semantic_evidence_cache_enabled=True),
        evidence_identity=SimpleNamespace(safe_for_cache_reuse=True),
        toolbox=toolbox,
        runtime_event_bus=RuntimeEventBus(run_id="test"),
        workflow_steps=[],
        tool_calls=[],
    )

    assert decision.action == "return"
    assert decision.sanitized_detail == "resume_checkpoint_without_sources"


def test_coordinator_gate_adapter_returns_service_refusal_before_tool_execution() -> None:
    calls: list[str] = []
    runtime_state = AgentRuntimeState(
        context=RuntimeContext(current_query="Give me a tomato soup recipe")
    )
    planning = SimpleNamespace(
        plan=lambda _: calls.append("plan")
        or SimpleNamespace(
            action=SimpleNamespace(required_tool=None, forbidden_tools=()),
            canonical_task="Give me a tomato soup recipe",
            runtime_state=runtime_state,
            identity=SimpleNamespace(),
        )
    )
    checkpoints = SimpleNamespace(
        start=lambda *_: calls.append("checkpoint_start") or "run-1",
        persist_state=lambda _run, **kwargs: calls.append(f"checkpoint_{kwargs['node']}"),
        complete=lambda *_: calls.append("checkpoint_complete"),
    )
    coordinator = RunCoordinator(
        planning_policy=planning,
        checkpoints=checkpoints,
        tool_executor=SimpleNamespace(
            execute=lambda _: (_ for _ in ()).throw(
                AssertionError("service gate adapter must skip tool execution")
            )
        ),
        evidence_machine=SimpleNamespace(),
        final_answers=SimpleNamespace(),
        pre_tool_gate=ToolCallingCoordinatorGateAdapter(),
    )

    result = coordinator.run(
        CoordinatorRequest(
            question="Give me a tomato soup recipe",
            budget=RunBudget(max_tool_calls=1, max_iterations=1),
            history=(),
            event_sink=None,
            conversation_id=None,
            resume_policy="never",
            resume_run_id=None,
            image_path=None,
            latency_trace=LatencyTrace(),
        )
    )

    assert result.refused
    assert result.workflow_steps[0].tool_name == "off_topic_gate"
    assert calls == [
        "plan",
        "checkpoint_start",
        "checkpoint_final_answer_refused",
        "checkpoint_complete",
    ]


def test_coordinator_gate_adapter_marks_resumed_run_completed() -> None:
    recorded: list[object] = []
    run = SimpleNamespace(state_json='{"sources":[],"workflow_steps":[]}')
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="问题"))
    planning = SimpleNamespace(runtime_state=runtime_state, identity=SimpleNamespace())
    adapter = ToolCallingCoordinatorGateAdapter(
        run_pre_tool_gate=False,
        run_resume_gate=True,
        run_semantic_cache_gate=True,
        resume_decision=SimpleNamespace(should_resume=True, run=run),
        chat_model_provider=CachedEvidenceAnswerProvider(),
        final_answer_strategy="structured_final_answer",
        settings=SimpleNamespace(semantic_evidence_cache_enabled=True),
        toolbox=SimpleNamespace(
            lookup_semantic_evidence_cache=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("resume gate must short-circuit semantic cache")
            )
        ),
        runtime_event_bus=RuntimeEventBus(run_id="test"),
        workflow_steps=[],
        tool_calls=[],
        resume_completion_recorder=recorded.append,
    )

    decision = adapter(
        CoordinatorRequest(
            question="问题",
            budget=RunBudget(max_tool_calls=1, max_iterations=1),
            history=(),
            event_sink=None,
            conversation_id=None,
            resume_policy="auto",
            resume_run_id=None,
            image_path=None,
            latency_trace=LatencyTrace(),
        ),
        planning,
        "new-run",
    )

    assert decision.action == "return"
    assert decision.sanitized_detail == "resume_checkpoint_without_sources"
    assert recorded == [run]


def test_service_passes_auto_resume_run_id_to_coordinator_request(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "true")
    get_settings.cache_clear()
    captured_resume_run_ids: list[str | None] = []
    stopped_run = SimpleNamespace(
        run_id="run-stopped",
        status="stopped",
        last_completed_node="tool_execution_completed",
        state_json='{"sources":[]}',
    )

    class CapturingCoordinator:
        def __init__(self, **_kwargs) -> None:
            pass

        def run(self, request: CoordinatorRequest) -> AgentQueryResult:
            captured_resume_run_ids.append(request.resume_run_id)
            return AgentQueryResult(
                question=request.question,
                answer="resumed",
                tool_calls=[],
                refused=False,
                mode="tool_calling_agent",
                latency_trace={},
            )

    monkeypatch.setattr(
        "app.services.agent.tool_calling_service.decide_resume",
        lambda **_kwargs: SimpleNamespace(
            should_resume=True,
            run=stopped_run,
            reason="explicit_continue",
        ),
    )
    monkeypatch.setattr(
        "app.services.agent.tool_calling_service.RunCoordinator",
        CapturingCoordinator,
    )

    try:
        with make_session(tmp_path)() as db:
            seed_tool_calling_documents(db)
            result = make_service(db).query("堆石混凝土继续", conversation_id=7)
    finally:
        get_settings.cache_clear()

    assert result.answer == "resumed"
    assert captured_resume_run_ids == ["run-stopped"]


def test_coordinator_gate_adapter_preserves_required_tool_preflight_priority() -> None:
    recorded: list[object] = []
    trace = LatencyTrace()
    run = SimpleNamespace(state_json='{"sources":[],"workflow_steps":[]}')
    planning = SimpleNamespace(
        runtime_state=AgentRuntimeState(context=RuntimeContext(current_query="问题")),
        identity=SimpleNamespace(safe_for_cache_reuse=True),
        action=SimpleNamespace(required_tool="search_tables", forbidden_tools=()),
    )
    adapter = ToolCallingCoordinatorGateAdapter(
        run_pre_tool_gate=False,
        run_resume_gate=True,
        run_semantic_cache_gate=True,
        resume_decision=SimpleNamespace(should_resume=True, run=run),
        chat_model_provider=CachedEvidenceAnswerProvider(),
        final_answer_strategy="structured_final_answer",
        settings=SimpleNamespace(semantic_evidence_cache_enabled=True),
        toolbox=SimpleNamespace(
            lookup_semantic_evidence_cache=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("required tool preflight must run before semantic cache")
            )
        ),
        runtime_event_bus=RuntimeEventBus(run_id="test"),
        workflow_steps=[],
        tool_calls=[],
        resume_completion_recorder=recorded.append,
    )

    decision = adapter(
        CoordinatorRequest(
            question="问题",
            budget=RunBudget(max_tool_calls=1, max_iterations=1),
            history=(),
            event_sink=None,
            conversation_id=None,
            resume_policy="auto",
            resume_run_id=None,
            image_path=None,
            latency_trace=trace,
        ),
        planning,
        "new-run",
    )

    assert decision.action == "continue"
    assert recorded == []
    assert (
        trace.values["run_coordinator_pre_tool_gate_skip_reason"]
        == "required_tool_preflight_priority"
    )
    assert trace.values["run_coordinator_required_tool_preflight"] == "search_tables"


def test_coordinator_gate_adapter_allows_post_preflight_resume_after_required_tool() -> None:
    recorded: list[object] = []
    trace = LatencyTrace()
    run = SimpleNamespace(state_json='{"sources":[],"workflow_steps":[]}')
    planning = SimpleNamespace(
        runtime_state=AgentRuntimeState(context=RuntimeContext(current_query="问题")),
        identity=SimpleNamespace(safe_for_cache_reuse=True),
        action=SimpleNamespace(required_tool="search_tables", forbidden_tools=()),
    )
    adapter = ToolCallingCoordinatorGateAdapter(
        run_pre_tool_gate=False,
        run_resume_gate=True,
        run_semantic_cache_gate=True,
        resume_decision=SimpleNamespace(should_resume=True, run=run),
        chat_model_provider=CachedEvidenceAnswerProvider(),
        final_answer_strategy="structured_final_answer",
        settings=SimpleNamespace(semantic_evidence_cache_enabled=True),
        toolbox=SimpleNamespace(
            lookup_semantic_evidence_cache=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("resume gate must short-circuit semantic cache")
            )
        ),
        runtime_event_bus=RuntimeEventBus(run_id="test"),
        workflow_steps=[],
        tool_calls=[],
        resume_completion_recorder=recorded.append,
        defer_required_tool_gates=False,
    )

    decision = adapter(
        CoordinatorRequest(
            question="问题",
            budget=RunBudget(max_tool_calls=1, max_iterations=1),
            history=(),
            event_sink=None,
            conversation_id=None,
            resume_policy="auto",
            resume_run_id=None,
            image_path=None,
            latency_trace=trace,
        ),
        planning,
        "new-run",
    )

    assert decision.action == "return"
    assert decision.sanitized_detail == "resume_checkpoint_without_sources"
    assert recorded == [run]
    assert trace.values.get("run_coordinator_pre_tool_gate_skip_reason") is None


def test_service_query_can_use_run_coordinator_when_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "true")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)
    events: list[ToolCallingRuntimeEvent] = []

    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(
                db,
                chat_provider=CachedEvidenceAnswerProvider(),
            ).query("堆石混凝土缝隙问题", max_tool_calls=2, event_sink=events.append)
    finally:
        get_settings.cache_clear()

    assert result.answer == "Fresh answer generated from cached evidence [1]."
    assert not result.refused
    assert result.tool_calls
    assert result.latency_trace["run_coordinator_enabled"] is True
    assert result.latency_trace["run_coordinator_skip_reason"] == ""
    assert result.latency_trace["runtime_stop_reason"] == "completed"
    event_names = [event.event for event in events]
    assert "agent_step" in event_names
    assert "tool_call_start" in event_names
    assert "tool_call_result" in event_names
    assert any(
        event.event == "agent_step"
        and str(event.payload.get("action", "")).startswith("final_")
        for event in events
    )


def test_run_coordinator_uses_service_final_answer_strategy(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "true")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)
    chat_provider = StrategyCapturingFinalAnswerProvider()

    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(
                db,
                chat_provider=chat_provider,
                final_answer_strategy="baseline",
            ).query("堆石混凝土缝隙问题", max_tool_calls=2)
    finally:
        get_settings.cache_clear()

    assert not result.refused
    assert result.latency_trace["run_coordinator_enabled"] is True
    assert chat_provider.final_messages
    final_system_prompt = chat_provider.final_messages[0].content
    assert "Final answer strategy: baseline" in final_system_prompt
    assert "structured_final_answer" not in final_system_prompt


def test_run_coordinator_uses_phase64_final_answer_provider(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "true")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)
    wrapped_provider = WrappedFinalAnswerProvider()
    seen_original: list[object] = []

    def fake_phase64_final_answer_provider(provider, settings):
        seen_original.append(provider)
        return wrapped_provider

    monkeypatch.setattr(
        "app.services.agent.tool_calling_service.phase64_final_answer_provider",
        fake_phase64_final_answer_provider,
    )
    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            original_provider = DeterministicChatModelProvider()
            result = make_service(
                db,
                chat_provider=original_provider,
            ).query("堆石混凝土缝隙问题", max_tool_calls=2)
    finally:
        get_settings.cache_clear()

    assert seen_original == [original_provider]
    assert wrapped_provider.called
    assert result.answer == "Wrapped final answer [1]."
    assert result.latency_trace["run_coordinator_enabled"] is True


def test_run_coordinator_generates_hyde_on_semantic_cache_miss(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "true")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)

    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(
                db,
                runtime_identity_provider=IdentityAndHydeProvider(),
            ).query("堆石混凝土裂缝现象", max_tool_calls=2)
    finally:
        get_settings.cache_clear()

    assert result.sources
    assert result.latency_trace["semantic_cache_hit"] is False
    assert result.latency_trace["hyde_generated"] is True
    assert result.latency_trace["hyde_used_for_vector"] is True
    assert (
        result.latency_trace["hyde_model"]
        == "runtime-identity-test/identity-hyde-test-v1"
    )
    assert result.latency_trace["run_coordinator_enabled"] is True


def test_service_query_marks_run_coordinator_disabled_when_feature_flag_off(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "false")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)
    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(db).query("堆石混凝土缝隙问题", max_tool_calls=2)
    finally:
        get_settings.cache_clear()

    assert result.latency_trace["run_coordinator_enabled"] is False
    assert result.latency_trace["run_coordinator_skip_reason"] == "disabled"


def test_run_coordinator_preflights_explicit_table_request(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "true")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)
    events: list[ToolCallingRuntimeEvent] = []
    calls: list[str] = []
    hybrid_calls: list[str] = []
    table_item = AgentSearchItem(
        document_id=1,
        document_title="Rock-filled concrete mix table",
        source_type="local_file",
        source_path="mix.md",
        file_name="mix.md",
        chunk_id=30,
        chunk_index=0,
        content="Table: SCC mix ratio for rock-filled concrete.",
        heading_path="Mix ratio",
        score=0.9,
        chunk_type="table",
    )
    table_source = AgentSourceReference(
        source_id="chunk:30",
        title=table_item.document_title,
        source_type=table_item.source_type,
        document_id=table_item.document_id,
        chunk_id=table_item.chunk_id,
        chunk_index=table_item.chunk_index,
        content=table_item.content,
        score=table_item.score,
        chunk_type="table",
    )
    text_item = AgentSearchItem(
        document_id=1,
        document_title="Rock-filled concrete mix explanation",
        source_type="local_file",
        source_path="mix-explain.md",
        file_name="mix-explain.md",
        chunk_id=31,
        chunk_index=1,
        content="Text explanation for SCC mix ratio in rock-filled concrete.",
        heading_path="Mix explanation",
        score=0.8,
        chunk_type="text",
    )
    text_source = AgentSourceReference(
        source_id="chunk:31",
        title=text_item.document_title,
        source_type=text_item.source_type,
        document_id=text_item.document_id,
        chunk_id=text_item.chunk_id,
        chunk_index=text_item.chunk_index,
        content=text_item.content,
        score=text_item.score,
        chunk_type="text",
    )

    def fake_search_tables(self, query: str, top_k: int = 4) -> AgentToolResult:
        calls.append(query)
        return AgentToolResult(
            tool_name="search_tables",
            call=AgentToolCallRecord(
                tool_name="search_tables",
                input_summary=f"query={query}; top_k={top_k}",
                output_summary="returned 1 table results",
                succeeded=True,
            ),
            search_results=[table_item],
            sources=[table_source],
        )

    def fake_hybrid_search(self, query: str, top_k: int = 4) -> AgentToolResult:
        hybrid_calls.append(query)
        return AgentToolResult(
            tool_name="hybrid_search_knowledge",
            call=AgentToolCallRecord(
                tool_name="hybrid_search_knowledge",
                input_summary=f"query={query}; top_k={top_k}",
                output_summary="returned 1 text result",
                succeeded=True,
            ),
            search_results=[text_item],
            sources=[text_source],
        )

    monkeypatch.setattr(
        "app.services.agent.tools.AgentToolbox.search_tables",
        fake_search_tables,
    )
    monkeypatch.setattr(
        "app.services.agent.tools.AgentToolbox.hybrid_search_knowledge",
        fake_hybrid_search,
    )
    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(
                db,
                chat_provider=CachedEvidenceAnswerProvider(),
            ).query(
                "请列出堆石混凝土配合比表格",
                max_tool_calls=3,
                event_sink=events.append,
            )
    finally:
        get_settings.cache_clear()

    assert calls
    assert hybrid_calls
    assert [call.tool_name for call in result.tool_calls[:2]] == [
        "search_tables",
        "hybrid_search_knowledge",
    ]
    assert result.sources[0].chunk_type == "table"
    assert result.sources[1].chunk_type == "text"
    assert result.latency_trace["run_coordinator_enabled"] is True
    assert result.latency_trace["retrieval_required_tool"] == "search_tables"
    tool_result_event = next(
        event
        for event in events
        if event.event == "tool_call_result"
        and event.payload["step_id"] == "runtime-retrieval-1"
    )
    assert tool_result_event.payload["tool_name"] == "search_tables"
    assert tool_result_event.payload["selected_count"] == 1
    hybrid_result_event = next(
        event
        for event in events
        if event.event == "tool_call_result"
        and event.payload["step_id"] == "runtime-retrieval-2"
    )
    assert hybrid_result_event.payload["tool_name"] == "hybrid_search_knowledge"
    assert hybrid_result_event.payload["selected_count"] == 1


def test_run_coordinator_preflights_explicit_figure_request(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "true")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)
    events: list[ToolCallingRuntimeEvent] = []
    calls: list[str] = []
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
        calls.append(query)
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
    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(
                db,
                chat_provider=CachedEvidenceAnswerProvider(),
            ).query(
                "请给我堆石混凝土应力应变曲线图片",
                max_tool_calls=3,
                event_sink=events.append,
            )
    finally:
        get_settings.cache_clear()

    assert calls
    assert result.tool_calls[0].tool_name == "search_figures"
    assert result.sources[0].image_url == "/assets/images/tool_calling_fixture/page3_img1.png"
    assert result.latency_trace["run_coordinator_enabled"] is True
    assert result.latency_trace["retrieval_required_tool"] == "search_figures"
    tool_result_event = next(
        event
        for event in events
        if event.event == "tool_call_result"
        and event.payload["step_id"] == "runtime-retrieval-1"
    )
    assert tool_result_event.payload["tool_name"] == "search_figures"
    assert tool_result_event.payload["selected_count"] == 1


def test_run_coordinator_enabled_uploaded_image_uses_legacy_multimodal_path(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("AGENT_RUN_COORDINATOR_ENABLED", "true")
    get_settings.cache_clear()
    TestingSessionLocal = make_session(tmp_path)
    calls: list[tuple[str, str]] = []

    def fake_analyze_user_image(
        self,
        image_path: str,
        question: str,
        top_k: int = 5,
    ) -> AgentToolResult:
        calls.append((image_path, question))
        return AgentToolResult(
            tool_name="analyze_user_image",
            call=AgentToolCallRecord(
                tool_name="analyze_user_image",
                input_summary="image_path=<user_upload>",
                output_summary="image described; text_results=0; similar_figures=0",
                succeeded=True,
            ),
            answer="图片显示堆石混凝土相关现象。",
            image_analysis={"domain_relevance": "in_scope"},
        )

    monkeypatch.setattr(
        "app.services.agent.tools.AgentToolbox.analyze_user_image",
        fake_analyze_user_image,
    )
    try:
        with TestingSessionLocal() as db:
            seed_tool_calling_documents(db)
            result = make_service(
                db,
                chat_provider=CachedEvidenceAnswerProvider(),
            ).query(
                "请分析这张堆石混凝土图片",
                max_tool_calls=3,
                image_path="uploads/user/image.png",
            )
    finally:
        get_settings.cache_clear()

    assert calls == [("uploads/user/image.png", "请分析这张堆石混凝土图片")]
    assert result.answer == "图片显示堆石混凝土相关现象。"
    assert result.tool_calls[0].tool_name == "analyze_user_image"
    assert result.latency_trace["run_coordinator_enabled"] is False
    assert (
        result.latency_trace["run_coordinator_skip_reason"]
        == "uploaded_image_uses_legacy_multimodal_path"
    )
    assert result.image_analysis == {"domain_relevance": "in_scope"}


def test_final_answer_facade_refusal_preserves_existing_runtime_stop_reason() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="任务"))
    runtime_state.set_stop_reason("deadline_exhausted")
    request = FinalAnswerRequest(
        question="任务",
        history=(),
        strategy="structured_final_answer",
        search_results=(),
        sources=(),
        tool_calls=(),
        workflow_steps=(),
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
        prompt_budgets={},
    )

    outcome = ToolCallingFinalAnswerFacade(
        chat_model_provider=DeterministicChatModelProvider()
    ).refuse(request)

    assert outcome.stop_reason == "deadline_exhausted"
    assert outcome.result.refused
    assert "Runtime deadline was exhausted" in outcome.result.answer
    assert "Runtime deadline was exhausted" in (outcome.result.refusal_reason or "")
    assert outcome.result.latency_trace["runtime_stop_reason"] == "deadline_exhausted"
    assert (
        outcome.result.latency_trace["runtime_normalized_stop_reason"]
        == "deadline_exhausted"
    )
    assert outcome.result.latency_trace["runtime_final_decision"] == "refuse"


def test_final_answer_facade_refusal_uses_bounded_evidence_failure_message() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="任务"))
    runtime_state.set_stop_reason("reranking_failed")
    request = FinalAnswerRequest(
        question="任务",
        history=(),
        strategy="structured_final_answer",
        search_results=(),
        sources=(),
        tool_calls=(),
        workflow_steps=(),
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
        prompt_budgets={},
    )

    outcome = ToolCallingFinalAnswerFacade(
        chat_model_provider=DeterministicChatModelProvider()
    ).refuse(request)

    assert outcome.stop_reason == "insufficient_evidence"
    assert outcome.result.refused
    assert "Evidence reranking failed" in outcome.result.answer
    assert "reliable ranked sources" in (outcome.result.refusal_reason or "")
    assert outcome.result.latency_trace["runtime_stop_reason"] == "reranking_failed"
    assert (
        outcome.result.latency_trace["runtime_normalized_stop_reason"]
        == "insufficient_evidence"
    )


def test_final_answer_facade_refusal_uses_bounded_completed_tool_replay_message() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="任务"))
    runtime_state.set_stop_reason("completed_tool_replay_prevented")
    request = FinalAnswerRequest(
        question="任务",
        history=(),
        strategy="structured_final_answer",
        search_results=(),
        sources=(),
        tool_calls=(),
        workflow_steps=(),
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
        prompt_budgets={},
    )

    outcome = ToolCallingFinalAnswerFacade(
        chat_model_provider=DeterministicChatModelProvider()
    ).refuse(request)

    assert outcome.stop_reason == "checkpoint_unavailable"
    assert outcome.result.refused
    assert "duplicate completed tool execution" in outcome.result.answer
    assert "replaying retrieval" in (outcome.result.refusal_reason or "")
    assert (
        outcome.result.latency_trace["runtime_stop_reason"]
        == "completed_tool_replay_prevented"
    )
    assert (
        outcome.result.latency_trace["runtime_normalized_stop_reason"]
        == "checkpoint_unavailable"
    )


def test_final_answer_facade_refusal_uses_bounded_tool_budget_message() -> None:
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="任务"))
    runtime_state.set_stop_reason("tool_budget_exhausted")
    request = FinalAnswerRequest(
        question="任务",
        history=(),
        strategy="structured_final_answer",
        search_results=(),
        sources=(),
        tool_calls=(),
        workflow_steps=(),
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
        prompt_budgets={},
    )

    outcome = ToolCallingFinalAnswerFacade(
        chat_model_provider=DeterministicChatModelProvider()
    ).refuse(request)

    assert outcome.stop_reason == "tool_budget_exhausted"
    assert outcome.result.refused
    assert "Runtime tool budget was exhausted" in outcome.result.answer
    assert "reliable evidence" in (outcome.result.refusal_reason or "")
    assert outcome.result.latency_trace["runtime_stop_reason"] == "tool_budget_exhausted"
    assert (
        outcome.result.latency_trace["runtime_normalized_stop_reason"]
        == "tool_budget_exhausted"
    )


def test_final_answer_facade_streams_and_emits_safe_citation_suffix() -> None:
    provider = UncitedStreamingChatProvider()
    runtime_state = AgentRuntimeState(context=RuntimeContext(current_query="任务"))
    source = AgentSourceReference(
        source_id="s1",
        title="来源标题",
        source_type="local",
        content="缓存证据",
    )
    request = FinalAnswerRequest(
        question="任务",
        history=(),
        strategy="structured_final_answer",
        search_results=(),
        sources=(source,),
        tool_calls=(),
        workflow_steps=(),
        runtime_state=runtime_state,
        latency_trace=LatencyTrace(),
        prompt_budgets={},
        token_emitter=provider.emit_stream_token,
    )

    outcome = ToolCallingFinalAnswerFacade(chat_model_provider=provider).generate(request)

    assert outcome.stop_reason == "completed"
    assert outcome.citations == (1,)
    assert outcome.result.answer.endswith("证据引用：[1]")
    assert provider.emitted_tokens == [
        "Filling capacity depends on SCC flowability.",
        "\n\n证据引用：[1]",
    ]
    assert outcome.result.latency_trace["streamed_token_count"] == 2
    assert outcome.result.latency_trace["runtime_final_decision"] == "answer"


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


def test_phase63_default_tool_surface_keeps_three_high_level_tools() -> None:
    tool_names = [tool.function.name for tool in tool_calling_tool_definitions()]

    assert tool_names == [
        "hybrid_search_knowledge",
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
