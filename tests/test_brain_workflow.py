from dataclasses import dataclass

from app.services.brain.workflow import (
    build_retrieval_outcome,
    evaluate_evidence_confidence,
    extract_citations,
)


@dataclass(frozen=True)
class FakeSearchResult:
    document_id: int = 1
    document_title: str = "Thermal control guide"
    source_type: str = "local_file"
    source_path: str | None = "thermal.md"
    file_name: str = "thermal.md"
    chunk_id: int = 1
    chunk_index: int = 0
    content: str = "Thermal control reduces hydration heat."
    heading_path: str | None = "Thermal"
    score: float = 1.0


def test_build_retrieval_outcome_filters_by_min_score() -> None:
    high_score = FakeSearchResult(chunk_id=1, score=0.8)
    low_score = FakeSearchResult(chunk_id=2, score=0.2)

    outcome = build_retrieval_outcome(
        raw_results=[high_score, low_score],
        used_retrieval_mode="hybrid",
        min_score=0.5,
    )

    assert outcome.used_retrieval_mode == "hybrid"
    assert outcome.results == [high_score]
    assert outcome.refusal_reason is None


def test_build_retrieval_outcome_refuses_when_no_results_meet_threshold() -> None:
    outcome = build_retrieval_outcome(
        raw_results=[FakeSearchResult(score=0.2)],
        used_retrieval_mode="keyword",
        min_score=0.5,
    )

    assert outcome.results == []
    assert outcome.used_retrieval_mode == "keyword"
    assert "minimum score" in (outcome.refusal_reason or "")


def test_evaluate_evidence_confidence_accepts_shared_query_terms() -> None:
    confidence = evaluate_evidence_confidence(
        "What affects filling capacity in rock-filled concrete?",
        [
            FakeSearchResult(
                document_title="Filling capacity guide",
                content="Self compacting concrete flowability improves filling capacity.",
            )
        ],
    )

    assert confidence.sufficient
    assert "filling" in confidence.matched_terms
    assert confidence.score > 0


def test_evaluate_evidence_confidence_rejects_unsupported_token() -> None:
    confidence = evaluate_evidence_confidence(
        "zqxjvblorptasticprotocol",
        [FakeSearchResult(content="Thermal control reduces hydration heat.")],
    )

    assert not confidence.sufficient
    assert confidence.score == 0
    assert "share no" in (confidence.refusal_reason or "")


def test_evaluate_evidence_confidence_accepts_cross_language_expanded_terms() -> None:
    confidence = evaluate_evidence_confidence(
        "孔隙率会怎么影响堆石混凝土抗压表现？",
        [
            FakeSearchResult(
                document_title="Void effect study on compressive behavior",
                content="Porosity and void defects influence compressive behavior.",
            )
        ],
    )

    assert confidence.sufficient
    assert "porosity" in confidence.matched_terms


def test_extract_citations_returns_unique_allowed_source_ids() -> None:
    assert extract_citations("Use [2], [1], [2], and [99].", [1, 2]) == [2, 1]
