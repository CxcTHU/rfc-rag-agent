from collections.abc import Sequence

from app.services.agent.memory_context import (
    PriorEvidenceMemory,
    PriorEvidenceRelevanceGate,
    build_agent_memory_context,
)


class StaticEmbeddingProvider:
    provider_name = "static"
    model_name = "gate-test"
    dimension = 2

    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        assert len(texts) == 2
        return self.vectors

    def embed_query(self, query: str) -> list[float]:
        raise AssertionError("gate should batch question and prior summary")


def test_prior_evidence_relevance_gate_passes_high_similarity() -> None:
    gate = PriorEvidenceRelevanceGate(
        StaticEmbeddingProvider([[1.0, 0.0], [0.8, 0.0]]),
        threshold=0.5,
    )

    result = gate.evaluate(
        question="please expand",
        history=["user: rock-filled concrete filling capacity"],
        prior=PriorEvidenceMemory(
            sources=({"source_id": "chunk:1"},),
            answer_summary="rock-filled concrete filling capacity",
        ),
    )

    assert result.passed is True
    assert result.score >= 0.5


def test_prior_evidence_relevance_gate_rejects_low_similarity() -> None:
    gate = PriorEvidenceRelevanceGate(
        StaticEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]),
        threshold=0.5,
    )

    result = gate.evaluate(
        question="please expand",
        history=["user: rock-filled concrete filling capacity"],
        prior=PriorEvidenceMemory(
            sources=({"source_id": "chunk:1"},),
            answer_summary="unrelated cooling pipe table",
        ),
    )

    assert result.passed is False
    assert result.score == 0.0


def test_low_relevance_expand_followup_does_not_reuse_prior_evidence() -> None:
    context = build_agent_memory_context(
        question="please expand",
        history=["user: rock-filled concrete filling capacity"],
        prior_evidence={
            "prior_sources": [{"source_id": "chunk:1", "content": "old evidence"}],
            "prior_answer_summary": "unrelated cooling pipe table",
        },
        embedding_provider=StaticEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]),
    )

    assert context.prior_relevance.passed is False
    assert context.decision_hint == "session_memory_retrieval_hint"
    assert context.policy.use_prior_evidence_for_answer is False
