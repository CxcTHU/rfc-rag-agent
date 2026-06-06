import csv

from scripts.analyze_retrieval_errors import (
    ErrorCase,
    analyze_error_cases,
    chat_failure_type,
    write_error_cases,
)


def write_csv(path, fieldnames, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_analyze_error_cases_records_vector_keyword_gap(tmp_path) -> None:
    keyword_queries = tmp_path / "keyword_queries.csv"
    keyword_results = tmp_path / "keyword_results.csv"
    vector_results = tmp_path / "vector_results.csv"
    hybrid_results = tmp_path / "hybrid_results.csv"
    chat_queries = tmp_path / "chat_queries.csv"
    chat_results = tmp_path / "chat_results.csv"

    write_csv(
        keyword_queries,
        [
            "query_id",
            "question",
            "query",
            "top_k",
            "expected_title_terms",
            "expected_content_terms",
            "expected_source_types",
            "notes",
        ],
        [
            {
                "query_id": "filling",
                "question": "Question?",
                "query": "filling capacity",
                "top_k": "8",
                "expected_title_terms": "Filling Capacity",
                "expected_content_terms": "",
                "expected_source_types": "local_file",
                "notes": "",
            }
        ],
    )
    write_csv(
        keyword_results,
        ["query_id", "query", "passed", "top_titles"],
        [{"query_id": "filling", "query": "filling capacity", "passed": "yes", "top_titles": "Expected"}],
    )
    write_csv(
        vector_results,
        ["query_id", "query", "passed", "comparison", "top_titles"],
        [
            {
                "query_id": "filling",
                "query": "filling capacity",
                "passed": "no",
                "comparison": "keyword_only_pass",
                "top_titles": "Wrong Topic",
            }
        ],
    )
    write_csv(
        hybrid_results,
        ["query_id", "passed"],
        [{"query_id": "filling", "passed": "yes"}],
    )
    write_csv(
        chat_queries,
        [
            "query_id",
            "question",
            "expected_refused",
            "expected_source_title_terms",
            "expected_source_content_terms",
        ],
        [],
    )
    write_csv(chat_results, ["query_id", "passed"], [])

    cases = analyze_error_cases(
        keyword_queries,
        chat_queries,
        keyword_results,
        vector_results,
        hybrid_results,
        chat_results,
    )

    assert len(cases) == 1
    assert cases[0].evaluator == "vector"
    assert cases[0].failure_type == "keyword_only_pass"
    assert "Filling Capacity" in cases[0].expected_terms
    assert "hybrid search" in cases[0].suggested_fix
    assert cases[0].after_status == "fixed_by_hybrid"


def test_chat_failure_type_prefers_specific_quality_dimension() -> None:
    assert chat_failure_type({"returned_answer": "no"}) == "no_answer"
    assert (
        chat_failure_type(
            {
                "returned_answer": "yes",
                "refusal_matched": "no",
                "expected_refused": "no",
                "refused": "yes",
            }
        )
        == "over_refusal"
    )
    assert (
        chat_failure_type(
            {
                "returned_answer": "yes",
                "refusal_matched": "yes",
                "citations_valid": "no",
            }
        )
        == "citation_miss"
    )


def test_write_error_cases_uses_stable_schema(tmp_path) -> None:
    output_path = tmp_path / "errors.csv"

    write_error_cases(
        output_path,
        [
            ErrorCase(
                query_id="q1",
                query="query",
                evaluator="vector",
                failure_type="keyword_only_pass",
                expected_terms="term",
                actual_top_titles="title",
                likely_reason="reason",
                suggested_fix="fix",
                before_status="failed",
            )
        ],
    )

    with output_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["query_id"] == "q1"
    assert rows[0]["after_status"] == "pending"
