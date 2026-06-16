import csv
from pathlib import Path

from scripts.evaluate_stage41_post_import_retrieval import (
    QUERY_PATH,
    RESULT_FIELDS,
    SUMMARY_FIELDS,
    load_queries,
)


def test_stage41_query_set_covers_new_import_categories() -> None:
    queries = load_queries(QUERY_PATH)
    categories = {query.category for query in queries}
    source_types = {query.expected_source_type for query in queries}

    assert len(queries) >= 12
    assert {"new_cn_rfc", "new_cn_dam", "new_en_rfc"}.issubset(categories)
    assert {"institutional_access_pdf", "open_access_pdf"}.issubset(source_types)


def test_stage41_query_set_has_required_fields() -> None:
    with Path(QUERY_PATH).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        assert set(reader.fieldnames or []) == {
            "query_id",
            "question",
            "category",
            "expected_source_type",
            "expected_title_terms",
            "expected_answer_points",
            "notes",
        }

    for query in load_queries(QUERY_PATH):
        assert query.query_id
        assert query.question
        assert query.expected_title_terms
        assert query.expected_answer_points


def test_stage41_result_and_summary_fields_are_stable() -> None:
    assert "coverage_ratio" in RESULT_FIELDS
    assert "source_type_distribution" in RESULT_FIELDS
    assert "top1_document_title" in RESULT_FIELDS
    assert "avg_coverage_ratio" in SUMMARY_FIELDS
    assert "decision" in SUMMARY_FIELDS
