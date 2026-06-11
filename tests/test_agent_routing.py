import pytest

from app.services.agent.routing import classify_query_complexity


def test_classify_query_complexity_simple_concept() -> None:
    result = classify_query_complexity("What affects filling capacity in rock-filled concrete?")

    assert result.complexity == "simple"
    assert result.reasons


def test_classify_query_complexity_complex_compare() -> None:
    result = classify_query_complexity(
        "Search and compare filling capacity and thermal control mechanisms in rock-filled concrete."
    )

    assert result.complexity == "complex"
    assert "comparison" in result.signals
    assert "search_analysis_combo" in result.signals


def test_classify_query_complexity_complex_multi_evidence() -> None:
    result = classify_query_complexity(
        "Explain how flowability, aggregate grading, hydration heat, and "
        "adiabatic temperature rise jointly affect construction quality in rock-filled concrete."
    )

    assert result.complexity == "complex"
    assert result.score >= 2
    assert {"moderate_length", "several_clauses", "multi_aspect"}.intersection(result.signals)


def test_classify_query_complexity_keeps_direct_source_requests_simple() -> None:
    result = classify_query_complexity("Please list sources for filling capacity.")

    assert result.complexity == "simple"
    assert result.signals == ("direct_source_request",)


def test_classify_query_complexity_short_search_is_simple() -> None:
    result = classify_query_complexity("Search filling capacity")

    assert result.complexity == "simple"
    assert result.score < 2


def test_classify_query_complexity_rejects_blank_question() -> None:
    with pytest.raises(ValueError, match="question must not be empty"):
        classify_query_complexity("   ")
