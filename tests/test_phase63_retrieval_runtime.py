import json
from pathlib import Path

import networkx as nx
import pytest

from app.core.config import Settings
from app.services.agent.evidence_identity import (
    raw_identity,
    refine_evidence_query_identity_with_llm,
)
from app.services.generation.chat_model import ChatModelResult
from app.services.graphrag.graph_store import load_graph, save_graph
from app.services.graphrag.retriever import GraphRetriever, graph_content_fingerprint
from app.services.retrieval.reranking import ReRankResult
from app.services.retrieval.runtime import (
    RetrievalIntentProfile,
    build_retrieval_action,
    build_retrieval_plan,
    current_retrieval_plan,
    deterministic_intent_profile,
    reset_current_retrieval_plan,
    retrieval_plan_digest,
    set_current_retrieval_plan,
)
from app.services.retrieval.hybrid_search import (
    HybridSearchResult,
    rerank_candidate_text,
    rerank_input_identity_hash,
    reserve_required_rerank_candidates,
    select_reranked_results,
)


class RelationshipIdentityProvider:
    provider_name = "phase63-test"
    model_name = "phase63-intent-v1"

    def generate(self, messages) -> ChatModelResult:
        return ChatModelResult(
            answer=json.dumps(
                {
                    "entity_key": "GB/T 50081",
                    "intent_key": "standard_reference",
                    "canonical_query": "GB/T 50081 抗压强度试验 标准关系",
                    "confidence": 0.94,
                    "safe_for_cache_reuse": True,
                    "visual_intent": 0.02,
                    "table_intent": 0.08,
                    "relationship_intent": 0.93,
                    "relationship_type": "standard_reference",
                    "graph_search_mode": "local",
                    "visual_explicitness": "none",
                    "table_explicitness": "none",
                    "relationship_explicitness": "explicit",
                    "entities": ["GB/T 50081", "抗压强度试验"],
                    "required_evidence_types": ["text", "relationship"],
                },
                ensure_ascii=False,
            ),
            provider=self.provider_name,
            model_name=self.model_name,
        )


class UnsafeContradictoryVisualIdentityProvider(RelationshipIdentityProvider):
    model_name = "phase63-unsafe-visual-v1"

    def generate(self, messages) -> ChatModelResult:
        return ChatModelResult(
            answer=json.dumps(
                {
                    "entity_key": "rock-filled concrete",
                    "intent_key": "visual_explanation",
                    "canonical_query": "rock-filled concrete crack explanation",
                    "confidence": 0.55,
                    "safe_for_cache_reuse": False,
                    "visual_intent": 0.99,
                    "visual_explicitness": "explicit",
                    "required_evidence_types": ["text", "figure"],
                },
                ensure_ascii=False,
            ),
            provider=self.provider_name,
            model_name=self.model_name,
        )


class NegativeVisualIdentityProvider(RelationshipIdentityProvider):
    model_name = "phase63-negative-visual-v1"

    def generate(self, messages) -> ChatModelResult:
        return ChatModelResult(
            answer=json.dumps(
                {
                    "entity_key": "rock-filled concrete",
                    "intent_key": "visual_explanation",
                    "canonical_query": "rock-filled concrete figure",
                    "confidence": 0.8,
                    "safe_for_cache_reuse": False,
                    "visual_intent": 0.0,
                    "visual_explicitness": "negative",
                    "required_evidence_types": ["text"],
                }
            ),
            provider=self.provider_name,
            model_name=self.model_name,
        )


def write_phase63_relation_graph(tmp_path: Path) -> Path:
    graph = nx.MultiDiGraph(schema_version="phase53-networkx-v1")
    graph.add_node(
        "Standard:gb/t 50081",
        name="GB/T 50081",
        type="Standard",
        normalized_name="gb/t 50081",
        mentions=["GB/T 50081"],
        chunk_ids=[1],
    )
    graph.add_node(
        "Parameter:compressive-strength",
        name="抗压强度试验",
        type="Parameter",
        normalized_name="抗压强度试验",
        mentions=["抗压强度试验"],
        chunk_ids=[2],
    )
    graph.add_edge(
        "Standard:gb/t 50081",
        "Parameter:compressive-strength",
        type="defines",
        source_chunk_id=1,
        evidence="GB/T 50081 定义了混凝土抗压强度试验方法。",
    )
    path = tmp_path / "phase63-graph.json"
    save_graph(graph, path)
    return path


def test_phase63_explicit_relationship_maps_to_required_graph_plan() -> None:
    profile = RetrievalIntentProfile(
        relationship_intent=0.91,
        relationship_type="standard_reference",
        graph_search_mode="local",
        relationship_explicitness="explicit",
        entities=("GB/T 50081", "抗压强度试验"),
        required_evidence_types=("text", "relationship"),
        source="llm",
    )

    plan = build_retrieval_plan(
        profile,
        "抗压强度试验适用什么标准",
        Settings(),
    )

    assert plan.graph_requirement == "required"
    assert plan.graph_budget_profile == "relation"
    assert plan.graph_max_hops == 2
    assert plan.graph_max_matches == 50
    assert plan.required_evidence_types == ("text", "relationship")


def test_phase63_negative_visual_intent_disables_caption_channel() -> None:
    profile = RetrievalIntentProfile(
        visual_intent=0.99,
        visual_explicitness="negative",
        source="llm",
    )

    plan = build_retrieval_plan(
        profile,
        "只用文字，不要图片",
        Settings(),
    )

    assert plan.figure_caption_requirement == "disabled"


def test_phase63_implicit_relationship_uses_preferred_budget() -> None:
    profile = RetrievalIntentProfile(
        relationship_intent=0.62,
        relationship_type="causal",
        graph_search_mode="local",
        relationship_explicitness="implicit",
        source="llm",
    )

    plan = build_retrieval_plan(profile, "裂缝成因和施工过程", Settings())

    assert plan.graph_requirement == "preferred"
    assert plan.graph_budget_profile == "preferred"
    assert plan.graph_max_hops == 1
    assert plan.graph_max_matches == 20


def test_phase63_deterministic_fallback_prefers_graph_for_relationship_query() -> None:
    profile = deterministic_intent_profile(
        "GB/T 50081与抗压强度试验是什么关系？"
    )

    assert profile.relationship_intent >= 0.45
    assert profile.relationship_type == "standard_reference"
    assert profile.graph_search_mode == "local"
    assert profile.source == "deterministic_fallback"


def test_phase63_deterministic_fallback_respects_entity_relationship_negation() -> None:
    profile = deterministic_intent_profile(
        "只解释堆石混凝土的定义，不分析实体关系或上下游关系"
    )

    assert profile.relationship_explicitness == "negative"
    assert profile.graph_search_mode == "none"
    assert "relationship" not in profile.required_evidence_types


def test_phase63_current_explicit_visual_request_overrides_historical_negative() -> None:
    profile = deterministic_intent_profile(
        "现在请给我堆石混凝土施工图片",
        history=("上一轮：不要图片，只用文字。",),
    )

    assert profile.visual_explicitness == "explicit"
    assert profile.visual_intent >= 0.85
    assert "figure" in profile.required_evidence_types


def test_phase63_negative_table_citation_request_keeps_text_route() -> None:
    profile = deterministic_intent_profile("不要引用表格解释堆石混凝土配合比设计原则")
    action = build_retrieval_action(profile)

    assert profile.table_explicitness == "negative"
    assert profile.relationship_explicitness == "none"
    assert "table" not in profile.required_evidence_types
    assert "relationship" not in profile.required_evidence_types
    assert action.required_tool is None
    assert action.forbidden_tools == ("search_figures", "search_tables")


def test_phase63_negative_image_instruction_with_use_verb_keeps_text_route() -> None:
    profile = deterministic_intent_profile("请再次说明 RFC 的优势但不要使用图片")
    action = build_retrieval_action(profile)

    assert profile.visual_explicitness == "negative"
    assert profile.visual_intent == 0.0
    assert "figure" not in profile.required_evidence_types
    assert action.required_tool is None
    assert "search_figures" in action.forbidden_tools


def test_phase63_applicable_conditions_alone_do_not_require_graph() -> None:
    profile = deterministic_intent_profile(
        "综合比较堆石混凝土的技术优势适用条件质量风险和控制措施"
    )
    plan = build_retrieval_plan(profile, "safe synthetic query", Settings())

    assert profile.relationship_explicitness == "none"
    assert "relationship" not in profile.required_evidence_types
    assert plan.graph_requirement == "disabled"


def test_phase63_negative_causal_instruction_disables_graph() -> None:
    profile = deterministic_intent_profile(
        "不要分析因果关系只给出堆石混凝土质量检测项目清单"
    )
    plan = build_retrieval_plan(profile, "safe synthetic query", Settings())

    assert profile.relationship_explicitness == "negative"
    assert profile.relationship_intent == 0.0
    assert "relationship" not in profile.required_evidence_types
    assert plan.graph_requirement == "disabled"


@pytest.mark.parametrize(
    ("query", "required_tool", "forbidden_tools"),
    [
        ("请给我堆石混凝土施工图片", "search_figures", ("search_tables",)),
        ("请列出堆石混凝土配合比表格", "search_tables", ("search_figures",)),
        ("只用文字解释堆石混凝土，不要图片", None, ("search_figures", "search_tables")),
        ("不要表格，请文字说明堆石混凝土", None, ("search_figures", "search_tables")),
        ("坝址区岩石或岩体的力学性质参数有哪些？", None, ("search_figures", "search_tables")),
    ],
)
def test_phase63_runtime_builds_symmetric_explicit_asset_action(
    query: str,
    required_tool: str | None,
    forbidden_tools: tuple[str, ...],
) -> None:
    action = build_retrieval_action(deterministic_intent_profile(query))

    assert action.required_tool == required_tool
    assert action.forbidden_tools == forbidden_tools


def test_phase63_retrieval_plan_context_is_scoped_and_digest_is_stable() -> None:
    plan = build_retrieval_plan(
        RetrievalIntentProfile(source="llm"),
        "堆石混凝土定义",
        Settings(),
    )
    first_digest = retrieval_plan_digest(plan)

    token = set_current_retrieval_plan(plan)
    try:
        assert current_retrieval_plan() == plan
        assert retrieval_plan_digest(current_retrieval_plan()) == first_digest
    finally:
        reset_current_retrieval_plan(token)

    assert current_retrieval_plan() is None
    assert retrieval_plan_digest(None) == "legacy"


def test_phase63_runtime_settings_are_guarded_by_default() -> None:
    settings = Settings()

    assert settings.retrieval_runtime_enabled is True
    assert settings.retrieval_runtime_default_enabled is True
    assert settings.retrieval_runtime_schema == "phase63-gap-closure-v1"


def test_phase63_llm_identity_response_also_builds_retrieval_intent() -> None:
    query = "GB/T 50081与抗压强度试验是什么关系？"

    identity = refine_evidence_query_identity_with_llm(
        query,
        base_identity=raw_identity(
            query,
            "missing_intent",
            entity_key="GB/T 50081",
        ),
        provider=RelationshipIdentityProvider(),
    )

    assert identity.source == "llm"
    assert identity.retrieval_intent.relationship_intent == 0.93
    assert identity.retrieval_intent.relationship_type == "standard_reference"
    assert identity.retrieval_intent.relationship_explicitness == "explicit"
    assert identity.retrieval_intent.required_evidence_types == (
        "text",
        "relationship",
    )


def test_phase63_invalid_llm_identity_keeps_deterministic_intent_fallback() -> None:
    query = "GB/T 50081与抗压强度试验是什么关系？"

    class InvalidIdentityProvider(RelationshipIdentityProvider):
        def generate(self, messages) -> ChatModelResult:
            return ChatModelResult(
                answer="not-json",
                provider=self.provider_name,
                model_name=self.model_name,
            )

    identity = refine_evidence_query_identity_with_llm(
        query,
        base_identity=raw_identity(query, "missing_intent"),
        provider=InvalidIdentityProvider(),
    )

    assert identity.safe_for_cache_reuse is False
    assert identity.reason == "llm_identity_invalid_json"
    assert identity.retrieval_intent.relationship_intent >= 0.45
    assert identity.retrieval_intent.source == "deterministic_fallback"


def test_phase63_cache_unsafe_identity_keeps_valid_intent_but_hard_negative_wins() -> None:
    query = "只用文字解释堆石混凝土裂缝，不要图片"

    identity = refine_evidence_query_identity_with_llm(
        query,
        base_identity=raw_identity(query, "missing_intent"),
        provider=UnsafeContradictoryVisualIdentityProvider(),
        force=True,
    )

    assert identity.safe_for_cache_reuse is False
    assert identity.source == "llm"
    assert identity.retrieval_intent.source == "llm"
    assert identity.retrieval_intent.visual_intent == 0.0
    assert identity.retrieval_intent.visual_explicitness == "negative"
    assert "figure" not in identity.retrieval_intent.required_evidence_types


def test_phase63_deterministic_explicit_visual_intent_survives_conflicting_llm() -> None:
    query = "请给我堆石混凝土图片"

    identity = refine_evidence_query_identity_with_llm(
        query,
        base_identity=raw_identity(query, "missing_intent"),
        provider=NegativeVisualIdentityProvider(),
        force=True,
    )

    assert identity.retrieval_intent.visual_explicitness == "explicit"
    assert identity.retrieval_intent.visual_intent >= 0.85
    assert "figure" in identity.retrieval_intent.required_evidence_types


def test_phase63_graph_retriever_preserves_provenance_and_caps_candidates(tmp_path: Path) -> None:
    graph_path = write_phase63_relation_graph(tmp_path)

    outcome = GraphRetriever(graph_path=graph_path).retrieve(
        "GB/T 50081 与抗压强度试验是什么关系？",
        max_hops=2,
        max_matches=1,
    )

    assert outcome.summary.available is True
    assert outcome.summary.fallback is False
    assert len(outcome.candidates) == 1
    assert outcome.candidates[0].chunk_id == 1
    assert outcome.candidates[0].matched_node_ids
    assert outcome.candidates[0].relation_types == ("defines",)
    assert "GB/T 50081" in outcome.candidates[0].relation_evidence[0]
    assert outcome.fingerprint == graph_content_fingerprint(graph_path)

    first_fingerprint = outcome.fingerprint
    graph_path.write_text(
        graph_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    assert graph_content_fingerprint(graph_path) != first_fingerprint


def test_phase63_graph_retriever_avoids_copying_the_entire_graph_for_local_walk(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path = write_phase63_relation_graph(tmp_path)
    graph = load_graph(graph_path)

    def fail_if_full_copy_is_requested():
        raise AssertionError("local graph traversal must not clone the full graph")

    monkeypatch.setattr(graph, "to_undirected", fail_if_full_copy_is_requested)
    outcome = GraphRetriever(graph=graph).retrieve(
        "GB/T 50081 与抗压强度试验是什么关系？",
        max_hops=2,
        max_matches=1,
    )

    assert len(outcome.candidates) == 1
    assert outcome.candidates[0].relation_types


def test_graph_store_reuses_unchanged_graph_file_and_invalidates_changed_version(
    tmp_path: Path,
) -> None:
    graph_path = write_phase63_relation_graph(tmp_path)

    first = load_graph(graph_path)
    second = load_graph(graph_path)

    assert second is first
    first.add_node("Material:changed", name="changed", type="Material")
    save_graph(first, graph_path)

    refreshed = load_graph(graph_path)

    assert refreshed is not first
    assert refreshed.has_node("Material:changed")


def test_phase63_graph_retriever_fails_open_when_graph_is_missing(tmp_path: Path) -> None:
    outcome = GraphRetriever(graph_path=tmp_path / "missing.json").retrieve(
        "标准和试验方法有什么关系？",
        max_hops=1,
        max_matches=20,
    )

    assert outcome.candidates == []
    assert outcome.summary.available is False
    assert outcome.summary.fallback is True
    assert outcome.summary.error == "FileNotFoundError"
    assert outcome.fingerprint == "missing"


def test_phase63_required_graph_candidate_is_reserved_in_rerank_pool() -> None:
    def result(chunk_id: int, channels: tuple[str, ...]) -> HybridSearchResult:
        return HybridSearchResult(
            document_id=1,
            document_title=f"doc-{chunk_id}",
            source_type="local_file",
            source_path=None,
            file_name="doc.md",
            chunk_id=chunk_id,
            chunk_index=chunk_id,
            content=f"content-{chunk_id}",
            heading_path=None,
            score=1.0 / chunk_id,
            keyword_score=0.0,
            vector_score=0.0,
            channels=channels,
        )

    plan = build_retrieval_plan(
        RetrievalIntentProfile(
            relationship_intent=0.95,
            relationship_type="causal",
            graph_search_mode="local",
            relationship_explicitness="explicit",
        ),
        "relationship query",
        Settings(),
    )
    pool = reserve_required_rerank_candidates(
        [result(1, ("keyword",)), result(2, ("vector",)), result(3, ("graph",))],
        limit=2,
        plan=plan,
    )

    assert [item.chunk_id for item in pool] == [1, 3]


def test_phase63_required_table_and_figure_candidates_are_reserved_before_rerank() -> None:
    def result(chunk_id: int, channels: tuple[str, ...]) -> HybridSearchResult:
        return HybridSearchResult(
            document_id=1,
            document_title=f"doc-{chunk_id}",
            source_type="local_file",
            source_path=None,
            file_name=f"doc-{chunk_id}.md",
            chunk_id=chunk_id,
            chunk_index=0,
            content=f"content-{chunk_id}",
            heading_path=None,
            score=1.0 / chunk_id,
            keyword_score=0.0,
            vector_score=0.0,
            channels=channels,
        )

    plan = build_retrieval_plan(
        RetrievalIntentProfile(
            table_intent=0.95,
            table_explicitness="explicit",
            visual_intent=0.95,
            visual_explicitness="explicit",
            required_evidence_types=("text", "table", "figure"),
        ),
        "table and figure query",
        Settings(),
    )
    pool = reserve_required_rerank_candidates(
        [
            result(1, ("bm25",)),
            result(2, ("vector",)),
            result(3, ("table_text",)),
            result(4, ("figure_caption",)),
        ],
        limit=2,
        plan=plan,
    )

    assert len(pool) == 2
    assert {channel for item in pool for channel in item.channels} == {
        "table_text",
        "figure_caption",
    }


def test_phase63_required_graph_evidence_survives_final_dynamic_k_selection() -> None:
    def result(chunk_id: int, score: float, channels: tuple[str, ...]) -> HybridSearchResult:
        return HybridSearchResult(
            document_id=1,
            document_title=f"doc-{chunk_id}",
            source_type="local_file",
            source_path=None,
            file_name=f"doc-{chunk_id}.md",
            chunk_id=chunk_id,
            chunk_index=0,
            content=f"content-{chunk_id}",
            heading_path=None,
            score=score,
            keyword_score=0.0,
            vector_score=0.0,
            channels=channels,
        )

    candidates = [
        result(1, 1.0, ("bm25",)),
        result(2, 0.8, ("vector",)),
        result(3, 0.1, ("graph",)),
    ]
    reranked = [
        ReRankResult(index=0, score=1.0, content="content-1"),
        ReRankResult(index=1, score=0.8, content="content-2"),
        ReRankResult(index=2, score=0.1, content="content-3"),
    ]

    selected = select_reranked_results(
        candidates,
        reranked,
        requested_top_k=2,
        settings=Settings(
            reranking_dynamic_min_results=1,
            reranking_dynamic_max_results=2,
            reranking_dynamic_relative_score_threshold=0.65,
        ),
        required_channels=("graph",),
    )

    assert [item.chunk_id for item in selected] == [1, 3]


def test_phase63_relation_provenance_is_bounded_into_rerank_text_and_identity() -> None:
    result = HybridSearchResult(
        document_id=1,
        document_title="Standard Relationship",
        source_type="standard_document",
        source_path=None,
        file_name="standard.pdf",
        chunk_id=7,
        chunk_index=0,
        content="GB/T 50081 defines the compressive strength test.",
        heading_path="Test method",
        score=0.8,
        keyword_score=0.0,
        vector_score=0.0,
        channels=("graph",),
        relation_types=("defines",),
        relation_evidence=("GB/T 50081 --defines--> compressive strength",),
    )

    text = rerank_candidate_text(result)

    assert isinstance(text, str)
    assert "Graph relation types: defines" in text
    assert "--defines-->" in text
    assert len(rerank_input_identity_hash([result])) == 64
