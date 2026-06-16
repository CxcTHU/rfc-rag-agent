from scripts.analyze_stage38_citation_gaps import analyze


def row(
    query_id: str,
    strategy: str,
    citation_support: str,
    *,
    expected_refused: str = "false",
    refused: str = "false",
) -> dict[str, str]:
    return {
        "query_id": query_id,
        "category": "comparison",
        "strategy": strategy,
        "status": "completed",
        "expected_refused": expected_refused,
        "refused": refused,
        "answer_coverage": "0.800",
        "citation_support": citation_support,
        "citation_count": "3",
        "source_count": "5",
    }


def test_analyze_classifies_prompt_citation_gap() -> None:
    rows = [
        row("q1", "baseline", "0.900"),
        row("q1", "structured_final_answer", "0.500"),
    ]

    analysis = analyze(rows)

    assert analysis[0]["root_cause"] == "prompt_citation_gap"
    assert "baseline passed" in analysis[0]["evidence_note"]


def test_analyze_classifies_retrieval_or_repair_gap() -> None:
    rows = [
        row("q1", "baseline", "0.300"),
        row("q1", "structured_final_answer", "0.500"),
    ]

    analysis = analyze(rows)

    assert analysis[0]["root_cause"] == "retrieval_or_repair_gap"
    assert "both strategies missed" in analysis[0]["evidence_note"]


def test_analyze_classifies_expected_refusal_artifact() -> None:
    rows = [
        row(
            "q1",
            "baseline",
            "1.000",
            expected_refused="true",
            refused="true",
        ),
        row(
            "q1",
            "structured_final_answer",
            "0.000",
            expected_refused="true",
            refused="true",
        ),
    ]

    analysis = analyze(rows)

    assert analysis[0]["root_cause"] == "refusal_judge_artifact"
    assert "expected refusal" in analysis[0]["evidence_note"]
