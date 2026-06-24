from collections.abc import Sequence

from app.services.agent.memory_context import (
    DeterministicMemoryIntentClassifier,
    LLMMemoryIntentClassifier,
    MemoryIntent,
    MemoryIntentClassifier,
    build_agent_memory_context,
)
from app.services.generation.chat_model import ChatMessage, ChatModelResult


class StaticIntentProvider:
    provider_name = "static"
    model_name = "intent-test"

    def __init__(self, answer: str) -> None:
        self.answer = answer

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        assert messages
        return ChatModelResult(
            answer=self.answer,
            provider=self.provider_name,
            model_name=self.model_name,
        )


class StaticIntentClassifier:
    def classify(
        self,
        *,
        question: str,
        history: Sequence[str],
        prior_answer_summary: str = "",
    ) -> MemoryIntent:
        del question, history, prior_answer_summary
        return MemoryIntent(
            label="expand_followup",
            confidence=0.77,
            source="test",
            reason="forced by test",
        )


def test_deterministic_memory_intent_classifier_preserves_expand_rule() -> None:
    classifier = DeterministicMemoryIntentClassifier()

    intent = classifier.classify(question="please expand", history=[])

    assert intent.label == "expand_followup"
    assert intent.source == "deterministic"


def test_llm_memory_intent_classifier_accepts_json_intent() -> None:
    classifier = LLMMemoryIntentClassifier(
        StaticIntentProvider(
            '{"intent":"contextual_followup","confidence":0.82,"reason":"refers back"}'
        )
    )

    intent = classifier.classify(
        question="what about that method?",
        history=["user: RFC filling capacity"],
        prior_answer_summary="prior answer",
    )

    assert intent.label == "contextual_followup"
    assert intent.confidence == 0.82
    assert intent.source == "llm"


def test_llm_memory_intent_classifier_falls_back_on_invalid_output() -> None:
    classifier = LLMMemoryIntentClassifier(StaticIntentProvider("not json"))

    intent = classifier.classify(question="please expand", history=[])

    assert intent.label == "expand_followup"
    assert intent.source == "deterministic"


def test_llm_memory_intent_classifier_rejects_unanchored_correction_label() -> None:
    classifier = LLMMemoryIntentClassifier(
        StaticIntentProvider('{"intent":"correction","confidence":0.9,"reason":"switch"}')
    )

    intent = classifier.classify(
        question="I want the topic of permeability testing instead.",
        history=["Earlier topic was cooling pipes."],
    )

    assert intent.label == "new_topic"
    assert intent.source == "deterministic"


def test_build_agent_memory_context_uses_injected_intent_classifier() -> None:
    classifier: MemoryIntentClassifier = StaticIntentClassifier()

    context = build_agent_memory_context(
        question="say more",
        history=["user: What affects rock-filled concrete filling capacity?"],
        prior_evidence={
            "prior_sources": [
                {"source_id": "chunk:1", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:2", "document_title": "doc", "content": "evidence"},
                {"source_id": "chunk:3", "document_title": "doc", "content": "evidence"},
            ],
        },
        intent_classifier=classifier,
    )

    assert context.intent.label == "expand_followup"
    assert context.decision_hint == "reuse_prior_evidence"
    assert context.policy.planner_route == "answer_from_prior_evidence"
