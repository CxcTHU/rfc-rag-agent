import json

from app.services.agent.memory_context import (
    DisabledLongTermMemoryProvider,
    MEMORY_CONTEXT_SCHEMA_VERSION,
    MEMORY_TRACE_FIELDS,
    MemoryConsent,
    MemoryDeletionRequest,
    MemoryIntent,
    MemoryRetentionPolicy,
    agent_memory_context_from_state,
    augment_query_with_agent_memory,
    build_agent_memory_context,
    should_use_prior_evidence_for_answer,
)


def test_agent_memory_context_combines_session_and_prior_evidence() -> None:
    context = build_agent_memory_context(
        question="请详细回答",
        history=["用户：堆石混凝土填充密实性受流动性影响吗？"],
        prior_evidence={
            "prior_sources": [
                {"source_id": "chunk:1", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:2", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:3", "document_title": "doc", "content": "evidence"},
            ],
            "prior_citations": [1, "2"],
            "prior_answer_summary": "上一轮回答摘要",
        },
    )

    assert "堆石混凝土" in context.session.entities
    assert context.prior_evidence.source_count == 3
    assert context.prior_evidence.citations == (1, 2)
    assert context.decision_hint == "reuse_prior_evidence"
    assert should_use_prior_evidence_for_answer(context, "请详细回答")
    assert context.trace()["memory_prior_source_count"] == 3


def test_agent_memory_context_marks_correction_anchors_stale() -> None:
    context = build_agent_memory_context(
        question="更正一下，我想问 Peridynamics 用于裂纹分析的证据",
        history=["user:Peridynamics is a construction quality control method?"],
        prior_evidence={
            "prior_sources": [
                {"source_id": "chunk:1", "document_title": "doc", "content": "old evidence"},
                {"source_id": "chunk:2", "document_title": "doc", "content": "old evidence"},
                {"source_id": "chunk:3", "document_title": "doc", "content": "old evidence"},
            ],
        },
    )

    assert context.session.stale_anchors
    assert context.decision_hint == "stale_anchor_refresh_search"
    assert not should_use_prior_evidence_for_answer(context, "请详细回答")


def test_agent_memory_context_round_trips_state_dict() -> None:
    context = build_agent_memory_context(
        question="它的流动性为什么重要？",
        history=["用户：自密实混凝土在堆石混凝土中起什么作用？"],
        prior_evidence={},
    )

    restored = agent_memory_context_from_state(context.to_state_dict())

    assert restored.session.entities == context.session.entities
    assert restored.session.retrieval_anchors == context.session.retrieval_anchors
    assert restored.long_term.enabled is False
    assert restored.long_term.status == "disabled"
    assert restored.policy.planner_route == context.policy.planner_route


def test_agent_memory_context_state_contract_is_json_native() -> None:
    context = build_agent_memory_context(
        question="please expand",
        history=["user: What affects rock-filled concrete filling capacity?"],
        prior_evidence={
            "prior_sources": [
                {"source_id": "chunk:1", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:2", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:3", "document_title": "doc", "content": "evidence"},
            ],
            "prior_citations": [1, 2, 3],
            "prior_answer_summary": "sanitized prior answer",
        },
    )

    state = context.to_state_dict()
    encoded = json.dumps(state, ensure_ascii=False, sort_keys=True)
    restored = agent_memory_context_from_state(json.loads(encoded))

    assert state["schema_version"] == MEMORY_CONTEXT_SCHEMA_VERSION
    assert isinstance(state["session"]["entities"], list)
    assert isinstance(state["prior_evidence"]["sources"], list)
    assert isinstance(state["policy"], dict)
    assert restored.policy.planner_route == "answer_from_prior_evidence"
    assert restored.policy.use_prior_evidence_for_answer is True


def test_agent_memory_context_restores_legacy_string_session_memory() -> None:
    context = agent_memory_context_from_state(
        {
            "session": {
                "entities": ["rfc"],
                "retrieval_anchors": ["durability"],
                "constraints": [],
                "stale_anchors": ["old-anchor"],
            }
        }
    )

    assert "rfc" in context.session.entities
    assert context.session.entities[0].turn_index == 0
    assert context.session.entities[0].importance == 1.0
    assert "durability" in context.session.retrieval_anchors
    assert "old-anchor" in context.session.stale_anchors


def test_agent_memory_context_trace_contract_is_safe_and_complete() -> None:
    context = build_agent_memory_context(
        question="What affects rock-filled concrete permeability?",
        history=[],
        prior_evidence={},
    )

    trace = context.trace()

    assert set(trace) == set(MEMORY_TRACE_FIELDS)
    assert trace["memory_citation_source"] is False
    assert all("content" not in field for field in trace)


def test_augment_query_with_agent_memory_is_retrieval_only() -> None:
    context = build_agent_memory_context(
        question="它的流动性为什么重要？",
        history=["用户：自密实混凝土在堆石混凝土中起什么作用？"],
        prior_evidence={},
    )

    augmented = augment_query_with_agent_memory("它的流动性为什么重要？", context)

    assert "会话检索记忆" in augmented
    assert "不作为引用来源" in augmented


def test_disabled_long_term_memory_provider_is_read_none_write_none() -> None:
    provider = DisabledLongTermMemoryProvider()

    read_state = provider.read(user_id="u1", conversation_id="c1")
    write_state = provider.write(
        user_id="u1",
        conversation_id="c1",
        payload={"preference": "should not persist"},
    )

    assert read_state.enabled is False
    assert read_state.read_count == 0
    assert write_state.enabled is False
    assert write_state.write_count == 0
    deletion = provider.delete(
        MemoryDeletionRequest(user_id="u1", conversation_id="c1")
    )
    assert deletion.status == "disabled_noop"
    assert deletion.user_id_present is True
    assert deletion.conversation_id_present is True


def test_long_term_memory_retention_policy_is_disabled_by_default() -> None:
    policy = MemoryRetentionPolicy()

    assert policy.status == "disabled"
    assert policy.max_age_days is None
    assert policy.deletion_supported is True


def test_long_term_memory_consent_is_disabled_by_default() -> None:
    consent = MemoryConsent(user_id="u1", conversation_id="c1")

    assert consent.long_term_memory_enabled is False
    assert consent.source == "default_disabled"


def test_disabled_long_term_provider_does_not_echo_payload_or_reason() -> None:
    provider = DisabledLongTermMemoryProvider()

    write_state = provider.write(
        user_id="u1",
        conversation_id="c1",
        payload={"private_profile": "do not persist or echo"},
    )
    deletion = provider.delete(
        MemoryDeletionRequest(
            user_id="u1",
            conversation_id="c1",
            reason="contains private deletion reason",
        )
    )

    assert write_state.enabled is False
    assert write_state.write_count == 0
    assert deletion.detail == "long-term memory is disabled"
    assert "private" not in deletion.detail


def test_memory_policy_allows_prior_evidence_only_for_expand_followups() -> None:
    context = build_agent_memory_context(
        question="please expand",
        history=["user: What affects rock-filled concrete filling capacity?"],
        prior_evidence={
            "prior_sources": [
                {"source_id": "chunk:1", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:2", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:3", "document_title": "doc", "content": "evidence"},
            ],
            "prior_citations": [1, 2, 3],
            "prior_answer_summary": "sanitized prior answer",
        },
    )

    assert context.policy.planner_route == "answer_from_prior_evidence"
    assert context.policy.use_prior_evidence_for_answer is True
    assert context.policy.memory_used_for_answer is True
    assert context.policy.memory_citation_source is False
    assert context.trace()["memory_prior_evidence_used_for_answer"] is True
    assert should_use_prior_evidence_for_answer(context, "please expand")


def test_memory_policy_keeps_memory_context_out_of_answer_citations() -> None:
    context = build_agent_memory_context(
        question="What thermal control measures apply to rock-filled concrete?",
        history=["user: What affects rock-filled concrete filling capacity?"],
        prior_evidence={
            "prior_sources": [
                {"source_id": "chunk:1", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:2", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:3", "document_title": "doc", "content": "evidence"},
            ],
        },
    )

    assert context.policy.planner_route == "search_with_memory_context"
    assert context.policy.memory_used_for_planning is True
    assert context.policy.memory_used_for_answer is False
    assert context.policy.memory_citation_source is False
    assert context.policy.refusal_boundary == "memory_is_not_evidence"
    assert not should_use_prior_evidence_for_answer(context, context.policy.reason)


class StaticOffTopicIntentClassifier:
    def classify(self, *, question, history, prior_answer_summary=""):
        return MemoryIntent(
            label="off_topic",
            confidence=1.0,
            source="test",
            reason="forced off-topic boundary",
        )


def test_off_topic_memory_policy_does_not_use_memory_for_retrieval_or_answer() -> None:
    context = build_agent_memory_context(
        question="How do I cook pasta?",
        history=["user: Explain rock-filled concrete thermal control."],
        prior_evidence={
            "prior_sources": [
                {"source_id": "chunk:1", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:2", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:3", "document_title": "doc", "content": "evidence"},
            ],
            "prior_citations": [1, 2, 3],
            "prior_answer_summary": "sanitized prior answer",
        },
        intent_classifier=StaticOffTopicIntentClassifier(),
    )

    assert context.intent.label == "off_topic"
    assert context.policy.planner_route == "refuse_or_clarify"
    assert context.policy.memory_used_for_retrieval is False
    assert context.policy.memory_used_for_answer is False
    assert context.policy.use_prior_evidence_for_answer is False
    assert context.policy.memory_citation_source is False
    assert context.policy.refusal_boundary == "off_topic_memory_not_applicable"


class StaticExpandIntentClassifier:
    def classify(self, *, question, history, prior_answer_summary=""):
        return MemoryIntent(
            label="expand_followup",
            confidence=1.0,
            source="test",
            reason="forced expansion for low-relevance guard",
        )


class LowButPassingEmbeddingProvider:
    provider_name = "test"
    model_name = "low-passing"
    dimension = 2

    def embed_texts(self, texts):
        assert len(texts) == 2
        return [[1.0, 0.0], [0.6, 0.8]]

    def embed_query(self, query):
        return [1.0, 0.0]


def test_recent_topic_shift_blocks_direct_prior_reuse_even_when_relevance_passes() -> None:
    context = build_agent_memory_context(
        question="Please continue this point.",
        history=[
            "user: Earlier topic was hydration heat.",
            "assistant: Hydration heat affects temperature gradients.",
            "user: Latest topic is aggregate grading and void ratio.",
            "assistant: Aggregate grading controls void ratio and filling paths.",
        ],
        prior_evidence={
            "prior_sources": [
                {"source_id": "chunk:1", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:2", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:3", "document_title": "doc", "content": "evidence"},
            ],
            "prior_citations": [1, 2, 3],
            "prior_answer_summary": "Hydration heat causes thermal gradients.",
        },
        intent_classifier=StaticExpandIntentClassifier(),
        embedding_provider=LowButPassingEmbeddingProvider(),
    )

    assert context.prior_relevance.passed is True
    assert context.policy.planner_route == "search_with_memory_context"
    assert context.policy.use_prior_evidence_for_answer is False
    assert context.policy.memory_used_for_retrieval is False
    assert context.policy.memory_used_for_answer is False
