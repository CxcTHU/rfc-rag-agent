from dataclasses import dataclass

from app.services.brain.workflow import build_retrieval_outcome, extract_citations


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


def test_extract_citations_returns_unique_allowed_source_ids() -> None:
    assert extract_citations("Use [2], [1], [2], and [99].", [1, 2]) == [2, 1]
