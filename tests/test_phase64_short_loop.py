from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.agent.evidence_identity import (
    build_evidence_query_identity,
    refine_evidence_query_identity_with_llm,
)
from app.services.agent.tool_calling_service import (
    FinalPromptShape,
    ToolCallingAgentService,
    phase64_final_answer_provider,
    phase64_final_prompt_budgets,
    phase64_runtime_identity_provider,
)
from app.services.agent.tool_calling_service import evidence_answer_messages
from app.services.agent.tools import AgentSourceReference
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelResult,
    OpenAICompatibleChatModelProvider,
    ToolCallingChatModelResult,
)
from app.services.observability.latency_trace import LatencyTrace
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.runtime import (
    RetrievalIntentProfile,
    build_retrieval_action,
    retrieval_tool_for_action,
)
from app.services.retrieval.vector_index import VectorIndexService


class CountingUnifiedPlannerProvider:
    provider_name = "phase64-test-planner"
    model_name = "phase64-test-planner-v1"

    def __init__(self) -> None:
        self.generate_calls = 0

    def generate(self, _messages: object) -> ChatModelResult:
        self.generate_calls += 1
        return ChatModelResult(
            answer=json.dumps(
                {
                    "entity_key": "rock-filled concrete",
                    "intent_key": "crack_phenomena",
                    "canonical_query": "堆石混凝土裂缝原因",
                    "confidence": 0.9,
                    "safe_for_cache_reuse": True,
                    "relationship_intent": 0.95,
                    "relationship_type": "causal",
                    "graph_search_mode": "local",
                    "relationship_explicitness": "explicit",
                    "visual_intent": 0.0,
                    "table_intent": 0.0,
                    "visual_explicitness": "none",
                    "table_explicitness": "none",
                    "entities": ["rock-filled concrete"],
                    "required_evidence_types": ["text", "relationship"],
                    "hyde_passage": "堆石混凝土裂缝与温度应力、界面粘结和施工条件有关。",
                },
                ensure_ascii=False,
            ),
            provider=self.provider_name,
            model_name=self.model_name,
        )


class InvalidJsonProvider(CountingUnifiedPlannerProvider):
    def generate(self, _messages: object) -> ChatModelResult:
        self.generate_calls += 1
        return ChatModelResult(
            answer="not-json",
            provider=self.provider_name,
            model_name=self.model_name,
        )


class MissingRelationPlannerProvider(CountingUnifiedPlannerProvider):
    def generate(self, _messages: object) -> ChatModelResult:
        self.generate_calls += 1
        return ChatModelResult(
            answer=json.dumps(
                {
                    "entity_key": "rock-filled concrete",
                    "intent_key": "filling_effect",
                    "canonical_query": "堆石粒径 孔隙率 自密实混凝土填充效果",
                    "confidence": 0.9,
                    "safe_for_cache_reuse": True,
                    "relationship_intent": 0.0,
                    "relationship_type": "none",
                    "graph_search_mode": "none",
                    "relationship_explicitness": "none",
                    "visual_intent": 0.0,
                    "table_intent": 0.0,
                    "visual_explicitness": "none",
                    "table_explicitness": "none",
                    "entities": ["rock-filled concrete"],
                    "required_evidence_types": ["text"],
                    "hyde_passage": "",
                },
                ensure_ascii=False,
            ),
            provider=self.provider_name,
            model_name=self.model_name,
        )


class FinalStreamingProviderThatFailsOnToolPlanning:
    provider_name = "phase64-final-stream"
    model_name = "phase64-final-stream-v1"

    def __init__(self) -> None:
        self.generate_with_tools_calls = 0
        self.stream_generate_calls = 0

    def generate(self, _messages: list[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer="堆石混凝土的优势包括良好的填充能力 [1]。",
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def stream_generate(self, _messages: list[ChatMessage]):
        self.stream_generate_calls += 1
        yield "堆石混凝土的优势包括良好的填充能力 [1]。"

    def generate_with_tools(
        self,
        _messages: list[ChatMessage],
        _tools: object,
    ) -> ToolCallingChatModelResult:
        self.generate_with_tools_calls += 1
        raise AssertionError("the Phase 64 short loop must not ask the final model to plan tools")


def build_short_loop_service(tmp_path, provider: FinalStreamingProviderThatFailsOnToolPlanning) -> ToolCallingAgentService:
    database_path = tmp_path / "phase64_short_loop.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with session_factory() as db:
        DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Rock-filled concrete guide",
                source_type="local_file",
                source_path="phase64.md",
                file_name="phase64.md",
                file_extension=".md",
                content_hash="phase64-short-loop-fixture",
                raw_path="data/raw/phase64.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="Rock-filled concrete filling capacity depends on concrete flowability and void filling.",
                    char_count=84,
                    heading_path="Advantages",
                    start_char=0,
                    end_char=84,
                )
            ],
        )
        embedding_provider = DeterministicEmbeddingProvider(dimension=32)
        VectorIndexService(db, embedding_provider).build_index()
        return ToolCallingAgentService(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=provider,
            runtime_identity_provider=CountingUnifiedPlannerProvider(),
            log_answers=False,
        )


def test_unified_planner_returns_identity_intent_and_hyde_in_one_call() -> None:
    provider = CountingUnifiedPlannerProvider()
    trace = LatencyTrace()
    identity = refine_evidence_query_identity_with_llm(
        "堆石混凝土裂缝原因",
        base_identity=build_evidence_query_identity("堆石混凝土裂缝原因"),
        provider=provider,
        trace=trace,
        force=True,
    )

    assert provider.generate_calls == 1
    assert identity.retrieval_intent.relationship_explicitness == "explicit"
    assert identity.hyde_passage.startswith("堆石混凝土裂缝")
    assert trace.values["planner_call_count"] == 1
    assert trace.values["hyde_generated"] is True


def test_invalid_unified_planner_falls_back_without_second_call() -> None:
    provider = InvalidJsonProvider()
    identity = refine_evidence_query_identity_with_llm(
        "堆石混凝土优势",
        base_identity=build_evidence_query_identity("堆石混凝土优势"),
        provider=provider,
        force=True,
    )

    assert provider.generate_calls == 1
    assert identity.source == "deterministic"
    assert identity.hyde_passage == ""


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        (RetrievalIntentProfile(), "hybrid_search_knowledge"),
        (RetrievalIntentProfile(table_explicitness="explicit"), "search_tables"),
        (RetrievalIntentProfile(visual_explicitness="explicit"), "search_figures"),
    ],
)
def test_short_loop_maps_plan_to_exactly_one_high_level_tool(
    profile: RetrievalIntentProfile,
    expected: str,
) -> None:
    assert retrieval_tool_for_action(build_retrieval_action(profile)) == expected


def test_short_loop_skips_generate_with_tools_and_streams_final_answer(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    monkeypatch.setenv("SEMANTIC_CACHE_ENABLED", "false")
    get_settings.cache_clear()
    provider = FinalStreamingProviderThatFailsOnToolPlanning()
    result = build_short_loop_service(tmp_path, provider).query("堆石混凝土优势")

    assert provider.generate_with_tools_calls == 0
    assert provider.stream_generate_calls == 1
    assert result.latency_trace["planner_call_count"] == 1
    assert result.latency_trace["final_generation_call_count"] == 1
    assert result.latency_trace["total_model_call_count"] == 2
    assert result.latency_trace["executed_tool_call_count"] == 1


def test_route_first_fast_path_skips_planner_and_records_execution_graph(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    monkeypatch.setenv("PHASE64_ROUTE_FIRST_ENABLED", "true")
    monkeypatch.setenv("PHASE64_FAST_PATH_MIN_SELECTED_SOURCES", "1")
    get_settings.cache_clear()
    provider = FinalStreamingProviderThatFailsOnToolPlanning()
    service = build_short_loop_service(tmp_path, provider)
    planner = service.runtime_identity_provider

    result = service.query("堆石混凝土优势")

    assert isinstance(planner, CountingUnifiedPlannerProvider)
    assert planner.generate_calls == 0
    assert result.latency_trace["phase64_execution_graph"] == "phase64_fast"
    assert result.latency_trace["phase64_route_kind"] == "fast"
    assert result.latency_trace["executed_tool_call_count"] == 1


def test_fast_path_escalates_once_before_generation_when_evidence_is_insufficient(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    monkeypatch.setenv("PHASE64_ROUTE_FIRST_ENABLED", "true")
    monkeypatch.setenv("PHASE64_FAST_PATH_MIN_SELECTED_SOURCES", "2")
    get_settings.cache_clear()
    provider = FinalStreamingProviderThatFailsOnToolPlanning()
    service = build_short_loop_service(tmp_path, provider)
    planner = service.runtime_identity_provider

    result = service.query("堆石混凝土优势")

    assert isinstance(planner, CountingUnifiedPlannerProvider)
    assert planner.generate_calls == 1
    assert result.latency_trace["phase64_fast_escalated"] is True
    assert result.latency_trace["phase64_fast_escalation_reason"] == "insufficient_selected_sources"
    assert result.latency_trace["phase64_execution_graph"] == "phase64_complex"
    assert provider.stream_generate_calls == 1


def test_route_first_explicit_table_keeps_one_complex_planner_call(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    monkeypatch.setenv("PHASE64_ROUTE_FIRST_ENABLED", "true")
    get_settings.cache_clear()
    provider = FinalStreamingProviderThatFailsOnToolPlanning()
    service = build_short_loop_service(tmp_path, provider)
    planner = service.runtime_identity_provider

    result = service.query("查参数表中的水胶比")

    assert isinstance(planner, CountingUnifiedPlannerProvider)
    assert planner.generate_calls == 1
    assert result.latency_trace["phase64_execution_graph"] == "phase64_complex"
    assert result.latency_trace["phase64_route_kind"] == "complex"


def test_route_first_causal_question_preserves_graph_requirement_if_planner_omits_it(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    monkeypatch.setenv("PHASE64_ROUTE_FIRST_ENABLED", "true")
    get_settings.cache_clear()
    provider = FinalStreamingProviderThatFailsOnToolPlanning()
    service = build_short_loop_service(tmp_path, provider)
    service.runtime_identity_provider = MissingRelationPlannerProvider()

    result = service.query("堆石粒径和孔隙率如何影响自密实混凝土填充效果？")

    assert result.latency_trace["phase64_execution_graph"] == "phase64_complex"
    assert result.latency_trace["retrieval_graph_requirement"] == "required"


def test_phase64_final_prompt_respects_exact_character_budgets() -> None:
    sources = [
        AgentSourceReference(
            source_id=f"chunk:{index}",
            title=f"Source {index}",
            source_type="local_file",
            chunk_id=index,
            content="x" * 2000,
        )
        for index in range(12)
    ]
    messages = evidence_answer_messages(
        "问题",
        sources=sources,
        history=["h" * 3000, "x" * 3000],
        max_sources=8,
        snippet_chars=600,
        history_chars=4000,
    )
    content = messages[1].content
    history = content.split("\n\nHistory:\n", 1)[1].split("\n\nContext:\n", 1)[0]
    snippets = [line.removeprefix("snippet=") for line in content.splitlines() if line.startswith("snippet=")]

    assert len(snippets) == 8
    assert len(history) <= 4000
    assert max(map(len, snippets)) <= 600


def test_phase64_b_prompt_budget_tracks_dynamic_k_upper_bound(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    get_settings.cache_clear()

    assert phase64_final_prompt_budgets(get_settings()) == {
        "max_sources": 12,
        "snippet_chars": 320,
        "history_chars": 1000,
        "estimated_input_token_budget": 0,
    }


def test_phase64_final_prompt_shape_is_numeric_and_cjk_sensitive() -> None:
    shape = FinalPromptShape()
    source_text = "中文证据" * 40

    evidence_answer_messages(
        "问题",
        sources=[
            AgentSourceReference(
                source_id="chunk:shape",
                title="Source shape",
                source_type="local_file",
                chunk_id=1,
                content=source_text,
            )
        ],
        prompt_shape=shape,
    )

    assert shape.source_count == 1
    assert shape.cjk_character_count > 0
    assert shape.estimated_input_tokens > 0
    assert source_text not in str(shape.as_trace_values())


def test_phase64_b_trace_records_final_prompt_shape(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    get_settings.cache_clear()
    provider = FinalStreamingProviderThatFailsOnToolPlanning()

    result = build_short_loop_service(tmp_path, provider).query("堆石混凝土优势")

    assert result.latency_trace["final_prompt_estimated_input_tokens"] > 0
    assert result.latency_trace["final_prompt_source_count"] == 1


def test_phase64_b_token_budget_keeps_all_dynamic_k_sources_in_order() -> None:
    sources = [
        AgentSourceReference(
            source_id=f"chunk:{index}",
            title=f"Source {index}",
            source_type="local_file",
            chunk_id=index,
            content="中文证据" * 100,
        )
        for index in range(1, 13)
    ]
    shape = FinalPromptShape()

    messages = evidence_answer_messages(
        "问题",
        sources=sources,
        max_sources=12,
        snippet_chars=320,
        estimated_input_token_budget=1664,
        prompt_shape=shape,
    )

    markers = [line for line in messages[1].content.splitlines() if line.startswith("[")]
    assert markers == [f"[{index}] Source {index}" for index in range(1, 13)]
    assert shape.estimated_input_tokens <= 1664
    assert shape.budget_applied is True


def test_phase64_a_omits_token_budget_when_short_loop_is_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "false")
    monkeypatch.setenv("AGENT_FINAL_ESTIMATED_INPUT_TOKEN_BUDGET", "1664")
    get_settings.cache_clear()

    assert "estimated_input_token_budget" not in phase64_final_prompt_budgets(get_settings())


def test_phase64_final_provider_applies_output_budget_without_mutating_planner(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    monkeypatch.setenv("AGENT_FINAL_MAX_TOKENS", "1200")
    get_settings.cache_clear()
    planner = OpenAICompatibleChatModelProvider(
        model_name="planner",
        api_key="test-key",
        base_url="https://example.test/v1",
        max_tokens=256,
    )

    final_provider = phase64_final_answer_provider(planner, get_settings())

    assert planner.max_tokens == 256
    assert final_provider is not planner
    assert final_provider.max_tokens == 1200


def test_final_provider_applies_output_budget_when_short_loop_is_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "false")
    monkeypatch.setenv("AGENT_FINAL_MAX_TOKENS", "900")
    get_settings.cache_clear()
    provider = OpenAICompatibleChatModelProvider(
        model_name="deepseek-v4-pro",
        api_key="test-key",
        base_url="https://api.deepseek.com",
        max_tokens=None,
    )

    final_provider = phase64_final_answer_provider(provider, get_settings())

    assert provider.max_tokens is None
    assert final_provider is not provider
    assert final_provider.max_tokens == 900


def test_final_provider_disables_deepseek_thinking_when_short_loop_is_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "false")
    monkeypatch.setenv("PHASE64_FINAL_NON_THINKING_ENABLED", "true")
    monkeypatch.setenv("AGENT_FINAL_MAX_TOKENS", "600")
    get_settings.cache_clear()
    provider = OpenAICompatibleChatModelProvider(
        model_name="deepseek-v4-pro",
        api_key="test-key",
        base_url="https://api.deepseek.com",
        extra_body={"existing": "preserved"},
    )

    final_provider = phase64_final_answer_provider(provider, get_settings())

    assert provider.extra_body == {"existing": "preserved"}
    assert final_provider is not provider
    assert final_provider.max_tokens == 600
    assert final_provider.extra_body == {
        "existing": "preserved",
        "thinking": {"type": "disabled"},
    }


def test_phase64_final_provider_disables_deepseek_thinking_only_for_route_first_b(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    monkeypatch.setenv("PHASE64_ROUTE_FIRST_ENABLED", "true")
    monkeypatch.setenv("PHASE64_FINAL_NON_THINKING_ENABLED", "true")
    get_settings.cache_clear()
    provider = OpenAICompatibleChatModelProvider(
        model_name="deepseek-v4-pro",
        api_key="test-key",
        base_url="https://api.deepseek.com",
        extra_body={"existing": "preserved"},
    )

    final_provider = phase64_final_answer_provider(provider, get_settings())

    assert provider.extra_body == {"existing": "preserved"}
    assert final_provider is not provider
    assert final_provider.extra_body == {
        "existing": "preserved",
        "thinking": {"type": "disabled"},
    }


def test_phase64_final_provider_disables_thinking_for_flash_b(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    monkeypatch.setenv("PHASE64_ROUTE_FIRST_ENABLED", "true")
    monkeypatch.setenv("PHASE64_FINAL_NON_THINKING_ENABLED", "true")
    get_settings.cache_clear()
    provider = OpenAICompatibleChatModelProvider(
        model_name="deepseek-v4-flash",
        api_key="test-key",
        base_url="https://api.deepseek.com",
    )

    final_provider = phase64_final_answer_provider(provider, get_settings())

    assert provider.extra_body == {}
    assert final_provider.model_name == "deepseek-v4-flash"
    assert final_provider.extra_body == {"thinking": {"type": "disabled"}}


def test_phase64_runtime_identity_provider_disables_deepseek_thinking_only_for_b(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    monkeypatch.setenv("PHASE64_ROUTE_FIRST_ENABLED", "true")
    monkeypatch.setenv("PHASE64_FINAL_NON_THINKING_ENABLED", "true")
    get_settings.cache_clear()
    provider = OpenAICompatibleChatModelProvider(
        model_name="deepseek-v4-pro",
        api_key="test-key",
        base_url="https://api.deepseek.com",
    )

    planner_provider = phase64_runtime_identity_provider(provider, get_settings())

    assert provider.extra_body == {}
    assert planner_provider is not provider
    assert planner_provider.extra_body == {"thinking": {"type": "disabled"}}
