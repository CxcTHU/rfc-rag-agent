from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ConversationCreate, ConversationRepository
from app.db.session import create_sqlite_engine
from app.services.agent.evidence_identity import (
    build_evidence_query_identity,
    refine_evidence_query_identity_with_llm,
)
from app.services.agent.runtime_checkpoint import (
    AgentRuntimeRunRepository,
    decide_resume,
    load_runtime_state,
)
from app.services.agent.tool_calling_service import ToolCallingAgentService
from app.services.generation.chat_model import ChatMessage, ChatModelResult
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.query_embedding_cache import QueryEmbeddingCache


def make_session(tmp_path):
    database_path = tmp_path / "phase58h.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


class ResumeOnlyChatProvider:
    provider_name = "resume-only"
    model_name = "resume-only-v1"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer="堆石混凝土的优势包括降低成本和改善施工效率 [1]。",
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def stream_generate(self, messages: list[ChatMessage]):
        yield self.generate(messages).answer

    def generate_with_tools(self, messages, tools):  # pragma: no cover - should be skipped.
        raise AssertionError("resume should skip tool selection and tool execution")


class CountingEmbeddingProvider:
    provider_name = "counting"
    model_name = "counting-v1"
    dimension = 4

    def __init__(self) -> None:
        self.calls = 0

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        return [float(len(text) % 7), 1.0, 0.0, 0.0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class IdentityClassifierProvider:
    provider_name = "identity-test"
    model_name = "identity-test-v1"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer=(
                '{"entity_key":"rock-filled concrete",'
                '"intent_key":"drawbacks_or_limitations",'
                '"canonical_query":"堆石混凝土 rock-filled concrete 劣势 缺点 局限性 不足 风险",'
                '"confidence":0.92,'
                '"safe_for_cache_reuse":true}'
            ),
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def stream_generate(self, messages: list[ChatMessage]):
        yield self.generate(messages).answer

    def generate_with_tools(self, messages, tools):  # pragma: no cover - not used.
        raise AssertionError("identity classifier should not select tools")


def test_phase58h_open_semantic_identity_uses_llm_instead_of_polarity_wordlist() -> None:
    first_base = build_evidence_query_identity("堆石混凝土的劣势呢？")
    second_base = build_evidence_query_identity("堆石混凝土的缺点有哪些啊？")

    assert not first_base.safe_for_cache_reuse
    assert not second_base.safe_for_cache_reuse

    provider = IdentityClassifierProvider()
    first = refine_evidence_query_identity_with_llm(
        "堆石混凝土的劣势呢？",
        base_identity=first_base,
        provider=provider,
    )
    second = refine_evidence_query_identity_with_llm(
        "堆石混凝土的缺点有哪些啊？",
        base_identity=second_base,
        provider=provider,
    )

    assert first.safe_for_cache_reuse
    assert second.safe_for_cache_reuse
    assert first.entity_key == second.entity_key == "rock-filled concrete"
    assert first.intent_key == second.intent_key == "drawbacks_or_limitations"
    assert first.canonical_query == second.canonical_query
    assert first.source == second.source == "llm"


def test_phase58h_canonical_identity_reuses_query_embedding_cache() -> None:
    provider = CountingEmbeddingProvider()
    cache = QueryEmbeddingCache()
    identity = refine_evidence_query_identity_with_llm(
        "堆石混凝土的缺点有哪些啊？",
        base_identity=build_evidence_query_identity("堆石混凝土的缺点有哪些啊？"),
        provider=IdentityClassifierProvider(),
    )
    trace = LatencyTrace()
    for key, value in identity.diagnostics().items():
        trace.set_value(key, value)
    token = set_current_latency_trace(trace)
    try:
        first = cache.get_or_embed(provider, "堆石混凝土的劣势呢？")
        second = cache.get_or_embed(provider, "堆石混凝土的缺点有哪些啊？")
    finally:
        reset_current_latency_trace(token)

    assert first == second
    assert provider.calls == 1
    assert trace.values["query_embedding_cache_hits"] == 1


def test_phase58h_different_intent_does_not_share_identity() -> None:
    first = build_evidence_query_identity("堆石混凝土的表格数据")
    second = build_evidence_query_identity("堆石混凝土裂缝成因")

    assert first.safe_for_cache_reuse
    assert second.safe_for_cache_reuse
    assert first.entity_key == second.entity_key
    assert first.intent_key == "table_evidence"
    assert second.intent_key == "causes"
    assert first.canonical_query != second.canonical_query


def test_phase58h_followup_uses_history_for_visual_identity() -> None:
    first = build_evidence_query_identity(
        "我需要图片支撑",
        history=("大坝裂缝成因有哪些？请详细列出",),
    )
    second = build_evidence_query_identity(
        "给我相关图示",
        history=("大坝裂缝成因有哪些？请详细列出",),
    )

    assert first.safe_for_cache_reuse
    assert second.safe_for_cache_reuse
    assert first.entity_key == second.entity_key == "dam crack causes"
    assert first.intent_key == second.intent_key == "visual_evidence"


def test_phase58h_resume_decision_handles_continue_and_new_topic(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        conversation = ConversationRepository(db).create_conversation(
            ConversationCreate(title="phase58h")
        )
        repository = AgentRuntimeRunRepository(db)
        run = repository.create_run(
            conversation_id=conversation.id,
            question="堆石混凝土的优势",
            canonical_task="堆石混凝土 优势 优点",
            state={"sources": []},
        )
        repository.mark_stopped(run)

        resume = decide_resume(
            repository=repository,
            conversation_id=conversation.id,
            question="继续",
        )
        new_topic = decide_resume(
            repository=repository,
            conversation_id=conversation.id,
            question="大坝裂缝成因有哪些？",
        )

    assert resume.should_resume
    assert resume.reason == "explicit_continue"
    assert not new_topic.should_resume
    assert new_topic.reason == "new_topic"


def test_phase58h_latest_running_run_can_be_marked_stopped(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        conversation = ConversationRepository(db).create_conversation(
            ConversationCreate(title="phase58h")
        )
        repository = AgentRuntimeRunRepository(db)
        repository.create_run(
            conversation_id=conversation.id,
            question="堆石混凝土的优势",
            canonical_task="堆石混凝土 优势 优点",
            state={"sources": []},
        )

        stopped = repository.mark_latest_running_stopped(
            conversation.id,
            reason="client_stream_aborted",
        )
        stopped_status = stopped.status if stopped is not None else ""
        stopped_state = load_runtime_state(stopped) if stopped is not None else {}

    assert stopped is not None
    assert stopped_status == "stopped"
    assert stopped_state["stop_reason"] == "client_stream_aborted"


def test_phase58h_expired_checkpoint_blocks_resume(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        conversation = ConversationRepository(db).create_conversation(
            ConversationCreate(title="phase58h")
        )
        repository = AgentRuntimeRunRepository(db)
        run = repository.create_run(
            conversation_id=conversation.id,
            question="堆石混凝土的优势",
            canonical_task="堆石混凝土 优势 优点",
            state={"sources": []},
        )
        repository.mark_stopped(run)
        run.expires_at = run.created_at - timedelta(minutes=1)
        db.commit()

        decision = decide_resume(
            repository=repository,
            conversation_id=conversation.id,
            question="继续",
        )

    assert not decision.should_resume
    assert decision.reason == "checkpoint_expired"


def test_phase58h_corrupted_checkpoint_fails_safe(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        conversation = ConversationRepository(db).create_conversation(
            ConversationCreate(title="phase58h")
        )
        repository = AgentRuntimeRunRepository(db)
        run = repository.create_run(
            conversation_id=conversation.id,
            question="堆石混凝土的优势",
            canonical_task="堆石混凝土 优势 优点",
            state={"sources": []},
        )
        repository.mark_stopped(run)
        run.state_json = "["
        db.commit()

        decision = decide_resume(
            repository=repository,
            conversation_id=conversation.id,
            question="继续",
        )

    assert not decision.should_resume
    assert decision.reason == "checkpoint_invalid"


def test_phase58h_tool_calling_service_resumes_from_checkpoint_sources(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        conversation = ConversationRepository(db).create_conversation(
            ConversationCreate(title="phase58h")
        )
        repository = AgentRuntimeRunRepository(db)
        run = repository.create_run(
            conversation_id=conversation.id,
            question="堆石混凝土的优势",
            canonical_task="堆石混凝土 优势 优点",
            state={
                "sources": [
                    {
                        "source_id": "checkpoint-source-1",
                        "title": "RFC advantages source",
                        "source_type": "local_file",
                        "document_id": 1,
                        "chunk_id": 101,
                        "chunk_index": 0,
                        "content": "堆石混凝土可降低成本并改善施工效率。",
                        "score": 0.91,
                    }
                ],
                "workflow_steps": [
                    {
                        "tool_name": "hybrid_search_knowledge",
                        "input_summary": "query=堆石混凝土 优势",
                        "output_summary": "returned checkpoint sources",
                        "succeeded": True,
                        "error": None,
                    }
                ],
            },
        )
        repository.persist_node(run, node="tool_execution_completed", state=load_runtime_state(run))
        repository.mark_stopped(run)

        result = ToolCallingAgentService(
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=ResumeOnlyChatProvider(),
            log_answers=False,
        ).query(
            "继续",
            conversation_id=conversation.id,
            resume_policy="auto",
        )

    assert not result.refused
    assert result.citations == [1]
    assert result.sources[0].chunk_id == 101
    assert result.latency_trace["runtime_resumed"] is True
    assert result.latency_trace["runtime_resume_reason"] == "explicit_continue"
    assert result.latency_trace["executed_tool_call_count"] == 0
